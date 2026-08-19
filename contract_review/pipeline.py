"""Orchestration: contract package + reference knowledge base -> findings.

Flow for one package:

1. Extract every PDF into provenance-rich lines (page, line, char offsets).
2. Decide applicability deterministically from Project_Metadata.json.
3. Resolve which document governs each requirement after Addenda.
4. For each applicable requirement: retrieve reference excerpts from the Bedrock
   knowledge base, render the requirement's skill prompt over the line-tagged
   package text, and call Converse.
5. Verify the model's cited lines and quote against the real package text.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import applicability, evidence, precedence, prompts
from .bedrock_client import BedrockClient
from .checklist import load_requirements
from .config import APPLIES, DOES_NOT_APPLY, FLAG, NO_FLAG, SEVERITIES
from .extraction import load_package, render_numbered_text
from .models import ContractPackage, Finding, Requirement, RetrievedChunk


def _retrieval_query(requirement: Requirement) -> str:
    """Query text for the reference knowledge base.

    Built from the requirement identity plus the challenge rule, which carries
    the concrete numbers (percentages, day counts) that discriminate between the
    reference sections.
    """
    return " ".join(
        part
        for part in (
            requirement.requirement_id,
            requirement.name,
            requirement.section,
            requirement.reference_source,
            requirement.challenge_reference_rule,
        )
        if part
    )


def _clean_severity(value: Any, label: str, guidance: str) -> str:
    """Normalise severity.

    NO_FLAG is always Info. For a FLAG the checklist's own Severity_Guidance is
    authoritative - it states the challenge severity for that requirement - so it
    is preferred over the model's choice, which drifts between adjacent levels.
    """
    if label == NO_FLAG:
        return "Info"
    from_checklist = str(guidance or "").strip().title()
    if from_checklist in SEVERITIES and from_checklist != "Info":
        return from_checklist
    text = str(value or "").strip().title()
    return text if text in SEVERITIES and text != "Info" else "Medium"


def _clean_label(value: Any) -> str:
    return FLAG if str(value or "").strip().upper() == FLAG else NO_FLAG


def _clean_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return round(min(max(number, 0.0), 1.0), 2)


@dataclass
class PackageResult:
    package: ContractPackage
    findings: list[Finding]


class ReviewPipeline:
    """Runs the review for a package or a directory of packages."""

    def __init__(
        self,
        client: BedrockClient | None = None,
        requirements: list[Requirement] | None = None,
        max_workers: int = 4,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.client = client or BedrockClient()
        self.requirements = list(requirements or load_requirements())
        self.max_workers = max(1, max_workers)
        self._progress = progress or (lambda message: None)
        self._reference_cache: dict[str, list[RetrievedChunk]] = {}

    # -- reference retrieval ------------------------------------------------
    def _reference_chunks(self, requirement: Requirement) -> list[RetrievedChunk]:
        """Retrieve reference excerpts once per requirement, then reuse."""
        cached = self._reference_cache.get(requirement.requirement_id)
        if cached is not None:
            return cached
        try:
            chunks = self.client.retrieve(_retrieval_query(requirement))
        except RuntimeError as exc:
            self._progress(f"  ! retrieval failed for {requirement.requirement_id}: {exc}")
            chunks = []
        self._reference_cache[requirement.requirement_id] = chunks
        return chunks

    # -- single requirement -------------------------------------------------
    def _not_applicable_finding(
        self,
        package: ContractPackage,
        requirement: Requirement,
        reason: str,
        governing: precedence.GoverningDocument,
    ) -> Finding:
        # Identify the metadata field that drove the exclusion
        draft_loc, draft_ev = self._exclusion_evidence(requirement, package.metadata)
        return Finding(
            document_id=package.package_id,
            requirement_id=requirement.requirement_id,
            applicability_decision=DOES_NOT_APPLY,
            applicability_reason=reason,
            predicted_label=NO_FLAG,
            severity="Info",
            governing_document=governing.file_name,
            draft_location=draft_loc,
            draft_evidence=draft_ev,
            reference_id=requirement.requirement_id,
            reference_location=f"{requirement.reference_source} - {requirement.section}",
            reference_evidence=requirement.challenge_reference_rule,
            explanation=(
                f"Requirement does not apply to this package. {reason} "
                "No clause comparison was performed."
            ),
            confidence=0.95,
            recommended_human_action="No action; confirm applicability against project metadata.",
            notes="applicability excluded by project metadata",
        )

    @staticmethod
    def _exclusion_evidence(requirement: Requirement, metadata: dict) -> tuple[str, str]:
        """Return (draft_location, draft_evidence) showing which metadata excluded this requirement."""
        # Map requirement IDs to the metadata field that gates them
        field_map: dict[str, str] = {
            "CC-01": "federal_aid",
            "CC-08": "issued_addenda",
            "CC-09": "buy_america_baba_applicable",
            "CC-14": "subcontracting_planned",
            "CC-15": "claim_event",
            "CC-16": "delay_event",
            "CC-18": "changed_work_event",
        }
        field = field_map.get(requirement.requirement_id)
        if field and field in metadata:
            value = metadata[field]
            return (
                f"Project_Metadata.json - {field}: {value}",
                f"{field} = {value}",
            )
        # Fallback: show that metadata was checked but field not mapped
        return (
            "Project_Metadata.json",
            f"Applicability excluded by project metadata ({requirement.applicability_rule})",
        )

    def analyze_requirement(
        self,
        package: ContractPackage,
        requirement: Requirement,
        governing: precedence.GoverningDocument,
        numbered_text: str,
    ) -> Finding:
        decision = applicability.decide(requirement.requirement_id, package.metadata)
        if decision.decision == DOES_NOT_APPLY:
            return self._not_applicable_finding(
                package, requirement, decision.reason, governing
            )

        # Retrieve chunks for confidence scoring only — they are NOT sent to the
        # model prompt. The challenge_reference_rule is the sole scoring authority.
        chunks = self._reference_chunks(requirement)
        user_prompt = prompts.build_user_prompt(
            requirement=requirement,
            package_id=package.package_id,
            metadata=package.metadata,
            governing=governing,
            numbered_package_text=numbered_text,
            applicability_reason=decision.reason,
        )

        try:
            raw = self.client.converse_json(prompts.SYSTEM_PROMPT, user_prompt)
        except (RuntimeError, ValueError) as exc:
            self._progress(
                f"  ! analysis failed for {package.package_id}/{requirement.requirement_id}: {exc}"
            )
            return Finding(
                document_id=package.package_id,
                requirement_id=requirement.requirement_id,
                applicability_decision=APPLIES,
                applicability_reason=decision.reason,
                predicted_label=NO_FLAG,
                severity="Info",
                governing_document=governing.file_name,
                draft_location="",
                draft_evidence="",
                reference_id=requirement.requirement_id,
                reference_location=f"{requirement.reference_source} - {requirement.section}",
                reference_evidence=requirement.challenge_reference_rule,
                explanation=(
                    "Automated analysis did not complete for this requirement, so no "
                    "deviation is asserted. Manual review required."
                ),
                confidence=0.0,
                recommended_human_action="Review manually; automated analysis failed.",
                notes=f"analysis error: {exc}",
            )

        label = _clean_label(raw.get("predicted_label"))
        severity = _clean_severity(raw.get("severity"), label, requirement.severity_guidance)

        cited = raw.get("cited_line_ids") or []
        if isinstance(cited, str):
            cited = [cited]
        located = evidence.locate(
            package,
            [str(c) for c in cited],
            str(raw.get("draft_evidence") or ""),
            preferred_file=governing.file_name,
        )

        # Retrieval score used only for confidence adjustment, NOT sent to model.
        retrieval_percent = round(max((c.score for c in chunks), default=0.0) * 100, 1)

        # Composite confidence: model confidence weighted by retrieval agreement.
        # If the KB retrieval strongly matches the requirement (high score), the
        # model's confidence is boosted; if retrieval is weak or absent, the
        # confidence is tempered — this is the ONLY role Sources play now.
        model_confidence = _clean_confidence(raw.get("confidence"))
        retrieval_factor = min(retrieval_percent / 100.0, 1.0)
        # Weighted: 70% model confidence + 30% retrieval agreement
        adjusted_confidence = round(0.7 * model_confidence + 0.3 * retrieval_factor, 2)

        # Prefer the verified location over the model's free-text description:
        # it is derived from the real file and is directly checkable.
        draft_location = located.location or str(raw.get("draft_location") or "")

        return Finding(
            document_id=package.package_id,
            requirement_id=requirement.requirement_id,
            applicability_decision=APPLIES,
            applicability_reason=decision.reason,
            predicted_label=label,
            severity=severity,
            governing_document=str(raw.get("governing_document") or governing.file_name),
            draft_location=draft_location,
            draft_evidence=str(raw.get("draft_evidence") or "").strip(),
            reference_id=requirement.requirement_id,
            reference_location=f"{requirement.reference_source} - {requirement.section}",
            reference_evidence=requirement.challenge_reference_rule,
            explanation=str(raw.get("explanation") or "").strip(),
            confidence=adjusted_confidence,
            recommended_human_action=str(raw.get("recommended_human_action") or "").strip()
            or ("Review and confirm with contract administration." if label == FLAG else "No action required."),
            cited_line_ids=located.line_ids,
            evidence_match_percent=located.match_percent,
            retrieval_score_percent=retrieval_percent,
            retrieved_sources=[c.source_name for c in chunks],
            notes="; ".join(located.notes),
        )

    # -- whole package -----------------------------------------------------
    def run_package(self, package_dir: Path | str) -> PackageResult:
        package = load_package(Path(package_dir))
        self._progress(
            f"[{package.package_id}] {len(package.documents)} documents, "
            f"{len(package.all_lines)} indexed lines"
        )

        governing = precedence.resolve_all(package, self.requirements)
        numbered_text = render_numbered_text(package)

        # Warm the reference cache serially so parallel workers share it.
        for requirement in self.requirements:
            if applicability.decide(requirement.requirement_id, package.metadata).decision == APPLIES:
                self._reference_chunks(requirement)

        def work(requirement: Requirement) -> Finding:
            finding = self.analyze_requirement(
                package, requirement, governing[requirement.requirement_id], numbered_text
            )
            marker = "FLAG" if finding.predicted_label == FLAG else "ok  "
            self._progress(
                f"  {marker} {finding.requirement_id} {finding.applicability_decision:15s} "
                f"{finding.severity:8s} evidence={finding.evidence_match_percent:5.1f}%"
            )
            return finding

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            findings = list(pool.map(work, self.requirements))

        findings.sort(key=lambda f: f.requirement_id)
        return PackageResult(package=package, findings=findings)

    def run_many(self, package_dirs: list[Path]) -> list[PackageResult]:
        return [self.run_package(directory) for directory in package_dirs]
