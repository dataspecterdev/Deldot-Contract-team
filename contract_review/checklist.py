"""Loader for References/Reference_Checklist.csv - the scoring authority."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from .config import REFERENCE_CHECKLIST
from .models import Requirement


@lru_cache(maxsize=None)
def load_requirements(path: Path | None = None) -> tuple[Requirement, ...]:
    """Read the reference checklist into ordered :class:`Requirement` records."""
    csv_path = Path(path) if path else REFERENCE_CHECKLIST
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    requirements: list[Requirement] = []
    for row in rows:
        requirement_id = (row.get("Requirement_ID") or "").strip()
        if not requirement_id:
            continue
        requirements.append(
            Requirement(
                requirement_id=requirement_id,
                tier=(row.get("Tier") or "").strip(),
                name=(row.get("Requirement_Name") or "").strip(),
                reference_source=(row.get("Reference_Source") or "").strip(),
                section=(row.get("Section") or "").strip(),
                applicability_rule=(row.get("Applicability_Rule") or "").strip(),
                review_expectation=(row.get("Review_Expectation") or "").strip(),
                severity_guidance=(row.get("Severity_Guidance") or "").strip(),
                evidence_required=(row.get("Evidence_Required") or "").strip(),
                challenge_reference_rule=(row.get("Challenge_Reference_Rule") or "").strip(),
            )
        )
    return tuple(requirements)


def requirement_map(path: Path | None = None) -> dict[str, Requirement]:
    return {req.requirement_id: req for req in load_requirements(path)}


@lru_cache(maxsize=None)
def submission_fields(path: Path | None = None) -> tuple[str, ...]:
    """Column order for the submission CSV, read from Submission_Schema.csv."""
    from .config import SUBMISSION_SCHEMA

    csv_path = Path(path) if path else SUBMISSION_SCHEMA
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        return tuple(
            (row.get("field") or "").strip()
            for row in csv.DictReader(handle)
            if (row.get("field") or "").strip()
        )
