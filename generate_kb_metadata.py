"""
Generates Bedrock Knowledge Base metadata sidecar files for each source document.

Each source file in Sources/ gets a matching <filename>.metadata.json so that
retrieval can be filtered by requirement_id. This keeps corroboration lookups
scoped to the correct reference section instead of competing across the 18 docs
(several DelDOT sections cross-reference each other and would otherwise collide).

Metadata is derived from References/Reference_Checklist.csv so the values stay
consistent with the scoring authority.
"""
import csv
import json
from pathlib import Path

BASE = Path(r"d:\Downloads\Hackathon\Github\Deldot-Contract-team\Contract_Clause_Risk_Flagging")
SOURCES = BASE / "Sources"
CHECKLIST = BASE / "References" / "Reference_Checklist.csv"

# Load checklist rows keyed by Requirement_ID
checklist = {}
with CHECKLIST.open(newline="", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        checklist[row["Requirement_ID"]] = row

written = 0
for src in sorted(SOURCES.glob("CC-*.txt")):
    # Filenames are CC-01_FHWA-1273.txt -> requirement id is the leading token
    req_id = src.name.split("_")[0]
    row = checklist.get(req_id)
    if row is None:
        print(f"WARNING: no checklist row for {req_id} ({src.name}) - skipped")
        continue

    metadata = {
        "metadataAttributes": {
            "requirement_id": req_id,
            "tier": row["Tier"],
            "requirement_name": row["Requirement_Name"],
            "reference_source": row["Reference_Source"],
            "section": row["Section"],
            "severity_guidance": row["Severity_Guidance"],
        }
    }

    out = src.with_suffix(src.suffix + ".metadata.json")
    out.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    written += 1
    print(f"{out.name}  ->  requirement_id={req_id}, section={row['Section']}")

print(f"\nWrote {written} metadata sidecar files.")
