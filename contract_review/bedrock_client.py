"""Amazon Bedrock access: knowledge base retrieval and Converse analysis."""
from __future__ import annotations

import json
import re
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import BEDROCK, BedrockConfig
from .models import RetrievedChunk

# Adaptive retry backs off automatically on throttling.
_BOTO_CONFIG = Config(retries={"max_attempts": 5, "mode": "adaptive"}, read_timeout=300)

_RETRYABLE = {
    "ThrottlingException",
    "ModelTimeoutException",
    "ServiceUnavailableException",
    "InternalServerException",
}


class BedrockClient:
    """Thin wrapper over bedrock-agent-runtime (Retrieve) and bedrock-runtime (Converse)."""

    def __init__(self, config: BedrockConfig | None = None) -> None:
        self.config = config or BEDROCK
        session = boto3.Session(region_name=self.config.region)
        self._agent_runtime = session.client("bedrock-agent-runtime", config=_BOTO_CONFIG)
        self._runtime = session.client("bedrock-runtime", config=_BOTO_CONFIG)
        self.input_tokens = 0
        self.output_tokens = 0

    # -- retrieval ---------------------------------------------------------
    def retrieve(self, query: str, number_of_results: int | None = None) -> list[RetrievedChunk]:
        """Fetch reference excerpts from the knowledge base.

        Retrieve-only (not RetrieveAndGenerate) because the analysis prompt is
        assembled here: the reference excerpts are one input among several.
        """
        count = number_of_results or self.config.retrieval_results
        try:
            response = self._agent_runtime.retrieve(
                knowledgeBaseId=self.config.knowledge_base_id,
                retrievalQuery={"text": query[:20000]},  # hard API limit
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": count}
                },
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            raise RuntimeError(f"Knowledge base retrieval failed ({code}): {exc}") from exc

        chunks: list[RetrievedChunk] = []
        for result in response.get("retrievalResults", []):
            location = result.get("location", {})
            uri = location.get("s3Location", {}).get("uri", "") or json.dumps(location)
            chunks.append(
                RetrievedChunk(
                    text=result.get("content", {}).get("text", ""),
                    source_uri=uri,
                    score=float(result.get("score", 0.0) or 0.0),
                )
            )
        return chunks

    # -- generation --------------------------------------------------------
    def converse_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        """Call Converse and parse a single JSON object out of the reply."""
        messages = [{"role": "user", "content": [{"text": user_prompt}]}]
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            try:
                response = self._runtime.converse(
                    modelId=self.config.model_id,
                    system=[{"text": system_prompt}],
                    messages=messages,
                    inferenceConfig={
                        # maxTokens is always explicit: an unset value reserves
                        # the model maximum from the account quota.
                        "maxTokens": self.config.max_tokens,
                        "temperature": self.config.temperature,
                    },
                )
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in _RETRYABLE and attempt < max_attempts:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"Bedrock Converse failed ({code}): {exc}") from exc

            usage = response.get("usage", {})
            self.input_tokens += int(usage.get("inputTokens", 0) or 0)
            self.output_tokens += int(usage.get("outputTokens", 0) or 0)

            text = "".join(
                block.get("text", "")
                for block in response["output"]["message"]["content"]
                if "text" in block
            )
            parsed = _extract_json(text)
            if parsed is not None:
                return parsed

            last_error = text[:400]
            # Ask for a correction on the next pass rather than discarding work.
            messages = [
                {"role": "user", "content": [{"text": user_prompt}]},
                {"role": "assistant", "content": [{"text": text[:4000]}]},
                {
                    "role": "user",
                    "content": [
                        {
                            "text": "That reply was not a single parseable JSON object. "
                            "Reply again with only the JSON object described earlier."
                        }
                    ],
                },
            ]

        raise ValueError(f"Model did not return parseable JSON. Last reply began: {last_error}")


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull one JSON object out of a model reply, tolerating code fences."""
    if not text:
        return None

    candidates: list[str] = []
    fenced = _FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text)

    for candidate in candidates:
        candidate = candidate.strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Fall back to the outermost balanced { ... } span.
        start = candidate.find("{")
        if start == -1:
            continue
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(candidate)):
            char = candidate[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(candidate[start : index + 1])
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        break
    return None
