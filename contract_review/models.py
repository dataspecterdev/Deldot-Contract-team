"""Dataclasses shared across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Line:
    """A single extracted line of text with full provenance.

    ``line_id`` is the stable handle we show to the model and write into the
    evidence trace, e.g. ``Special_Provisions.pdf|p2|L14``. Because the model is
    asked to echo these ids back, every finding can be re-opened at the exact
    spot in the source PDF.
    """

    file_name: str
    page: int
    line_on_page: int
    global_line: int
    char_start: int
    char_end: int
    text: str
    heading: str = ""

    @property
    def line_id(self) -> str:
        return f"{self.file_name}|p{self.page}|L{self.line_on_page}"

    def as_record(self) -> dict[str, Any]:
        return {
            "line_id": self.line_id,
            "file_name": self.file_name,
            "page": self.page,
            "line_on_page": self.line_on_page,
            "global_line": self.global_line,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "heading": self.heading,
            "text": self.text,
        }


@dataclass
class ExtractedDocument:
    """One PDF from a contract package after text extraction."""

    file_name: str
    document_type: str
    package_status: str
    lines: list[Line] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def page_count(self) -> int:
        return max((line.page for line in self.lines), default=0)


@dataclass
class ContractPackage:
    """A contract package: metadata, document index and extracted documents."""

    package_id: str
    directory: Path
    metadata: dict[str, Any]
    documents: list[ExtractedDocument] = field(default_factory=list)

    def document(self, file_name: str) -> ExtractedDocument | None:
        for doc in self.documents:
            if doc.file_name == file_name:
                return doc
        return None

    @property
    def all_lines(self) -> list[Line]:
        return [line for doc in self.documents for line in doc.lines]

    def line_index(self) -> dict[str, Line]:
        return {line.line_id: line for line in self.all_lines}

    @property
    def addenda(self) -> list[ExtractedDocument]:
        return [
            doc
            for doc in self.documents
            if "addendum" in doc.document_type.lower()
            or "addendum" in doc.file_name.lower()
        ]


@dataclass
class Requirement:
    """One row of References/Reference_Checklist.csv."""

    requirement_id: str
    tier: str
    name: str
    reference_source: str
    section: str
    applicability_rule: str
    review_expectation: str
    severity_guidance: str
    evidence_required: str
    challenge_reference_rule: str


@dataclass
class ApplicabilityDecision:
    decision: str
    reason: str


@dataclass
class RetrievedChunk:
    """A reference excerpt returned by the Bedrock knowledge base."""

    text: str
    source_uri: str
    score: float

    @property
    def source_name(self) -> str:
        return self.source_uri.rsplit("/", 1)[-1]


@dataclass
class Finding:
    """The complete, traceable result for one package x requirement pair."""

    document_id: str
    requirement_id: str
    applicability_decision: str
    applicability_reason: str
    predicted_label: str
    severity: str
    governing_document: str
    draft_location: str
    draft_evidence: str
    reference_id: str
    reference_location: str
    reference_evidence: str
    explanation: str
    confidence: float
    recommended_human_action: str
    # Traceability extras (written to the evidence trace, not the submission).
    cited_line_ids: list[str] = field(default_factory=list)
    evidence_match_percent: float = 0.0
    retrieval_score_percent: float = 0.0
    retrieved_sources: list[str] = field(default_factory=list)
    notes: str = ""
