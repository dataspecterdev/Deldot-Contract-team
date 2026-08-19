"""Evidence verification and line-level location.

The model cites ``line_id`` tags and quotes text. This module checks those claims
against the extracted package:

* every cited line id must exist in the package (invented ids are dropped);
* the quoted evidence is matched back to the real file text to produce an
  ``evidence_match_percent`` - how much of the quote is genuinely present;
* if the model quotes text but cites no usable line, the quote itself is located
  by search so the user still gets a page and line to check.

The result is a human-checkable location string plus a numeric confidence in the
citation itself, kept separate from the model's own confidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .models import ContractPackage, Line


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace and unify quotes/dashes for comparison."""
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


# Models often stitch several verbatim passages into one quote. Splitting on
# these joiners lets each fragment be verified on its own, so a legitimate
# multi-part citation is not scored as a mismatch.
_FRAGMENT_SPLIT = re.compile(
    r"\s*(?:\[\s*\.\.\.\s*\]|\[\s*…\s*\]|\.\.\.\s|…|\s/\s|\s\|\s|\s--\s)\s*"
)


def _fragments(quote: str) -> list[str]:
    """Split a possibly multi-part quote into individually checkable pieces."""
    pieces = [piece.strip(" .;,/|-") for piece in _FRAGMENT_SPLIT.split(quote)]
    # Ignore scraps too short to verify meaningfully.
    return [piece for piece in pieces if len(_normalize(piece)) >= 12]


def _fragment_coverage(quote: str, haystack: str) -> tuple[float, bool]:
    """Fraction of the quote's fragments present verbatim in ``haystack``.

    Returns the coverage ratio and whether the quote was genuinely multi-part.
    """
    pieces = _fragments(quote)
    if len(pieces) < 2:
        return 0.0, False
    target = _normalize(haystack)
    matched = sum(1 for piece in pieces if _normalize(piece) in target)
    return matched / len(pieces), True


@dataclass
class LocatedEvidence:
    """Where a finding's evidence actually lives in the package."""

    lines: list[Line] = field(default_factory=list)
    match_percent: float = 0.0
    location: str = ""
    verified_quote: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def line_ids(self) -> list[str]:
        return [line.line_id for line in self.lines]


def _format_location(lines: list[Line], fallback_file: str = "") -> str:
    """Human-readable location: file, page, line range and heading."""
    if not lines:
        return fallback_file

    by_file: dict[str, list[Line]] = {}
    for line in lines:
        by_file.setdefault(line.file_name, []).append(line)

    parts: list[str] = []
    for file_name, group in by_file.items():
        group.sort(key=lambda ln: (ln.page, ln.line_on_page))
        pages = sorted({ln.page for ln in group})
        page_text = f"p{pages[0]}" if len(pages) == 1 else f"p{pages[0]}-p{pages[-1]}"
        numbers = [ln.line_on_page for ln in group]
        if len(numbers) == 1:
            line_text = f"line {numbers[0]}"
        elif numbers == list(range(numbers[0], numbers[-1] + 1)):
            line_text = f"lines {numbers[0]}-{numbers[-1]}"
        else:
            line_text = "lines " + ",".join(str(n) for n in numbers)
        heading = next((ln.heading for ln in group if ln.heading), "")
        segment = f"{file_name}, {page_text}, {line_text}"
        if heading:
            segment += f' (section "{heading}")'
        parts.append(segment)
    return "; ".join(parts)


def _best_window(quote: str, lines: list[Line], max_span: int = 6) -> tuple[list[Line], float]:
    """Find the run of consecutive lines that best matches ``quote``."""
    target = _normalize(quote)
    if not target or not lines:
        return [], 0.0

    best: tuple[list[Line], float] = ([], 0.0)
    for start in range(len(lines)):
        joined = ""
        for span in range(max_span):
            index = start + span
            if index >= len(lines):
                break
            # Only join lines that stay inside the same page.
            if span and lines[index].file_name != lines[start].file_name:
                break
            joined = f"{joined} {lines[index].text}".strip()
            candidate = _normalize(joined)
            if not candidate:
                continue
            if target in candidate:
                # Exact containment: prefer the tightest window.
                return lines[start : index + 1], 1.0
            ratio = SequenceMatcher(None, target, candidate).ratio()
            if ratio > best[1]:
                best = (lines[start : index + 1], ratio)
    return best


def locate(
    package: ContractPackage,
    cited_line_ids: list[str] | None,
    quote: str,
    preferred_file: str = "",
) -> LocatedEvidence:
    """Verify cited lines and locate the quoted evidence in the package."""
    result = LocatedEvidence()
    index = package.line_index()

    valid: list[Line] = []
    for raw in cited_line_ids or []:
        line_id = str(raw).strip().strip("[]")
        line = index.get(line_id)
        if line is not None:
            valid.append(line)
        elif line_id:
            result.notes.append(f"unknown line id cited: {line_id}")

    quote = (quote or "").strip()

    if valid:
        valid.sort(key=lambda ln: (ln.file_name, ln.page, ln.line_on_page))
        result.lines = valid
        if quote:
            cited_raw = " ".join(ln.text for ln in valid)
            cited_text = _normalize(cited_raw)
            target = _normalize(quote)
            coverage, multipart = _fragment_coverage(quote, cited_raw)
            if target and target in cited_text:
                result.match_percent = 100.0
                result.verified_quote = quote
            elif multipart and coverage > 0:
                # Each fragment checked on its own against the cited lines.
                result.match_percent = round(coverage * 100, 1)
                result.verified_quote = quote
                if coverage == 1.0:
                    result.notes.append(
                        "multi-part quote; every fragment verified verbatim at the cited lines"
                    )
                else:
                    result.notes.append(
                        f"multi-part quote; {int(round(coverage * 100))}% of fragments verified verbatim"
                    )
            else:
                ratio = SequenceMatcher(None, target, cited_text).ratio() if target else 0.0
                result.match_percent = round(ratio * 100, 1)
                result.verified_quote = quote
                # Weak agreement: try to find where the quote really sits.
                if ratio < 0.6:
                    scope = package.all_lines
                    if preferred_file:
                        scoped = [ln for ln in scope if ln.file_name == preferred_file]
                        scope = scoped or scope
                    found, found_ratio = _best_window(quote, scope)
                    if found and found_ratio > ratio:
                        result.notes.append(
                            "quoted evidence matched better outside the cited lines"
                        )
                        result.lines = found
                        result.match_percent = round(found_ratio * 100, 1)
        else:
            # Cited lines with no quote still give a checkable location.
            result.match_percent = 0.0
        result.location = _format_location(result.lines, preferred_file)
        return result

    # No usable citation: locate the quote directly.
    if quote:
        scope = package.all_lines
        if preferred_file:
            scoped = [ln for ln in scope if ln.file_name == preferred_file]
            scope = scoped or scope
        found, ratio = _best_window(quote, scope)
        if found:
            result.lines = found
            result.match_percent = round(ratio * 100, 1)
            result.verified_quote = quote
            result.notes.append("located by text search; model cited no valid line id")

    result.location = _format_location(result.lines, preferred_file)
    return result
