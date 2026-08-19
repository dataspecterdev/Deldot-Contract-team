"""Cross-document precedence and Addendum resolution.

Two rules drive this module:

* DelDOT 105.6 sets a static order of precedence between document types.
* A later Addendum that explicitly revises a named provision governs that
  provision, overriding both the original text and the static order.

The resolver reads the Addenda, works out which requirement each revision
targets, and reports the governing document per requirement so the analysis
prompt compares against the text that actually controls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import PRECEDENCE_ORDER
from .models import ContractPackage, ExtractedDocument, Line, Requirement

# "Revision to Performance and payment bonds", "Section 103.5 is hereby revised"
_REVISION_HEADER = re.compile(
    r"^\s*(?:revision\s+to|revised\s+provision|amendment\s+to)\s*[:\-]?\s*(?P<topic>.+?)\s*$",
    re.IGNORECASE,
)
_REVISION_VERB = re.compile(
    r"\b(is\s+hereby\s+(?:revised|replaced|deleted|amended)|"
    r"delete\s+and\s+replace|replacement\s+text|the\s+following\s+replaces)\b",
    re.IGNORECASE,
)
_NO_CHANGE = re.compile(
    r"\bmakes\s+no\s+change|no\s+changes?\s+(?:are\s+)?made|does\s+not\s+(?:change|revise)\b",
    re.IGNORECASE,
)
_ORDINAL = re.compile(r"(?:addendum|addenda)[\s_]*([A-Z]|\d+)", re.IGNORECASE)

_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "for", "in", "on", "must", "shall",
    "is", "are", "be", "with", "requirement", "requirements", "provision", "clause",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def addendum_rank(doc: ExtractedDocument) -> int:
    """Order addenda so later ones win. ``Addendum_C`` outranks ``Addendum_A``."""
    match = _ORDINAL.search(f"{doc.document_type} {doc.file_name}")
    if not match:
        return 0
    token = match.group(1).upper()
    if token.isdigit():
        return int(token)
    return ord(token) - ord("A") + 1


@dataclass
class Revision:
    """One provision revision carried by an Addendum."""

    document: str
    rank: int
    topic: str
    replacement_text: str
    lines: list[Line]

    @property
    def location(self) -> str:
        if not self.lines:
            return self.document
        pages = sorted({ln.page for ln in self.lines})
        span = f"p{pages[0]}" if len(pages) == 1 else f"p{pages[0]}-p{pages[-1]}"
        return f"{self.document}, {span}, lines {self.lines[0].line_on_page}-{self.lines[-1].line_on_page}"


def extract_revisions(package: ContractPackage) -> list[Revision]:
    """Collect every provision revision announced by the package Addenda."""
    revisions: list[Revision] = []

    for doc in sorted(package.addenda, key=addendum_rank):
        rank = addendum_rank(doc)
        lines = doc.lines
        for idx, line in enumerate(lines):
            header = _REVISION_HEADER.match(line.text)
            if not header:
                continue
            topic = header.group("topic").strip(" .:")
            if not topic or _NO_CHANGE.search(line.text):
                continue

            # Body = following lines until the next revision header or the
            # page footer, skipping the "REPLACEMENT TEXT:" marker itself.
            body: list[Line] = []
            for follower in lines[idx + 1 :]:
                if _REVISION_HEADER.match(follower.text):
                    break
                if re.match(r"^\s*(replacement\s+text|new\s+text)\s*[:\-]?\s*$", follower.text, re.IGNORECASE):
                    continue
                if "FOR EVALUATION USE ONLY" in follower.text:
                    break
                body.append(follower)

            revisions.append(
                Revision(
                    document=doc.file_name,
                    rank=rank,
                    topic=topic,
                    replacement_text=" ".join(ln.text for ln in body).strip(),
                    lines=body or [line],
                )
            )

    return revisions


def _document_type_rank(doc: ExtractedDocument) -> int:
    haystack = f"{doc.document_type} {doc.file_name}".lower()
    for position, label in enumerate(PRECEDENCE_ORDER):
        if label.lower() in haystack:
            return position
    # General Conditions behaves like Special Provisions for this dataset:
    # more specific than the Standard Specifications baseline.
    if "general condition" in haystack:
        return PRECEDENCE_ORDER.index("Special Provisions")
    return len(PRECEDENCE_ORDER)


@dataclass
class GoverningDocument:
    """Which package document controls a requirement, and why."""

    file_name: str
    reason: str
    superseding_revision: Revision | None = None

    @property
    def is_superseded(self) -> bool:
        return self.superseding_revision is not None


def resolve(
    package: ContractPackage,
    requirement: Requirement,
    revisions: list[Revision] | None = None,
    threshold: float = 0.34,
) -> GoverningDocument:
    """Resolve the governing document for one requirement."""
    revisions = revisions if revisions is not None else extract_revisions(package)

    # 1. A later Addendum explicitly revising this provision governs.
    best: tuple[float, Revision] | None = None
    for revision in revisions:
        score = max(
            _similarity(revision.topic, requirement.name),
            _similarity(revision.topic, requirement.section),
        )
        if score >= threshold and (best is None or (score, revision.rank) >= (best[0], best[1].rank)):
            best = (score, revision)

    if best is not None:
        revision = best[1]
        return GoverningDocument(
            file_name=revision.document,
            reason=(
                f"{revision.document} explicitly revises '{revision.topic}' and therefore governs "
                f"this provision over the earlier package text."
            ),
            superseding_revision=revision,
        )

    # 2. Otherwise, the document that actually carries the clause, chosen by the
    #    DelDOT 105.6 order when several mention it.
    candidates: list[tuple[int, float, ExtractedDocument]] = []
    for doc in package.documents:
        if doc in package.addenda:
            continue
        topical = max(
            (
                max(_similarity(line.text, requirement.name), _similarity(line.heading, requirement.name))
                for line in doc.lines
            ),
            default=0.0,
        )
        if topical > 0:
            candidates.append((_document_type_rank(doc), -topical, doc))

    if candidates:
        candidates.sort(key=lambda item: (item[1], item[0]))
        doc = candidates[0][2]
        return GoverningDocument(
            file_name=doc.file_name,
            reason=(
                f"{doc.file_name} carries this provision and ranks highest under the DelDOT 105.6 "
                f"order of precedence among the documents that address it."
            ),
        )

    # 3. Nothing addresses it: fall back to the proposal, which is where an
    #    omission would be visible.
    fallback = next(
        (d for d in package.documents if "proposal" in d.file_name.lower()),
        package.documents[0] if package.documents else None,
    )
    return GoverningDocument(
        file_name=fallback.file_name if fallback else "(no package document)",
        reason="No package document addresses this provision; reviewed the proposal for an omission.",
    )


def resolve_all(
    package: ContractPackage, requirements: list[Requirement]
) -> dict[str, GoverningDocument]:
    revisions = extract_revisions(package)
    return {req.requirement_id: resolve(package, req, revisions) for req in requirements}
