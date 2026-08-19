# `run_summary.json`

Run bookkeeping: what was processed, how it came out, what it cost, and which
files were produced. Small, flat, and about the *run* rather than about the
contracts.

Written only by the API path (`dora_api/analysis.py`, `run_analysis`), so it
appears for projects analysed through the UI but not for CLI runs. It is also
the value returned to the API caller when analysis completes.

## Shape

```json
{
  "packages_analyzed": 2,
  "packages": [
    {
      "package_id": "DEV-HARBOR-CROSSING",
      "package_name": "Harbor_Crossing",
      "total_findings": 18,
      "flags": 5,
      "compliant": 13
    }
  ],
  "totals": {
    "total_findings": 36,
    "flags": 9,
    "compliant": 27
  },
  "tokens_in": 412350,
  "tokens_out": 18422,
  "output_files": [
    "submission.csv",
    "evidence_trace.csv",
    "findings_report.json"
  ]
}
```

## Top-level fields

### `packages_analyzed`

How many packages produced findings. Uploaded folders that turned out to contain
no PDFs are skipped and not counted, so this can be lower than the number of
folders uploaded.

### `packages[]`

One entry per analysed package, in processing order.

### `totals`

Run-wide counts. Equal to the sum of the per-package numbers.

### `tokens_in` / `tokens_out`

Bedrock token usage for the whole run, accumulated on the `BedrockClient`.
`tokens_in` covers prompts sent (the line-tagged package text dominates this),
`tokens_out` covers model responses. Cost and throttling diagnostics, nothing to
do with the contracts.

### `output_files`

File names of the three finding files written alongside this summary. Names only,
no paths — they sit in the same directory. `run_summary.json` does not list
itself.

## `packages[]` fields

### `package_id` vs `package_name`

Two names for the same package, from different places. This is the one pair in
this file worth understanding:

- `package_id` — the identifier the findings use. Read from `package_id` in the
  package's `Project_Metadata.json`, falling back to the prepared package folder
  name. This is the value that appears as `document_id` in both CSVs and as
  `package_id` in the JSON report.
- `package_name` — the name from the upload: the subfolder name, or the project
  name when PDFs were uploaded loose at the root. Display-oriented.

They match when uploaded metadata omits `package_id` (a default is synthesised
from the folder name, with spaces replaced by underscores). They differ when the
metadata carries its own id — e.g. folder `Harbor_Crossing` supplying
`package_id: DEV-HARBOR-CROSSING`. **Join to the other output files on
`package_id`, never on `package_name`.**

### `total_findings`

Findings for this package. Equals the number of checklist requirements analysed,
since every requirement gets a row whether or not it applies.

### `flags` / `compliant`

`FLAG` and `NO_FLAG` counts for this package. They sum to `total_findings`.

`compliant` is a `NO_FLAG` count, which includes requirements that do not apply
to the project. It is not a "checked and clean" count. For that distinction, read
`applicability_decision` in [`submission.csv`](submission_csv.md) or
`decision.applicability` in
[`findings_report.json`](findings_report_json.md).

The same three fields appear in `totals` with `total_findings` keeping its name
while `flags` and `compliant` also keep theirs — so unlike the JSON report,
scope here is signalled by the block (`packages[]` vs `totals`) rather than by a
`total_` prefix.

## Relationship to the JSON report

`run_summary.json` and the `summary` block of
[`findings_report.json`](findings_report_json.md) count the same things with
different keys and one extra field each:

| Concept | `run_summary.json` | `findings_report.json` |
| --- | --- | --- |
| Package count | `packages_analyzed` | `summary.total_packages` |
| Findings, run-wide | `totals.total_findings` | `summary.total_requirements_checked` |
| Flags, run-wide | `totals.flags` | `summary.total_flags` |
| `NO_FLAG`, run-wide | `totals.compliant` | `summary.total_compliant` |
| Findings, per package | `packages[].total_findings` | `packages[].summary.total_requirements_checked` |
| Which requirements flagged | not carried | `packages[].summary.flag_ids` |
| Upload folder name | `packages[].package_name` | not carried |
| Token usage | `tokens_in` / `tokens_out` | not carried |

If the two ever disagree, the JSON report is derived from the findings
themselves and is the one to trust.

## Error runs

No summary file is written when analysis raises. The failure is recorded on the
project status instead (`project_manager.update_status(..., "error", ...)`), so
the absence of `run_summary.json` in an output directory means the run did not
finish.

Note the difference in scope: a *run* failure means no summary file at all,
whereas a single *requirement* failing its model call still produces a row — a
`NO_FLAG` placeholder with confidence `0` and an `analysis error:` note in
[`evidence_trace.csv`](evidence_trace_csv.md). Those placeholder rows are counted
in `compliant` here, which is a reason not to read `compliant` as a clean bill of
health.
