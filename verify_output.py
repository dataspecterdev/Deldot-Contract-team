"""Validate the generated CSVs against Submission_Schema.csv and the enums."""
import csv
import sys

from contract_review.checklist import submission_fields
from contract_review.config import SEVERITIES

expected = list(submission_fields())
ok = True

for run in sys.argv[1:] or ["dev", "validation"]:
    rows = list(csv.DictReader(open(f"output/{run}/submission.csv", newline="", encoding="utf-8")))
    header = list(rows[0].keys())
    packages = sorted({r["document_id"] for r in rows})
    pairs = {(r["document_id"], r["requirement_id"]) for r in rows}

    checks = {
        "header matches schema exactly": header == expected,
        "one row per package x requirement": len(rows) == len(packages) * 18 == len(pairs),
        "applicability enum valid": all(
            r["applicability_decision"] in ("APPLIES", "DOES_NOT_APPLY") for r in rows
        ),
        "predicted_label enum valid": all(r["predicted_label"] in ("FLAG", "NO_FLAG") for r in rows),
        "severity enum valid": all(r["severity"] in SEVERITIES for r in rows),
        "DOES_NOT_APPLY implies NO_FLAG": all(
            r["predicted_label"] == "NO_FLAG"
            for r in rows
            if r["applicability_decision"] == "DOES_NOT_APPLY"
        ),
        "confidence within 0.00-1.00": all(0.0 <= float(r["confidence"]) <= 1.0 for r in rows),
        "required fields populated": all(
            all(r[f].strip() for f in expected if f not in ("draft_location", "draft_evidence"))
            for r in rows
        ),
        "FLAG rows carry location + evidence": all(
            r["draft_evidence"].strip() and r["draft_location"].strip()
            for r in rows
            if r["predicted_label"] == "FLAG"
        ),
        "NO_FLAG severity is Info": all(
            r["severity"] == "Info" for r in rows if r["predicted_label"] == "NO_FLAG"
        ),
    }

    print(f"--- {run}: {len(rows)} rows, {len(packages)} packages ---")
    for name, passed in checks.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
        ok &= passed

    trace = list(csv.DictReader(open(f"output/{run}/evidence_trace.csv", newline="", encoding="utf-8")))
    keyed = {(t["document_id"], t["requirement_id"]) for t in trace}
    aligned = keyed == pairs
    print(f"  {'PASS' if aligned else 'FAIL'}  evidence trace keyed 1:1 on document_id + CC-##")
    ok &= aligned

print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
sys.exit(0 if ok else 1)
