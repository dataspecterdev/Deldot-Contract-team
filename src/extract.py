"""
PDF extraction with location metadata.

Every line of every contract document keeps its file name, page number, line
number on the page, global line number, character offsets, and the nearest
preceding heading. That is what makes a finding traceable: a reviewer can open
the PDF at the cited page/line and read the same words the model read.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import pdfplumber

# Headings we care about in DelDOT-style packages, e.g.
#   "102.8 Proposal Guaranty."      -> numbered spec section
#   "SECTION 5 - CONTRACT CHANGES"  -> all-caps heading
#   "Right to Audit"                -> short title-case line
_NUMBERED_HEADING = re.compile(r"^\s*(\d{3}\.\d+(?:\.\d+)?)\s+(.+?)\.?\s*$")
_CAPS_HEADING = re.compile(r"^[A-Z0-9][A-Z0-9 ,.:;/&()\-']{3,80}$")
_ADDENDUM_HEADING = re.compile(r"^\s*ADDENDUM\s+(?:NO\.?\s*)?([A-Z0-9]+)", re.IGNORECASE)


@dataclass
class TextLine:
    """One line of text plus everything needed to point a human back at it."""

    file_name: str
    document_type: str
    page: int
    line_on_page: int
    line_global: int
    char_start: int
    char_end: int
    heading: str
    text: str

    def citation(self) -> str:
        """Human-readable location, e.g. 'Special_Provisions.pdf p.2 line 14 (108.9 ...)'."""
        base = f"{self.file_name} p.{self.page} line {self.line_on_page}"
        return f"{base} ({self.heading})" if self.heading else base


@dataclass
class Document:
    file_name: str
    document_type: str
    package_status: str
    lines: list[TextLine]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    def numbered_text(self) -> str:
        """Text with page/line prefixes so the model can cite exact locations."""
        return "\n".join(
            f"[p{line.page}:L{line.line_on_page}] {line.text}" for line in self.lines
        )


@dataclass
class Package:
    package_id: str
    root: Path
    metadata: dict
    documents: list[Document]

    def document_types(self) -> list[str]:
        return [doc.document_type for doc in self.documents]

    def find_document(self, needle: str) -> Document | None:
        needle = needle.lower()
        for doc in self.documents:
            if needle in doc.file_name.lower() or needle in doc.document_type.lower():
                return doc
        return None

    def bundle_text(self, max_chars_per_doc: int | None = None) -> str:
        """All package documents concatenated, labelled, and line-numbered."""
        parts = []
        for doc in self.documents:
            body = doc.numbered_text()
            if max_chars_per_doc and len(body) > max_chars_per_doc:
                body = body[:max_chars_per_doc] + "\n[... truncated ...]"
            parts.append(
                f"===== FILE: {doc.file_name} | TYPE: {doc.document_type} "
                f"| STATUS: {doc.package_status} =====\n{body}"
            )
        return "\n\n".join(parts)


def _classify_heading(line: str, current: str) -> str:
    """Return the heading this line establishes, or the current one if it is body text."""
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return current

    addendum = _ADDENDUM_HEADING.match(stripped)
    if addendum:
        return stripped.rstrip(".")

    numbered = _NUMBERED_HEADING.match(stripped)
    if numbered:
        return f"{numbered.group(1)} {numbered.group(2)}".strip()

    # All-caps lines that are not sentences act as headings.
    if _CAPS_HEADING.match(stripped) and not stripped.endswith((".", ";", ",")):
        letters = [c for c in stripped if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.85:
            return stripped

    return current


def extract_document(pdf_path: Path, document_type: str, package_status: str) -> Document:
    """Read one PDF into location-tagged lines."""
    lines: list[TextLine] = []
    char_cursor = 0
    line_global = 0
    heading = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            for line_on_page, raw_line in enumerate(raw.split("\n"), start=1):
                text = raw_line.rstrip()
                if not text.strip():
                    char_cursor += len(raw_line) + 1
                    continue

                heading = _classify_heading(text, heading)
                line_global += 1
                lines.append(
                    TextLine(
                        file_name=pdf_path.name,
                        document_type=document_type,
                        page=page_index,
                        line_on_page=line_on_page,
                        line_global=line_global,
                        char_start=char_cursor,
                        char_end=char_cursor + len(text),
                        heading=heading,
                        text=text,
                    )
                )
                char_cursor += len(raw_line) + 1

    return Document(
        file_name=pdf_path.name,
        document_type=document_type,
        package_status=package_status,
        lines=lines,
    )


def _read_document_index(index_path: Path) -> list[dict]:
    if not index_path.exists():
        return []
    with index_path.open(newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle) if any(row.values())]


def load_package(package_dir: str | Path) -> Package:
    """Load a contract package: metadata, document index, and every PDF in Docs/."""
    root = Path(package_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"Package directory not found: {root}")

    metadata_path = root / "Project_Metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}

    docs_dir = root / "Docs" if (root / "Docs").is_dir() else root
    index_rows = _read_document_index(root / "Document_Index.csv")
    indexed = {
        row["File_Name"].strip(): (
            row.get("Document_Type", "").strip(),
            row.get("Package_Status", "").strip(),
        )
        for row in index_rows
        if row.get("File_Name")
    }

    documents: list[Document] = []
    for pdf_path in sorted(docs_dir.glob("*.pdf")):
        document_type, package_status = indexed.get(
            pdf_path.name, (pdf_path.stem.replace("_", " "), "Not listed in Document_Index.csv")
        )
        documents.append(extract_document(pdf_path, document_type, package_status))

    # Keep index order where possible so precedence reasoning sees a stable list.
    if indexed:
        order = list(indexed.keys())
        documents.sort(
            key=lambda d: order.index(d.file_name) if d.file_name in order else len(order)
        )

    package_id = metadata.get("package_id") or root.name.upper().replace("_", "-")
    return Package(package_id=package_id, root=root, metadata=metadata, documents=documents)


def package_to_dict(package: Package) -> dict:
    """Serialisable view, handy for caching extractions or debugging citations."""
    return {
        "package_id": package.package_id,
        "root": str(package.root),
        "metadata": package.metadata,
        "documents": [
            {
                "file_name": doc.file_name,
                "document_type": doc.document_type,
                "package_status": doc.package_status,
                "lines": [asdict(line) for line in doc.lines],
            }
            for doc in package.documents
        ],
    }


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "."
    pkg = load_package(target)
    print(f"Package: {pkg.package_id}")
    print(f"Metadata keys: {', '.join(pkg.metadata) or '(none)'}")
    for document in pkg.documents:
        print(f"  {document.file_name:<48} {document.document_type:<34} {len(document.lines):>4} lines")
    total = sum(len(d.lines) for d in pkg.documents)
    print(f"Total lines: {total}")
