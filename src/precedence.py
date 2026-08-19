"""
Cross-document precedence and Addendum handling.

Two things decide which document controls a provision:

1. A later Addendum that explicitly revises a named provision governs that
   provision (challenge rule for CC-04, CC-05, CC-10, CC-12, ...).
2. Otherwise DelDOT 105.6 order of precedence applies:
   General Description > General Notices > Plans > Special Provisions >
   Standard Construction Details > Standard Specifications > Electronic Design
   Data Files.

We resolve this deterministically so the model is told which document is
governing instead of having to work it out - that is where precedence questions
are usually lost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from extract import Document, Package, TextLine
from requirements import Requirement

# DelDOT 105.6 order: lower rank wins a conflict.
_PRECEDENCE_ORDER: tuple[tuple[str, ...], ...] = (
    ("general description",),
    ("proposal", "general notices", "general notice"),
    ("plan",),
    ("special provision",),
    ("standard construction detail",),
    ("standard specification", "general conditions"),
    ("electronic design data",),
)

_REVISION_MARKERS = (
    "revision to",
    "is hereby revised",
    "is revised",
    "hereby replaced",
    "is replaced",
    "replacement text",
    "delete and replace",
    "is deleted",
    "amended to read",
)

_NO_CHANGE_MARKERS = (
    "makes no change",
    "no change to the provisions",
    "no changes to the provisions",
)

_ADDENDUM_SEQUENCE = re.compile(r"addendum[_\s]*(?:no\.?\s*)?([a-z0-9]+)", re.IGNORECASE)

# Words that carry no signal when matching an addendum revision to a requirement.
_STOPWORDS = {
    "and",
    "or",
    "the",
    "of",
    "to",
    "for",
    "a",
    "an",
    "must",
    "logic",
    "notice",
    "schedule",
    "process",
    "follow",
    "written",
}


@dataclass
class Revision:
    """An Addendum provision that replaces earlier text."""

    document: Document
    topic: str
    lines: list[TextLine]
    order: int

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)

    @property
    def citation(self) -> str:
        if not self.lines:
            return self.document.file_name
        first, last = self.lines[0], self.lines[-1]
        span = (
            f"line {first.line_on_page}"
            if first.line_on_page == last.line_on_page
            else f"lines {first.line_on_page}-{last.line_on_page}"
        )
        return f"{self.document.file_name} p.{first.page} {span} ({self.topic})"


@dataclass
class GoverningDocument:
    file_name: str
    document_type: str
    basis: str  # "addendum-revision" | "105.6-precedence" | "only-source"
    explanation: str
    revision: Revision | None = None


def _addendum_order(document: Document) -> int:
    """Sort key for addenda: A/1 before B/2 before C/3."""
    match = _ADDENDUM_SEQUENCE.search(f"{document.document_type} {document.file_name}")
    if not match:
        return 0
    token = match.group(1).upper()
    if token.isdigit():
        return int(token)
    if len(token) == 1 and token.isalpha():
        return ord(token) - ord("A") + 1
    return 0


def _precedence_rank(document: Document) -> int:
    label = f"{document.document_type} {document.file_name}".lower()
    for rank, keywords in enumerate(_PRECEDENCE_ORDER):
        if any(keyword in label for keyword in keywords):
            return rank
    return len(_PRECEDENCE_ORDER)


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _is_addendum(document: Document) -> bool:
    return "addend" in f"{document.document_type} {document.file_name}".lower()


def topical_strength(requirement: Requirement, document: Document) -> float:
    """
    How specifically a document addresses a requirement.

    Package documents label each provision with a heading close to the checklist
    requirement name, so heading agreement is the strongest signal. Anchor
    phrases in the body are secondary. Generic shared words are ignored on
    purpose - "contract" appearing everywhere must not imply relevance.
    """
    target = _tokens(requirement.name)
    if not target:
        return 0.0

    best_heading = 0.0
    for line in document.lines:
        heading_tokens = _tokens(line.heading)
        if not heading_tokens:
            continue
        best_heading = max(best_heading, len(target & heading_tokens) / len(target))

    body = document.text.lower()
    anchor_hits = sum(1 for anchor in requirement.draft_anchors if anchor.lower() in body)

    # A heading match is worth far more than a stray body mention.
    score = 2.0 * best_heading + 0.25 * min(anchor_hits, 3)
    return round(score, 3)


def find_revisions(package: Package) -> list[Revision]:
    """Collect every explicit revision carried by the package's addenda."""
    revisions: list[Revision] = []

    for document in package.documents:
        if not _is_addendum(document):
            continue

        body = document.text.lower()
        if any(marker in body for marker in _NO_CHANGE_MARKERS):
            continue

        order = _addendum_order(document)
        topic: str | None = None
        collected: list[TextLine] = []

        for line in document.lines:
            lowered = line.text.lower()

            revision_start = next((m for m in _REVISION_MARKERS if m in lowered), None)
            if revision_start and "replacement text" not in lowered:
                if topic and collected:
                    revisions.append(Revision(document, topic, collected, order))
                    collected = []
                topic = re.sub(
                    r"^\s*(revision to|revised)\s*:?\s*", "", line.text, flags=re.IGNORECASE
                ).strip(" .:-")
                continue

            if topic and "replacement text" in lowered:
                continue

            # Skip boilerplate headers/footers.
            if topic and (
                "sample contract document" in lowered
                or "sample material" in lowered
                or "for evaluation use only" in lowered
                or lowered.startswith("addendum")
                or line.text.strip() == document.document_type
            ):
                continue

            if topic:
                collected.append(line)

        if topic and collected:
            revisions.append(Revision(document, topic, collected, order))

    return revisions


def _revision_score(requirement: Requirement, revision: Revision) -> float:
    """How strongly an Addendum revision targets a given requirement."""
    target = _tokens(requirement.name)
    topic_tokens = _tokens(revision.topic)
    if not target or not topic_tokens:
        return 0.0

    # Jaccard, so a revision topic carrying extra concepts (e.g. "notification")
    # does not score full marks against a broader requirement name.
    overlap = len(target & topic_tokens) / len(target | topic_tokens)

    haystack = f"{revision.topic} {revision.text}".lower()
    anchor_hits = sum(1 for anchor in requirement.draft_anchors if anchor.lower() in haystack)
    return overlap + 0.1 * min(anchor_hits, 2)


def assign_revisions(
    requirements: tuple[Requirement, ...] | list[Requirement], revisions: list[Revision]
) -> dict[str, Revision]:
    """
    Assign each revision to the single requirement it best matches.

    Assigning revision -> requirement (rather than requirement -> revision) stops
    a broader requirement from claiming an Addendum that plainly targets a more
    specific one, e.g. CC-11 "Contract changes" vs CC-12 "Notification of
    contract changes".
    """
    assigned: dict[str, Revision] = {}
    for revision in revisions:
        scored = sorted(
            ((_revision_score(req, revision), req.id) for req in requirements), reverse=True
        )
        if not scored or scored[0][0] < 0.4:
            continue
        best_score, best_id = scored[0]
        existing = assigned.get(best_id)
        # Later addendum wins if two revisions target the same requirement.
        if existing is None or revision.order >= existing.order:
            assigned[best_id] = revision
    return assigned


def match_revision(requirement: Requirement, revisions: list[Revision]) -> Revision | None:
    """Pick the Addendum revision that targets this requirement, if any."""
    from requirements import REQUIREMENTS

    return assign_revisions(REQUIREMENTS, revisions).get(requirement.id)


def resolve(requirement: Requirement, package: Package, revisions: list[Revision] | None = None) -> GoverningDocument:
    """Determine which package document controls this requirement."""
    revisions = revisions if revisions is not None else find_revisions(package)
    revision = match_revision(requirement, revisions)

    if revision is not None:
        return GoverningDocument(
            file_name=revision.document.file_name,
            document_type=revision.document.document_type,
            basis="addendum-revision",
            explanation=(
                f"{revision.document.document_type} explicitly revises '{revision.topic}', so it governs this "
                f"provision and supersedes the earlier package text."
            ),
            revision=revision,
        )

    # No revision: find which documents actually carry the provision, then let
    # DelDOT 105.6 break ties between documents that genuinely conflict.
    candidates: list[tuple[float, int, Document]] = []
    for document in package.documents:
        if _is_addendum(document):
            continue
        strength = topical_strength(requirement, document)
        if strength > 0:
            candidates.append((strength, _precedence_rank(document), document))

    if candidates:
        # Strongest topical match first; equal strength falls back to 105.6 rank.
        candidates.sort(key=lambda item: (-item[0], item[1]))
        top_strength, _, document = candidates[0]
        contenders = [c for c in candidates if c[0] == top_strength]
        if len(contenders) > 1:
            contenders.sort(key=lambda item: item[1])
            document = contenders[0][2]
            others = ", ".join(doc.document_type for _, _, doc in contenders[1:])
            explanation = (
                f"{document.document_type} outranks {others} under the DelDOT 105.6 order of precedence, "
                f"and no Addendum revises this provision."
            )
            basis = "105.6-precedence"
        elif len(candidates) == 1:
            explanation = (
                f"{document.document_type} is the only package document addressing this requirement."
            )
            basis = "only-source"
        else:
            explanation = (
                f"{document.document_type} carries the operative provision for this requirement and no Addendum "
                f"revises it; other documents mention it only in passing."
            )
            basis = "105.6-precedence"
        return GoverningDocument(
            file_name=document.file_name,
            document_type=document.document_type,
            basis=basis,
            explanation=explanation,
        )

    # Nothing mentions it: name the highest-precedence document present.
    fallback = min(
        (d for d in package.documents if not _is_addendum(d)),
        key=_precedence_rank,
        default=None,
    )
    if fallback is None:
        return GoverningDocument("(none)", "(none)", "only-source", "Package contains no reviewable documents.")
    return GoverningDocument(
        file_name=fallback.file_name,
        document_type=fallback.document_type,
        basis="105.6-precedence",
        explanation=(
            f"No package document addresses this requirement; {fallback.document_type} is the highest-precedence "
            f"document where the provision would be expected."
        ),
    )


if __name__ == "__main__":
    import sys

    from extract import load_package
    from requirements import REQUIREMENTS

    pkg = load_package(sys.argv[1])
    revs = find_revisions(pkg)
    print(f"{pkg.package_id}: {len(revs)} addendum revision(s) detected")
    for rev in revs:
        print(f"  [{rev.order}] {rev.citation}\n      {rev.text[:150]}")
    print()
    for req in REQUIREMENTS:
        gov = resolve(req, pkg, revs)
        print(f"  {req.id}  {gov.basis:<19} {gov.file_name}")
