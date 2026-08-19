"""CSV output: the submission file and the line-level evidence trace.

Two files are produced:

* ``submission.csv`` - exactly the columns declared in Submission_Schema.csv, in
  that order, one row per package x requirement pair.
* ``evidence_trace.csv`` - the cross-check companion, keyed by the same
  document_id + requirement_id (CC-##). It carries the resolved file, page and
  line numbers, the verbatim quote, the evidence match percent and the knowledge
  base retrieval score so a reviewer can open the PDF and confirm each finding.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .checklist import submission_fields
from .config import FLAG
from .models import ContractPackage, Finding


def _sanitize(text: str) -> str:
    """Normalize non-ASCII characters to their plain-text equivalents."""
    # Em/en dashes to hyphens
    text = text.replace("\u2014", "-").replace("\u2013", "-")
    # Curly quotes to straight
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # Section symbol
    text = text.replace("\u00a7", "Section")
    # Arrows
    text = text.replace("\u2192", "->").replace("\u2190", "<-")
    # Ellipsis
    text = text.replace("\u2026", "...")
    # Bullet
    text = text.replace("\u2022", "-")
    return text

EVIDENCE_TRACE_FIELDS = (
    "document_id",
    "requirement_id",
    "predicted_label",
    "severity",
    "applicability_decision",
    "governing_document",
    "evidence_file",
    "evidence_pages",
    "evidence_line_numbers",
    "evidence_line_ids",
    "evidence_section_heading",
    "draft_evidence_quote",
    "evidence_match_percent",
    "rag_retrieval_score_percent",
    "rag_reference_sources",
    "model_confidence_percent",
    "verification_status",
    "notes",
)


def _sanitize_csv_value(value: str) -> str:
    """Remove newlines/control chars and normalize non-ASCII to plain-text equivalents."""
    # Non-ASCII normalization
    value = _sanitize(value)
    # Control characters
    return value.replace("\n", " ").replace("\r", "").strip()


def _submission_row(finding: Finding) -> dict[str, str]:
    return {
        "document_id": _sanitize_csv_value(finding.document_id),
        "requirement_id": finding.requirement_id,
        "applicability_decision": finding.applicability_decision,
        "applicability_reason": _sanitize_csv_value(finding.applicability_reason),
        "predicted_label": finding.predicted_label,
        "severity": finding.severity,
        "governing_document": _sanitize_csv_value(finding.governing_document),
        "draft_location": _sanitize_csv_value(finding.draft_location),
        "draft_evidence": _sanitize_csv_value(finding.draft_evidence),
        "reference_id": finding.reference_id,
        "reference_location": _sanitize_csv_value(finding.reference_location),
        "reference_evidence": _sanitize_csv_value(finding.reference_evidence),
        "explanation": _sanitize_csv_value(finding.explanation),
        "confidence": f"{finding.confidence:.2f}",
        "recommended_human_action": _sanitize_csv_value(finding.recommended_human_action),
    }


def write_submission(findings: list[Finding], path: Path) -> Path:
    """Write submission.csv using the schema's own field order."""
    fields = list(submission_fields())
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for finding in sorted(findings, key=lambda f: (f.document_id, f.requirement_id)):
            row = _submission_row(finding)
            writer.writerow({field: row.get(field, "") for field in fields})
    return path


def _verification_status(finding: Finding) -> str:
    """How much the citation can be trusted, independent of the model's opinion."""
    if finding.applicability_decision == "DOES_NOT_APPLY":
        return "NOT_APPLICABLE_NO_EVIDENCE_NEEDED"
    if not finding.cited_line_ids:
        return "UNLOCATED_REVIEW_MANUALLY"
    if finding.evidence_match_percent >= 99.0:
        return "VERBATIM_MATCH"
    if finding.evidence_match_percent >= 75.0:
        return "CLOSE_MATCH"
    if finding.evidence_match_percent > 0.0:
        return "WEAK_MATCH_REVIEW"
    return "LINES_CITED_NO_QUOTE"


def write_evidence_trace(
    findings: list[Finding], packages: dict[str, ContractPackage], path: Path
) -> Path:
    """Write the CC-## keyed cross-check file with page and line numbers."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EVIDENCE_TRACE_FIELDS))
        writer.writeheader()

        for finding in sorted(findings, key=lambda f: (f.document_id, f.requirement_id)):
            package = packages.get(finding.document_id)
            index = package.line_index() if package else {}
            lines = [index[lid] for lid in finding.cited_line_ids if lid in index]

            files = sorted({ln.file_name for ln in lines})
            pages = sorted({ln.page for ln in lines})
            numbers = [ln.line_on_page for ln in lines]
            heading = next((ln.heading for ln in lines if ln.heading), "")

            writer.writerow(
                {
                    "document_id": _sanitize_csv_value(finding.document_id),
                    "requirement_id": finding.requirement_id,
                    "predicted_label": finding.predicted_label,
                    "severity": finding.severity,
                    "applicability_decision": finding.applicability_decision,
                    "governing_document": _sanitize_csv_value(finding.governing_document),
                    "evidence_file": "; ".join(files),
                    "evidence_pages": ", ".join(str(p) for p in pages),
                    "evidence_line_numbers": ", ".join(str(n) for n in numbers),
                    # Separated with "; " because the ids themselves contain "|".
                    "evidence_line_ids": "; ".join(finding.cited_line_ids),
                    "evidence_section_heading": _sanitize_csv_value(heading),
                    "draft_evidence_quote": _sanitize_csv_value(finding.draft_evidence),
                    "evidence_match_percent": f"{finding.evidence_match_percent:.1f}",
                    "rag_retrieval_score_percent": f"{finding.retrieval_score_percent:.1f}",
                    "rag_reference_sources": "; ".join(dict.fromkeys(finding.retrieved_sources)),
                    "model_confidence_percent": f"{finding.confidence * 100:.0f}",
                    "verification_status": _verification_status(finding),
                    "notes": _sanitize_csv_value(finding.notes),
                }
            )
    return path


def summarize(findings: list[Finding]) -> str:
    """Short human summary of a run."""
    total = len(findings)
    applies = sum(1 for f in findings if f.applicability_decision == "APPLIES")
    flags = sum(1 for f in findings if f.predicted_label == FLAG)
    located = sum(1 for f in findings if f.cited_line_ids)
    verbatim = sum(1 for f in findings if f.evidence_match_percent >= 99.0)

    by_severity: dict[str, int] = {}
    for finding in findings:
        if finding.predicted_label == FLAG:
            by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1
    severity_text = ", ".join(f"{k}: {v}" for k, v in sorted(by_severity.items())) or "none"

    return (
        f"rows: {total} | applicable: {applies} | flags: {flags} ({severity_text})\n"
        f"evidence located: {located}/{total} | verbatim quotes: {verbatim}/{total}"
    )
