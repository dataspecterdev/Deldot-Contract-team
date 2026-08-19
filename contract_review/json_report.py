"""Structured JSON report: findings with actual line/page/file provenance.

This report is the primary human-readable output. For each finding it shows:
- The actual line number, page, and file name in the contract
- The verbatim contract text at those locations
- The challenge_reference_rule criteria it was judged against
- The decision, severity, confidence, and explanation

This is a standalone document that does NOT depend on the CSV submission or the
evidence trace — it is designed to be read by project managers and reviewers who
need to see exactly what the contract says and why it was flagged.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .checklist import requirement_map
from .config import FLAG, NO_FLAG
from .models import ContractPackage, Finding


def _build_contract_evidence(finding: Finding, package: ContractPackage | None) -> list[dict[str, Any]]:
    """Build the list of exact contract locations with verbatim text.

    Each entry has:
      - file_name: the PDF file where the text lives
      - page: 1-based page number
      - line_number: 1-based line number on that page
      - line_id: the full provenance id (file|page|line)
      - text: the verbatim line content from the contract
      - section_heading: the heading context for that line
    """
    if not package or not finding.cited_line_ids:
        return []

    index = package.line_index()
    evidence_lines: list[dict[str, Any]] = []

    for line_id in finding.cited_line_ids:
        line = index.get(line_id)
        if line is None:
            continue
        evidence_lines.append({
            "file_name": line.file_name,
            "page": line.page,
            "line_number": line.line_on_page,
            "line_id": line.line_id,
            "text": line.text,
            "section_heading": line.heading,
        })

    return evidence_lines


def _build_finding_entry(
    finding: Finding,
    package: ContractPackage | None,
    req_map: dict[str, Any],
) -> dict[str, Any]:
    """Build one finding entry for the JSON report."""
    requirement = req_map.get(finding.requirement_id)

    # The criteria: straight from Reference_Checklist challenge_reference_rule
    criteria = {
        "requirement_id": finding.requirement_id,
        "requirement_name": requirement.name if requirement else "",
        "reference_source": requirement.reference_source if requirement else "",
        "section": requirement.section if requirement else "",
        "challenge_reference_rule": requirement.challenge_reference_rule if requirement else "",
        "review_expectation": requirement.review_expectation if requirement else "",
        "severity_guidance": requirement.severity_guidance if requirement else "",
    }

    # The actual contract evidence with real line numbers/pages/files
    contract_evidence = _build_contract_evidence(finding, package)

    return {
        "requirement_id": finding.requirement_id,
        "document_id": finding.document_id,
        "decision": {
            "applicability": finding.applicability_decision,
            "applicability_reason": finding.applicability_reason,
            "predicted_label": finding.predicted_label,
            "severity": finding.severity,
            "confidence": finding.confidence,
            "explanation": finding.explanation,
            "recommended_action": finding.recommended_human_action,
        },
        "criteria": criteria,
        "contract_evidence": {
            "governing_document": finding.governing_document,
            "draft_location": finding.draft_location,
            "draft_quote": finding.draft_evidence,
            "evidence_match_percent": finding.evidence_match_percent,
            "lines": contract_evidence,
        },
        "confidence_factors": {
            "model_confidence": finding.confidence,
            "retrieval_score_percent": finding.retrieval_score_percent,
            "evidence_match_percent": finding.evidence_match_percent,
            "sources_used_for_confidence": finding.retrieved_sources,
        },
    }


def build_json_report(
    findings: list[Finding],
    packages: dict[str, ContractPackage],
) -> dict[str, Any]:
    """Build the full JSON report structure."""
    req_map = requirement_map()

    # Group findings by package
    by_package: dict[str, list[Finding]] = {}
    for finding in findings:
        by_package.setdefault(finding.document_id, []).append(finding)

    package_reports: list[dict[str, Any]] = []
    for package_id, pkg_findings in sorted(by_package.items()):
        package = packages.get(package_id)
        pkg_findings.sort(key=lambda f: f.requirement_id)

        flags = [f for f in pkg_findings if f.predicted_label == FLAG]
        compliant = [f for f in pkg_findings if f.predicted_label == NO_FLAG]

        package_reports.append({
            "package_id": package_id,
            "summary": {
                "total_requirements_checked": len(pkg_findings),
                "flags": len(flags),
                "compliant": len(compliant),
                "flag_ids": [f.requirement_id for f in flags],
            },
            "findings": [
                _build_finding_entry(f, package, req_map) for f in pkg_findings
            ],
        })

    total_flags = sum(1 for f in findings if f.predicted_label == FLAG)
    total_findings = len(findings)

    return {
        "report_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_type": "contract_clause_risk_flagging",
            "scoring_authority": "Reference_Checklist.csv — Challenge_Reference_Rule column",
            "sources_role": "Confidence scoring only (not used as validation criteria)",
            "description": (
                "Each finding shows the exact contract text (file, page, line number) "
                "and the challenge_reference_rule it was judged against. Sources from the "
                "knowledge base are used ONLY to compute a retrieval confidence factor."
            ),
        },
        "summary": {
            "total_packages": len(package_reports),
            "total_requirements_checked": total_findings,
            "total_flags": total_flags,
            "total_compliant": total_findings - total_flags,
        },
        "packages": package_reports,
    }


def write_json_report(
    findings: list[Finding],
    packages: dict[str, ContractPackage],
    path: Path,
) -> Path:
    """Write the structured JSON report to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    report = build_json_report(findings, packages)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    return path
