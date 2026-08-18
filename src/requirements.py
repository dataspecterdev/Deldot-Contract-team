"""
The 18 reference requirements, as instruction sets ("skills").

Each entry carries what the checklist says (section, applicability rule, review
expectation, challenge reference rule, default severity) plus the retrieval
query used to pull the matching reference text out of the Bedrock Knowledge
Base. The wording of the rules is taken from References/Reference_Checklist.csv
so the scoring authority stays the checklist, not our paraphrase.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Requirement:
    id: str
    tier: str
    name: str
    reference_source: str
    section: str
    applicability_rule: str
    review_expectation: str
    challenge_reference_rule: str
    default_severity: str
    kb_query: str
    # Metadata flag that gates applicability. None means "always applies".
    metadata_gate: str | None = None
    # Extra phrases that help locate the clause inside the reviewed package.
    draft_anchors: tuple[str, ...] = field(default_factory=tuple)


REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        id="CC-01",
        tier="Baseline",
        name="FHWA-1273 physical incorporation",
        reference_source="FHWA-1273 + federal-aid proposal",
        section="FHWA-1273 I.1",
        applicability_rule="Federal-aid construction contract funded under Title 23, subject to stated exceptions",
        review_expectation="Flag a covered contract that only references FHWA-1273 instead of physically including the form.",
        challenge_reference_rule=(
            "If federal-aid metadata makes FHWA-1273 applicable, the form must be physically included in the "
            "package; a reference-only statement is insufficient for challenge scoring."
        ),
        default_severity="Critical",
        kb_query="Form FHWA-1273 must be physically incorporated in each construction contract funded under title 23",
        metadata_gate="federal_aid",
        draft_anchors=("FHWA-1273", "federal requirements", "incorporated by reference"),
    ),
    Requirement(
        id="CC-02",
        tier="Baseline",
        name="Proposal guaranty / bid bond",
        reference_source="DelDOT Standard Specifications + proposal",
        section="DelDOT 102.8",
        applicability_rule="DelDOT bid where Section 102.8 governs",
        review_expectation="Verify acceptable proposal guaranty is provided and equals 10% of total bid price.",
        challenge_reference_rule="Where applicable, proposal guaranty must equal 10% of total bid price.",
        default_severity="High",
        kb_query="proposal guaranty equal to 10 percent of the total bid price bid bond",
        draft_anchors=("proposal guaranty", "bid bond", "bid security"),
    ),
    Requirement(
        id="CC-03",
        tier="Baseline",
        name="Non-collusive bidding certification",
        reference_source="DelDOT Standard Specifications + General Notices",
        section="DelDOT 102.15",
        applicability_rule="DelDOT proposal",
        review_expectation="Verify the signed non-collusive bidding certification is included where required.",
        challenge_reference_rule=(
            "Required non-collusive bidding certification must be present; harmless formatting/capitalization "
            "changes are not deviations."
        ),
        default_severity="High",
        kb_query="signed non-collusive bidding certification form provided in the bid proposal",
        draft_anchors=("non-collusive", "non-collusion", "certification"),
    ),
    Requirement(
        id="CC-04",
        tier="Baseline",
        name="Performance and payment bonds",
        reference_source="DelDOT Standard Specifications",
        section="DelDOT 103.5",
        applicability_rule="Contract execution where Section 103.5 governs",
        review_expectation="Verify performance/payment bond coverage and surety conditions match the reference requirement.",
        challenge_reference_rule=(
            "For challenge scoring, required performance and payment bond coverage is 100% of the contract price, "
            "subject to the referenced surety conditions. Resolve any later governing Addendum before flagging "
            "earlier text."
        ),
        default_severity="High",
        kb_query="surety bond at time of contract execution sum equal to 100 percent of the contract price",
        draft_anchors=("performance and payment bonds", "bond coverage", "surety"),
    ),
    Requirement(
        id="CC-05",
        tier="Baseline",
        name="Contract execution and proof of insurance",
        reference_source="DelDOT Standard Specifications",
        section="DelDOT 103.7",
        applicability_rule="Successful bidder / contract execution",
        review_expectation="Verify execution timing and proof-of-insurance requirements are not omitted or materially altered.",
        challenge_reference_rule=(
            "For challenge scoring, required execution documents must be returned within 20 calendar days after "
            "notice of award, and acceptable proof/certificate of insurance must be furnished before contract "
            "execution. A later governing Addendum may validly revise a named provision."
        ),
        default_severity="High",
        kb_query="return signed contract and bonds within 20 calendar days after notice of award certificate of insurance",
        draft_anchors=("contract execution", "proof of insurance", "certificate of insurance"),
    ),
    Requirement(
        id="CC-06",
        tier="Baseline",
        name="Contractor Registration Act notice",
        reference_source="Delaware Contractor Registration Act + DelDOT proposal",
        section="19 Del. C. § 3604",
        applicability_rule="Delaware construction/maintenance contractor context described by the proposal",
        review_expectation="Verify the draft does not contradict the proposal requirement that contractors register before performing covered work.",
        challenge_reference_rule=(
            "For covered Delaware construction/maintenance work, the draft must not allow required contractor "
            "registration to occur only after work begins."
        ),
        default_severity="High",
        kb_query="contractor must register before performing construction services or maintenance",
        draft_anchors=("contractor registration", "register"),
    ),
    Requirement(
        id="CC-07",
        tier="Baseline",
        name="Delaware business / subcontractor licenses",
        reference_source="Delaware public works licensing statute + DelDOT proposal",
        section="29 Del. C. § 6967",
        applicability_rule="Delaware public works proposal",
        review_expectation="Verify required contractor business-license evidence and stated subcontractor-license submission timing are preserved.",
        challenge_reference_rule=(
            "For challenge scoring, a current prime contractor occupational/business license must accompany the "
            "proposal. Subcontractor/independent-contractor license copies must be provided within 30 days after "
            "entering the public works contract, or within 10 days after a subcontractor/independent contractor is "
            "hired more than 20 days after contract entry."
        ),
        default_severity="High",
        kb_query="occupational and business license public works contract within 30 days subcontractor 10 days",
        draft_anchors=("license", "business license", "subcontractor license"),
    ),
    Requirement(
        id="CC-08",
        tier="Baseline",
        name="Addenda and Q&A currency",
        reference_source="DelDOT proposal + solicitation record",
        section="Attachments / Addenda",
        applicability_rule="Project has posted addenda and/or Q&A",
        review_expectation="Verify the reviewed package acknowledges the current addenda/Q&A and does not treat the original proposal as self-updating.",
        challenge_reference_rule=(
            "Use the latest provided Addendum/package version. A draft that ignores a later issued Addendum is a finding."
        ),
        default_severity="High",
        kb_query="acknowledge current addenda and Q and A latest addendum version",
        metadata_gate="issued_addenda",
        draft_anchors=("addenda", "addendum", "acknowledgment"),
    ),
    Requirement(
        id="CC-09",
        tier="Baseline",
        name="Buy America / BABA applicability",
        reference_source="Federal-aid DelDOT proposal General Notices",
        section="Buy America Requirement",
        applicability_rule="Federal-aid project whose proposal states Buy America/BABA requirements apply",
        review_expectation="Verify Buy America/BABA applicability and certification language are not omitted or contradicted for a project explicitly marked as subject to the requirement.",
        challenge_reference_rule=(
            "Apply Buy America/BABA only when project metadata/reference indicates it applies; if applicable, a "
            "clause saying it does not apply is a finding."
        ),
        default_severity="Critical",
        kb_query="Buy America BABA domestic content requirements applicability certification",
        metadata_gate="buy_america_baba_applicable",
        draft_anchors=("buy america", "baba", "domestic-content", "domestic content"),
    ),
    Requirement(
        id="CC-10",
        tier="Baseline",
        name="Coordination / order of precedence",
        reference_source="DelDOT Standard Specifications",
        section="DelDOT 105.6",
        applicability_rule="Multiple contract documents are incorporated and may conflict",
        review_expectation="Verify contract documents are treated as complementary and conflict resolution follows the stated order of precedence.",
        challenge_reference_rule=(
            "Treat contract documents as complementary and resolve conflicts using DelDOT 105.6. General Description "
            "> General Notices > Plans > Special Provisions > Standard Construction Details > Standard Specifications "
            "> Electronic Design Data Files. A later Addendum that explicitly revises a named provision governs that "
            "revised provision for this challenge."
        ),
        default_severity="High",
        kb_query="coordination of contract documents order of precedence complementary General Notices Plans Special Provisions",
        draft_anchors=("coordination", "order of precedence", "complementary"),
    ),
    Requirement(
        id="CC-11",
        tier="Baseline",
        name="Contract changes must follow written process",
        reference_source="DelDOT Standard Specifications + General Notices",
        section="DelDOT 104.2",
        applicability_rule="Contract package includes contract-change / differing-site-condition provisions",
        review_expectation="Verify the draft does not authorize material contract changes solely through oral promises or bypass required written change mechanisms.",
        challenge_reference_rule=(
            "Material contract changes must follow the documented written process; oral direction alone must not "
            "immediately alter scope/price/time."
        ),
        default_severity="High",
        kb_query="contract not modified by any oral promise unless reduced to writing proceed only after written direction",
        draft_anchors=("contract changes", "oral direction", "written process"),
    ),
    Requirement(
        id="CC-12",
        tier="Baseline",
        name="Notification of contract changes",
        reference_source="DelDOT Standard Specifications",
        section="DelDOT 104.3",
        applicability_rule="Contract package includes change-notification requirements",
        review_expectation="Verify required notification steps and key deadlines for alleged changes are not omitted or materially altered.",
        challenge_reference_rule=(
            "For challenge scoring, an alleged contract change requires immediate oral and written notice, affected "
            "work proceeds only after written direction, and the required written follow-up information is due within "
            "7 calendar days of the initial notice unless a later governing document validly revises that provision."
        ),
        default_severity="High",
        kb_query="notification of contract changes within 7 calendar days of initial notification written information",
        draft_anchors=("change notification", "notification of contract changes", "follow-up"),
    ),
    Requirement(
        id="CC-13",
        tier="Baseline",
        name="Right to audit and record retention",
        reference_source="DelDOT proposal General Notices",
        section="Right to Audit",
        applicability_rule="Contract/subcontract records related to performance",
        review_expectation="Verify audit rights are preserved and the stated records-retention period is not shortened.",
        challenge_reference_rule=(
            "For challenge scoring, relevant prime-contractor and subcontractor records supporting contract "
            "performance must be available for audit and retained for three years after final payment."
        ),
        default_severity="Medium",
        kb_query="right to audit prime contractor and subcontractor records retained three years after final payment",
        draft_anchors=("right to audit", "audit records", "record retention", "retained"),
    ),
    Requirement(
        id="CC-14",
        tier="Advanced",
        name="Contract subletting",
        reference_source="DelDOT Standard Specifications",
        section="DelDOT 108.1",
        applicability_rule="Contract uses subcontractors",
        review_expectation="Verify self-performance, approval, licensing, and flow-down requirements are not materially weakened.",
        challenge_reference_rule=(
            "When subcontracting applies, use DelDOT Section 108.1 as the challenge baseline: the prime performs no "
            "less than 50% of the total original contract price with its own organization, excluding designated "
            "specialty items as provided by the reference; subletting requires written consent and does not relieve "
            "the prime of contract responsibility."
        ),
        default_severity="High",
        kb_query="contract subletting perform no less than 50 percent with own organization written consent specialty items",
        metadata_gate="subcontracting_planned",
        draft_anchors=("subcontracting", "subletting", "subcontractor"),
    ),
    Requirement(
        id="CC-15",
        tier="Advanced",
        name="Claims procedure",
        reference_source="DelDOT Standard Specifications",
        section="DelDOT 105.15",
        applicability_rule="Unresolved contract-change/claim scenario",
        review_expectation="Verify claim prerequisites, notice timing, and supporting-document expectations are represented consistently with the reference.",
        challenge_reference_rule=(
            "When a claim scenario applies, the challenge benchmark requires the reference notice/documentation "
            "process and a written claim within 30 calendar days after completion of the work described in the notice "
            "of intent, together with applicable Section 104.3 notice compliance. Harmless paraphrases are not findings."
        ),
        default_severity="Medium",
        kb_query="claims resolution written claim within 30 calendar days after completing work notice of intent",
        metadata_gate="claim_event",
        draft_anchors=("claim", "claims procedure", "notice of intent"),
    ),
    Requirement(
        id="CC-16",
        tier="Advanced",
        name="Extensions of contract time",
        reference_source="DelDOT Standard Specifications + project metadata",
        section="DelDOT 108.7",
        applicability_rule="Delay/time-extension scenario",
        review_expectation="Verify time-extension language retains timely notice and excusable-delay/critical-path requirements.",
        challenge_reference_rule=(
            "When a delay scenario applies, an extension requires an excusable delay, a timely written request/notice "
            "under the reference process, and an effect on the critical path/substantial-completion time. Delay does "
            "not create an automatic time extension."
        ),
        default_severity="Medium",
        kb_query="extensions of contract time excusable delay critical path timely written request waiver",
        metadata_gate="delay_event",
        draft_anchors=("time extension", "extensions of contract time", "delay"),
    ),
    Requirement(
        id="CC-17",
        tier="Advanced",
        name="Liquidated damages schedule / rate logic",
        reference_source="DelDOT Standard Specifications",
        section="DelDOT 108.9",
        applicability_rule="Contract package includes a liquidated-damages provision or governing schedule",
        review_expectation="Verify liquidated-damages rate logic is tied to the applicable reference schedule rather than an unsupported arbitrary amount.",
        challenge_reference_rule=(
            "Use the governing Section 108.9 liquidated-damages schedule/rate logic for the applicable contract value "
            "and time basis after resolving Addenda and precedence. A universal invented flat daily rate is a "
            "material deviation."
        ),
        default_severity="Medium",
        kb_query="schedule of liquidated damages awarded contract value daily charge working day calendar day",
        draft_anchors=("liquidated damages", "daily rate", "per day"),
    ),
    Requirement(
        id="CC-18",
        tier="Advanced",
        name="Compensation for changes",
        reference_source="DelDOT Standard Specifications",
        section="DelDOT 109.4",
        applicability_rule="Changed-work pricing scenario",
        review_expectation="Verify compensation-for-change language preserves the reference pricing-method sequence and timely-notice dependency.",
        challenge_reference_rule=(
            "When changed work applies, the challenge benchmark pricing sequence is: applicable contract unit prices "
            "first, then negotiated prices, then force-account pricing if agreement is not reached, subject to the "
            "reference notice/documentation process. A fixed arbitrary markup that replaces this workflow is a "
            "material deviation."
        ),
        default_severity="Medium",
        kb_query="compensation for changes unit prices negotiated prices force account pricing sequence",
        metadata_gate="changed_work_event",
        draft_anchors=("compensation for changes", "changed work", "markup", "pricing"),
    ),
)

BY_ID: dict[str, Requirement] = {r.id: r for r in REQUIREMENTS}


def get(requirement_id: str) -> Requirement:
    try:
        return BY_ID[requirement_id]
    except KeyError as exc:
        raise KeyError(f"Unknown requirement id: {requirement_id}") from exc
