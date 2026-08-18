"""Per-requirement "skill" prompts.

Each of the 18 requirements gets its own instruction block built from the
reference checklist: the review expectation, the challenge reference rule, the
severity guidance and the evidence obligation. The prompts are zero-shot - the
checklist is the scoring authority, so its own wording is the instruction.

The model must cite ``line_id`` tags copied from the numbered package text. That
requirement is what makes every finding traceable back to a page and line.
"""
from __future__ import annotations

import json
from typing import Any

from .models import Requirement
from .precedence import GoverningDocument

SYSTEM_PROMPT = """\
You are a contract reviewer supporting Delaware DOT construction contract \
administration. You compare a reviewed contract package against one reference \
requirement and produce a decision-support finding for human review.

Operating rules:
1. The reference requirement is the scoring authority. Compare the package text
   against it and nothing else.
2. Judge substance, not wording. Reordered, paraphrased, restructured or
   recapitalized text that preserves the same obligation, percentage, deadline
   and scope is NOT a deviation. Report those as NO_FLAG / Info.
3. Flag only a material deviation you can prove by quoting package words that
   conflict with the reference.
4. Respect precedence. If a later Addendum explicitly revises the provision, the
   Addendum text governs and the superseded earlier text is not a finding.
5. Ground every statement in evidence. Quote the reviewed package verbatim and
   cite the bracketed line ids exactly as they appear in the numbered text. Never
   invent a line id, a quote or a reference.
6. You produce decision support, not a legal conclusion. Recommend human review.

## HOW TO DECIDE FLAG vs NO_FLAG

Contract packages summarize. A clause that carries the requirement forward by
pointing at the governing reference instead of repeating its numbers is
COMPLIANT - incorporation by reference preserves the obligation.

Answer NO_FLAG / Info when:
- The clause restates the requirement in different words, order or capitalization.
- The clause defers to the reference rather than repeating its figures, for
  example "within the reference period", "the reference conditions", "within the
  stated period", "required approval/limits apply", "the priority sequence listed
  in the applicable contract documents", "the reference timing stated in the
  applicable contract documents", "subject to the referenced surety conditions".
  A missing number is NOT an omission when the clause defers to the reference and
  contradicts nothing.
- A governing Addendum supplies text that satisfies the reference. The answer is
  then NO_FLAG / Info even if the superseded earlier text conflicted, and
  governing_document is the Addendum.
- The clause is brief, general or high level but consistent with the reference.

Answer FLAG only when the package affirmatively conflicts with the reference:
- A figure, percentage, deadline or duration differs (10% changed to 5%;
  7 calendar days changed to 30; three years shortened to one; 50%
  self-performance raised to 80%).
- A required element is negated or made optional: "not required", "optional",
  "encouraged but optional", "need not", "may be disregarded", "may begin before".
- Scope is narrowed, for example audit limited to "only prime-contractor records".
- A mandatory protection or sequence is bypassed: oral direction that
  "immediately modifies scope, price, or time"; an extension granted
  automatically for any delay; a fixed markup replacing the pricing sequence; a
  flat daily rate applied "regardless of contract value or governing schedule".
- A requirement the metadata marks applicable is denied, for example a clause
  stating Buy America/BABA does not apply.
- A form that must be physically incorporated appears only as a reference.

Decisive test: before you FLAG, quote the exact package words that conflict. If
your reason is that the clause is vague, generic, summary-level, a placeholder,
non-operative, or lacks specifics, that is NOT a deviation - answer NO_FLAG.

## STAY INSIDE THIS REQUIREMENT

You are reviewing ONE requirement. Contract packages place many provisions side
by side, each answering a different requirement.

- Judge only the clause whose subject matter belongs to this requirement, usually
  the clause under the heading that matches the requirement name.
- A deviation in a neighbouring clause belongs to that clause's own requirement
  and is reviewed separately. Do not import it here, even when it appears in the
  same document a few lines away.
- If the clause for this requirement is compliant, answer NO_FLAG even though
  another provision nearby is defective.
- Report exactly one decision about one subject: this requirement.

Reply with a single JSON object and no other text."""

_OUTPUT_CONTRACT = """\
Return exactly this JSON shape:

{
  "predicted_label": "FLAG" | "NO_FLAG",
  "severity": "Critical" | "High" | "Medium" | "Low" | "Info",
  "cited_line_ids": ["<line id copied verbatim from the numbered text>", "..."],
  "draft_location": "<file name, page and section/heading of the analyzed text>",
  "draft_evidence": "<verbatim quote from the reviewed package>",
  "reference_location": "<reference section or checklist location relied on>",
  "reference_evidence": "<concise statement of the reference requirement>",
  "explanation": "<why the text is material, benign, superseded or absent>",
  "confidence": <number between 0.00 and 1.00>,
  "recommended_human_action": "<review/confirm/no action - never a legal conclusion>"
}

Field rules:
- predicted_label is FLAG only for a material deviation from the reference.
- severity must be Info when predicted_label is NO_FLAG.
- severity should follow the challenge severity guidance for this requirement
  when predicted_label is FLAG.
- cited_line_ids must be copied character-for-character from the [ ... ] tags in
  the numbered package text, and must be the lines your evidence comes from.
- draft_evidence must be a verbatim substring of those cited lines.
- If the requirement is satisfied, still cite the lines that show compliance.
- If the required text is absent from the whole package, say so in explanation,
  set draft_evidence to the closest related text you did find (or "" if nothing
  is related), and cite the lines you checked."""


def _severity_block(requirement: Requirement) -> str:
    return (
        f"Challenge severity for this requirement when flagged: {requirement.severity_guidance}.\n"
        f"If you FLAG, report severity exactly as {requirement.severity_guidance}.\n"
        "If you do not flag, report severity Info. Use Info for an equivalent or benign "
        "wording difference and for a superseded provision the governing document corrects."
    )


def _precedence_block(governing: GoverningDocument) -> str:
    lines = [f"Governing document after precedence resolution: {governing.file_name}", governing.reason]
    revision = governing.superseding_revision
    if revision:
        lines.append(
            f"{revision.document} carries replacement text for '{revision.topic}' at {revision.location}."
        )
        if revision.replacement_text:
            lines.append(f"Replacement text: {revision.replacement_text}")
        lines.append(
            "Evaluate the reference requirement against this replacement text ONLY. The "
            "earlier package text on this provision has been superseded and must not be "
            "flagged. If the replacement text satisfies the reference, answer NO_FLAG with "
            "severity Info, set governing_document to this Addendum, quote the Addendum "
            "replacement text as your evidence, and explain that the Addendum corrects the "
            "earlier provision. Only FLAG if the Addendum replacement text itself conflicts "
            "with the reference."
        )
    else:
        lines.append(
            "No Addendum revises this provision, so evaluate the package text under the "
            "DelDOT 105.6 order of precedence: General Description > General Notices > Plans "
            "> Special Provisions > Standard Construction Details > Standard Specifications "
            "> Electronic Design Data Files."
        )
    return "\n".join(lines)


def _reference_block(requirement: Requirement) -> str:
    """Build the reference block using ONLY the Reference_Checklist data.

    The challenge_reference_rule is the sole scoring authority. No external
    Sources or KB excerpts are included — those are used only for confidence
    scoring outside the model context.
    """
    parts = [
        f"Requirement {requirement.requirement_id} - {requirement.name}",
        f"Reference source: {requirement.reference_source}",
        f"Reference section: {requirement.section}",
        f"Applicability rule: {requirement.applicability_rule}",
        f"Review expectation: {requirement.review_expectation}",
        "",
        "=== CHALLENGE REFERENCE RULE (SOLE SCORING AUTHORITY) ===",
        requirement.challenge_reference_rule,
        "=== END CHALLENGE REFERENCE RULE ===",
        "",
        f"Evidence required: {requirement.evidence_required}",
        "",
        "You MUST judge the contract text against the Challenge Reference Rule above",
        "and ONLY the Challenge Reference Rule. No other external reference material",
        "is provided or should be inferred. The rule above is complete and authoritative.",
    ]
    return "\n".join(parts)


def _metadata_block(metadata: dict[str, Any]) -> str:
    keys = (
        "package_id",
        "project_title",
        "federal_aid",
        "buy_america_baba_applicable",
        "assumed_contract_value",
        "issued_addenda",
        "subcontracting_planned",
        "claim_event",
        "delay_event",
        "changed_work_event",
    )
    trimmed = {k: metadata[k] for k in keys if k in metadata}
    return json.dumps(trimmed, indent=2)


def build_user_prompt(
    requirement: Requirement,
    package_id: str,
    metadata: dict[str, Any],
    governing: GoverningDocument,
    numbered_package_text: str,
    applicability_reason: str,
) -> str:
    """Assemble the full analysis prompt for one package x requirement pair.

    The challenge_reference_rule from Reference_Checklist.csv is the sole
    scoring authority. No external Sources or KB excerpts are sent to the model.
    """
    return f"""\
## REFERENCE REQUIREMENT
{_reference_block(requirement)}

## SEVERITY GUIDANCE
{_severity_block(requirement)}

## PROJECT METADATA
{_metadata_block(metadata)}

Applicability was already determined from this metadata: APPLIES - {applicability_reason}

## PRECEDENCE
{_precedence_block(governing)}

## REVIEWED CONTRACT PACKAGE ({package_id})
Every line is prefixed with its line id in square brackets. Copy those ids
verbatim into cited_line_ids.

{numbered_package_text}

## TASK
Decide whether package {package_id} deviates materially from requirement
{requirement.requirement_id} ({requirement.name}), after applying precedence.

Judge ONLY against the Challenge Reference Rule provided above. That rule is
complete and authoritative — do not infer additional criteria from elsewhere.

{_OUTPUT_CONTRACT}"""
