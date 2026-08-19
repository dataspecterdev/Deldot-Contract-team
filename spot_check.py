"""Independently re-open the PDFs and confirm each cited line holds the quote.

Deliberately does not reuse the pipeline's extraction cache: it re-reads the PDF
with pdfplumber and counts lines the way a human would, so the reported page and
line numbers are checked rather than trusted.
"""
import csv
import re
import sys
from pathlib import Path

import pdfplumber

CHALLENGE = Path("Contract_Clause_Risk_Flagging")


def page_lines(pdf_path: Path, page_number: int) -> list[str]:
    """Return the visual lines of a page, 1-based, blanks included."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        text = pdf.pages[page_number - 1].extract_text() or ""
    return text.splitlines()


def normalize(text: str) -> str:
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def find_package(document_id: str) -> Path | None:
    for parent in (CHALLENGE / "Development", CHALLENGE / "Validation"):
        for child in parent.iterdir() if parent.exists() else []:
            meta = child / "Project_Metadata.json"
            if meta.exists() and f'"{document_id}"' in meta.read_text(encoding="utf-8"):
                return child
    return None


def main(trace_path: str) -> int:
    rows = list(csv.DictReader(open(trace_path, newline="", encoding="utf-8")))
    checked = confirmed = 0
    failures: list[str] = []

    for row in rows:
        quote = row["draft_evidence_quote"].strip()
        ids = [i.strip() for i in row["evidence_line_ids"].split(";") if i.strip()]
        if not quote or not ids:
            continue

        package_dir = find_package(row["document_id"])
        if package_dir is None:
            continue

        # Rebuild the cited text straight from the PDFs.
        cited_text = ""
        for line_id in ids:
            file_name, page_token, line_token = line_id.split("|")
            page = int(page_token.lstrip("p"))
            line_no = int(line_token.lstrip("L"))
            pdf_path = package_dir / "Docs" / file_name
            if not pdf_path.exists():
                failures.append(f"{row['document_id']} {row['requirement_id']}: missing {file_name}")
                break
            lines = page_lines(pdf_path, page)
            if line_no > len(lines):
                failures.append(
                    f"{row['document_id']} {row['requirement_id']}: {file_name} p{page} has "
                    f"{len(lines)} lines, cited L{line_no}"
                )
                break
            cited_text += " " + lines[line_no - 1]
        else:
            checked += 1
            haystack = normalize(cited_text)
            if normalize(quote) in haystack:
                confirmed += 1
            else:
                # A multi-part quote is valid when every fragment is verbatim.
                pieces = [
                    p.strip(" .;,/|-")
                    for p in re.split(r"\s*(?:\[\s*\.\.\.\s*\]|\.\.\.\s|…|\s/\s|\s\|\s)\s*", quote)
                ]
                pieces = [p for p in pieces if len(normalize(p)) >= 12]
                if len(pieces) >= 2 and all(normalize(p) in haystack for p in pieces):
                    confirmed += 1
                else:
                    failures.append(
                        f"{row['document_id']} {row['requirement_id']}: quote not found at cited lines"
                    )

    print(f"spot check: {confirmed}/{checked} quotes confirmed at the cited page and line")
    for failure in failures:
        print(f"  {failure}")
    return 0 if confirmed == checked and not failures else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "output/dev/evidence_trace.csv"))
