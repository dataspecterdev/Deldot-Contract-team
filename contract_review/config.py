"""Central configuration for the contract clause risk flagging pipeline."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Repository layout ---------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
CHALLENGE_ROOT = REPO_ROOT / "Contract_Clause_Risk_Flagging"

REFERENCE_CHECKLIST = CHALLENGE_ROOT / "References" / "Reference_Checklist.csv"
SUBMISSION_SCHEMA = CHALLENGE_ROOT / "Submission" / "Submission_Schema.csv"
SEVERITY_GUIDANCE = CHALLENGE_ROOT / "Evaluation" / "Severity_Guidance.csv"
SOURCES_DIR = CHALLENGE_ROOT / "Sources"

DEVELOPMENT_DIR = CHALLENGE_ROOT / "Development"
VALIDATION_DIR = CHALLENGE_ROOT / "Validation"
DEVELOPMENT_LABELS = DEVELOPMENT_DIR / "Development_Labels.csv"

OUTPUT_DIR = REPO_ROOT / "output"


@dataclass(frozen=True)
class BedrockConfig:
    """Amazon Bedrock settings.

    Every value can be overridden with an environment variable so the pipeline
    can be pointed at a different account/region without code changes.
    """

    region: str = field(default_factory=lambda: os.environ.get("AWS_REGION", "us-east-1"))
    knowledge_base_id: str = field(
        default_factory=lambda: os.environ.get("KB_ID", "7BKLBOJA7F")
    )
    # Cross-region inference profile: higher availability than a bare model id.
    model_id: str = field(
        default_factory=lambda: os.environ.get(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6"
        )
    )
    # maxTokens MUST be explicit; leaving it unset reserves the model maximum
    # from the account quota and is the most common cause of throttling.
    max_tokens: int = 4096
    temperature: float = 0.0
    retrieval_results: int = 4


BEDROCK = BedrockConfig()

# Submission enumerations --------------------------------------------------
APPLIES = "APPLIES"
DOES_NOT_APPLY = "DOES_NOT_APPLY"
FLAG = "FLAG"
NO_FLAG = "NO_FLAG"
SEVERITIES = ("Critical", "High", "Medium", "Low", "Info")

# Order of precedence from DelDOT 105.6, most authoritative first. A later
# Addendum that explicitly revises a named provision outranks all of these.
PRECEDENCE_ORDER = (
    "General Description",
    "General Notices",
    "Plans",
    "Special Provisions",
    "Standard Construction Details",
    "Standard Specifications",
    "Electronic Design Data Files",
)
