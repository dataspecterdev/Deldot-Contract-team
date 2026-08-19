"""
Applicability determination.

This is deliberately deterministic: the checklist ties applicability to project
facts (federal aid, Buy America, addenda issued, subcontracting, claim, delay,
changed work), so a rule engine decides APPLIES / DOES_NOT_APPLY and the model
is never asked to guess. Over-flagging a non-applicable clause is penalised by
the scoring, so this step matters as much as the analysis itself.

For packages that ship a Project_Metadata.json we use it directly. For documents
a user simply drops in, we infer the same flags from the proposal text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from extract import Package
from requirements import REQUIREMENTS, Requirement

# Metadata gate -> (human label, phrases that indicate the fact is present)
_INFERENCE_HINTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "federal_aid": ("federal aid", ("federal aid", "federal-aid", "fhwa", "title 23")),
    "buy_america_baba_applicable": ("Buy America/BABA", ("buy america", "baba", "domestic content", "domestic-content")),
    "issued_addenda": ("issued addenda", ("addendum", "addenda")),
    "subcontracting_planned": ("subcontracting", ("subcontract", "subletting", "subcontractor")),
    "claim_event": ("claim scenario", ("claim",)),
    "delay_event": ("delay scenario", ("delay", "time extension")),
    "changed_work_event": ("changed work scenario", ("changed work", "change order", "compensation for changes")),
}

_YES = {"yes", "true", "y", "1", "applicable", "applies"}
_NO = {"no", "false", "n", "0", "not applicable", "does not apply", "none"}


@dataclass
class ApplicabilityDecision:
    requirement_id: str
    decision: str  # APPLIES | DOES_NOT_APPLY
    reason: str
    source: str  # metadata | inferred | always


def _truthy(value) -> bool | None:
    """Interpret a metadata value as yes/no. Returns None when unknown."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    text = str(value).strip().lower()
    if not text:
        return False
    if text in _YES:
        return True
    if text in _NO:
        return False
    return None


def _infer_from_text(gate: str, package: Package) -> tuple[bool, str]:
    """Fallback for inserted documents with no Project_Metadata.json."""
    label, phrases = _INFERENCE_HINTS[gate]
    haystack = "\n".join(doc.text for doc in package.documents).lower()

    # "Project summary" style lines, e.g. "Federal aid Yes" / "Buy America/BABA applicable No".
    for phrase in phrases:
        match = re.search(rf"{re.escape(phrase)}[^\n:]{{0,40}}[:\s]+(yes|no)\b", haystack)
        if match:
            stated = match.group(1)
            return stated == "yes", f"Package text states {label}: {stated}."

    if gate == "issued_addenda":
        addendum_docs = [
            doc.file_name for doc in package.documents if "addend" in doc.document_type.lower()
        ]
        if addendum_docs:
            return True, f"Package includes addendum document(s): {', '.join(addendum_docs)}."

    hit = next((p for p in phrases if p in haystack), None)
    if hit:
        return True, f"Package text discusses {label} (matched '{hit}')."
    return False, f"No {label} indication found in the package text or metadata."


def decide(requirement: Requirement, package: Package) -> ApplicabilityDecision:
    """Decide applicability for one requirement against one package."""
    gate = requirement.metadata_gate

    if gate is None:
        return ApplicabilityDecision(
            requirement_id=requirement.id,
            decision="APPLIES",
            reason=f"{requirement.applicability_rule}; this reviewed package is a DelDOT contract package.",
            source="always",
        )

    raw = package.metadata.get(gate)
    resolved = _truthy(raw)

    if resolved is None:
        resolved, reason = _infer_from_text(gate, package)
        source = "inferred"
    else:
        shown = ", ".join(raw) if isinstance(raw, list) and raw else raw
        if isinstance(raw, list) and not raw:
            shown = "none"
        reason = f"Project metadata {gate} = {shown}."
        source = "metadata"

    if resolved:
        return ApplicabilityDecision(
            requirement_id=requirement.id,
            decision="APPLIES",
            reason=f"{reason} Applicability rule: {requirement.applicability_rule}.",
            source=source,
        )

    return ApplicabilityDecision(
        requirement_id=requirement.id,
        decision="DOES_NOT_APPLY",
        reason=f"{reason} Applicability rule not met: {requirement.applicability_rule}.",
        source=source,
    )


def decide_all(package: Package) -> dict[str, ApplicabilityDecision]:
    return {r.id: decide(r, package) for r in REQUIREMENTS}


if __name__ == "__main__":
    import sys
    from extract import load_package

    pkg = load_package(sys.argv[1])
    print(f"{pkg.package_id}")
    for req_id, decision in decide_all(pkg).items():
        print(f"  {req_id}  {decision.decision:<15} [{decision.source}] {decision.reason}")
