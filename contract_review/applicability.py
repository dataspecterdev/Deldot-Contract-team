"""Deterministic applicability engine.

Applicability is decided from Project_Metadata.json, not by the model. The
checklist states each rule in plain language and every rule maps onto a metadata
field, so a rule table gives exact, reproducible APPLIES / DOES_NOT_APPLY
decisions and removes a whole class of model error.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .config import APPLIES, DOES_NOT_APPLY
from .models import ApplicabilityDecision

Predicate = Callable[[dict[str, Any]], ApplicabilityDecision]


def _yes(metadata: dict[str, Any], key: str) -> bool:
    return str(metadata.get(key, "")).strip().lower() in {"yes", "true", "y"}


def _always(reason: str) -> Predicate:
    def rule(_: dict[str, Any]) -> ApplicabilityDecision:
        return ApplicabilityDecision(APPLIES, reason)

    return rule


def _conditional(key: str, applies_reason: str, denies_reason: str) -> Predicate:
    def rule(metadata: dict[str, Any]) -> ApplicabilityDecision:
        if _yes(metadata, key):
            return ApplicabilityDecision(APPLIES, applies_reason)
        return ApplicabilityDecision(DOES_NOT_APPLY, denies_reason)

    return rule


def _addenda_rule(metadata: dict[str, Any]) -> ApplicabilityDecision:
    addenda = metadata.get("issued_addenda") or []
    if isinstance(addenda, str):
        addenda = [addenda] if addenda.strip() and addenda.strip().lower() != "none" else []
    if addenda:
        listed = ", ".join(str(a) for a in addenda)
        return ApplicabilityDecision(
            APPLIES, f"Project metadata lists issued addenda ({listed})."
        )
    return ApplicabilityDecision(
        DOES_NOT_APPLY, "Project metadata lists no issued addenda or Q&A for this solicitation."
    )


# Requirement_ID -> rule. Sourced from the Applicability_Rule column of the
# reference checklist.
RULES: dict[str, Predicate] = {
    "CC-01": _conditional(
        "federal_aid",
        "Project metadata marks this a federal-aid contract funded under Title 23, so FHWA-1273 incorporation applies.",
        "Project metadata marks this project as not federal-aid, so FHWA-1273 incorporation does not apply.",
    ),
    "CC-02": _always("DelDOT bid package governed by Section 102.8 proposal-guaranty requirements."),
    "CC-03": _always("DelDOT proposal, so the Section 102.15 non-collusive bidding certification applies."),
    "CC-04": _always("Contract execution package governed by Section 103.5 bond requirements."),
    "CC-05": _always("Successful-bidder execution package governed by Section 103.7."),
    "CC-06": _always("Delaware construction/maintenance contractor context described by the proposal."),
    "CC-07": _always("Delaware public works proposal subject to 29 Del. C. 6967 licensing."),
    "CC-08": _addenda_rule,
    "CC-09": _conditional(
        "buy_america_baba_applicable",
        "Project metadata states Buy America/BABA requirements apply to this federal-aid project.",
        "Project metadata states Buy America/BABA requirements do not apply to this project.",
    ),
    "CC-10": _always("Multiple contract documents are incorporated and may conflict, so DelDOT 105.6 applies."),
    "CC-11": _always("Package includes contract-change / differing-site-condition provisions."),
    "CC-12": _always("Package includes change-notification requirements under DelDOT 104.3."),
    "CC-13": _always("Contract and subcontract performance records are subject to the Right to Audit notice."),
    "CC-14": _conditional(
        "subcontracting_planned",
        "Project metadata indicates subcontractors will be used, so DelDOT 108.1 subletting limits apply.",
        "Project metadata indicates no subcontracting is planned, so the subletting requirement does not apply.",
    ),
    "CC-15": _conditional(
        "claim_event",
        "Project metadata records an unresolved contract-change/claim scenario.",
        "Project metadata records no claim scenario, so the claims procedure is not exercised.",
    ),
    "CC-16": _conditional(
        "delay_event",
        "Project metadata records a delay/time-extension scenario.",
        "Project metadata records no delay scenario, so time-extension review does not apply.",
    ),
    "CC-17": _always("Package includes a liquidated-damages provision or governing schedule."),
    "CC-18": _conditional(
        "changed_work_event",
        "Project metadata records a changed-work pricing scenario.",
        "Project metadata records no changed-work event, so change-pricing review does not apply.",
    ),
}


def decide(requirement_id: str, metadata: dict[str, Any]) -> ApplicabilityDecision:
    """Return the applicability decision for one requirement."""
    rule = RULES.get(requirement_id)
    if rule is None:
        return ApplicabilityDecision(
            APPLIES, "No metadata-based exclusion defined for this requirement."
        )
    return rule(metadata)


def decide_all(metadata: dict[str, Any], requirement_ids: list[str]) -> dict[str, ApplicabilityDecision]:
    return {rid: decide(rid, metadata) for rid in requirement_ids}
