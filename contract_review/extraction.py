"""PDF text extraction that preserves page, line and character provenance.

Every line keeps the page it came from, its 1-based position on that page, a
running document-wide line number and the character offsets inside the
reconstructed document text. That is what makes a finding checkable: the user
can open the PDF at the reported page and count down to the reported line.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pdfplumber

from .models import ContractPackage, ExtractedDocument, Line

# A heading is a short line that looks like a section title: a numbered DelDOT
# section, an ALL CAPS banner, a lettered clause header, or a topic label.
_SECTION_NUMBER = re.compile(r"^\s*(?:SECTION\s+)?\d{3}\.\d+(?:\.\d+)?\b", re.IGNORECASE)
_LETTERED_HEADING = re.compile(r"^\s*[A-Z]\.\s+[A-Z]")
_ARTICLE = re.compile(r"^\s*(ARTICLE|ADDENDUM|ATTACHMENT|EXHIBIT|APPENDIX|REVISION TO)\b", re.IGNORECASE)

# Page furniture and disclaimers: never useful as a section label.
_BOILERPLATE = re.compile(
    r"(FOR EVALUATION USE ONLY|SAMPLE MATERIAL|NOT AN EXECUTED CONTRACT|"
    r"CONTRACT CLAUSE RISK FLAGGING|SAMPLE CONTRACT DOCUMENT|^Page \d+$|"
    r"^REPLACEMENT TEXT|^NEW TEXT)",
    re.IGNORECASE,
)


def _looks_like_heading(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 120:
        return False
    if _BOILERPLATE.search(stripped):
        return False
    if _SECTION_NUMBER.match(stripped) or _ARTICLE.match(stripped):
        return True
    if _LETTERED_HEADING.match(stripped):
        return True
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) >= 4 and all(c.isupper() for c in letters):
        return True
    # Topic label: a short line with no terminal punctuation that does not read
    # as a sentence, e.g. "Proposal guaranty / bid bond".
    if len(stripped) <= 90 and stripped[-1] not in ".;:,":
        words = stripped.split()
        if 1 < len(words) <= 12 and stripped[0].isupper():
            return True
    return False


def extract_pdf(path: Path, document_type: str = "", package_status: str = "") -> ExtractedDocument:
    """Extract one PDF into an :class:`ExtractedDocument` of provenance-rich lines."""
    doc = ExtractedDocument(
        file_name=path.name,
        document_type=document_type or path.stem.replace("_", " "),
        package_status=package_status,
    )

    char_cursor = 0
    global_line = 0
    current_heading = ""

    with pdfplumber.open(str(path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            line_on_page = 0
            for raw_line in page_text.splitlines():
                text = raw_line.rstrip()
                if not text.strip():
                    # Keep blank lines out of the index but still advance the
                    # visual line counter so reported numbers match the PDF.
                    line_on_page += 1
                    char_cursor += len(raw_line) + 1
                    continue

                line_on_page += 1
                global_line += 1

                if _looks_like_heading(text):
                    current_heading = text.strip()

                doc.lines.append(
                    Line(
                        file_name=path.name,
                        page=page_number,
                        line_on_page=line_on_page,
                        global_line=global_line,
                        char_start=char_cursor,
                        char_end=char_cursor + len(text),
                        text=text,
                        heading=current_heading,
                    )
                )
                char_cursor += len(raw_line) + 1

    return doc


def _read_document_index(package_dir: Path) -> list[dict[str, str]]:
    index_path = package_dir / "Document_Index.csv"
    if not index_path.exists():
        return []
    with index_path.open(newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle)]


def load_package(package_dir: Path) -> ContractPackage:
    """Load a contract package: metadata, document index and extracted PDFs."""
    package_dir = Path(package_dir)
    metadata_path = package_dir / "Project_Metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    raw_id = str(metadata.get("package_id", package_dir.name))
    # Sanitize: strip commas, newlines, and excess length that would break CSV output
    clean_id = raw_id.replace(",", "").replace("\n", " ").replace("\r", "")
    clean_id = "_".join(clean_id.split())[:60] or package_dir.name

    package = ContractPackage(
        package_id=clean_id,
        directory=package_dir,
        metadata=metadata,
    )

    docs_dir = package_dir / "Docs"
    index_rows = _read_document_index(package_dir)

    # Follow Document_Index.csv order when present: it reflects the package's
    # own view of which documents are current.
    ordered: list[tuple[Path, str, str]] = []
    seen: set[str] = set()
    for row in index_rows:
        file_name = (row.get("File_Name") or "").strip()
        if not file_name:
            continue
        candidate = docs_dir / file_name
        if candidate.exists():
            ordered.append(
                (
                    candidate,
                    (row.get("Document_Type") or "").strip(),
                    (row.get("Package_Status") or "").strip(),
                )
            )
            seen.add(file_name)

    if docs_dir.exists():
        for pdf_path in sorted(docs_dir.glob("*.pdf")):
            if pdf_path.name not in seen:
                ordered.append((pdf_path, "", ""))

    for pdf_path, doc_type, status in ordered:
        package.documents.append(extract_pdf(pdf_path, doc_type, status))

    return package


def discover_packages(root: Path) -> list[Path]:
    """Return every package directory under ``root`` (one per project)."""
    root = Path(root)
    if not root.exists():
        return []
    return sorted(
        child
        for child in root.iterdir()
        if child.is_dir() and (child / "Project_Metadata.json").exists()
    )


def render_numbered_text(package: ContractPackage, governing_first: list[str] | None = None) -> str:
    """Render the whole package as line-tagged text for the model prompt.

    Each line is prefixed with its ``line_id`` so the model can cite exact
    locations instead of paraphrasing where it looked.
    """
    order = list(package.documents)
    if governing_first:
        priority = {name: i for i, name in enumerate(governing_first)}
        order.sort(key=lambda d: priority.get(d.file_name, len(priority)))

    blocks: list[str] = []
    for doc in order:
        status = f" [{doc.package_status}]" if doc.package_status else ""
        header = f"=== FILE: {doc.file_name} (type: {doc.document_type}{status}) ==="
        body = "\n".join(f"[{line.line_id}] {line.text}" for line in doc.lines)
        blocks.append(f"{header}\n{body}")
    return "\n\n".join(blocks)
