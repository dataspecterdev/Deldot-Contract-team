# Output file reference

Every analysis run writes the same set of files. Each one is documented separately:

| File | Format | Written by | Purpose |
| --- | --- | --- | --- |
| [`submission.csv`](submission_csv.md) | CSV, 15 columns | CLI + API | The deliverable. One row per package x requirement, columns fixed by `Submission_Schema.csv`. |
| [`evidence_trace.csv`](evidence_trace_csv.md) | CSV, 18 columns | CLI + API | The audit companion. Same rows, but with file/page/line numbers and the three quality percentages so a reviewer can re-open the PDF and check the claim. |
| [`findings_report.json`](findings_report_json.md) | JSON, nested | CLI + API | The human-readable report. Same findings plus the verbatim contract lines and the checklist rule each was judged against. |
| [`run_summary.json`](run_summary_json.md) | JSON, flat | API only | Run bookkeeping: packages processed, flag counts, token usage, files produced. |

`submission.csv`, `evidence_trace.csv` and `findings_report.json` all describe the
*same* findings. They differ in what they carry, not in what they claim.

## Row identity

In all three finding files a row is identified by the pair
`document_id` + `requirement_id`. Use that pair to join across files.

- `document_id` — the contract package. Read from `package_id` in
  `Project_Metadata.json`, falling back to the package folder name
  (`contract_review/extraction.py`, `load_package`).
- `requirement_id` — the checklist row, `CC-01` through `CC-18`, from
  `References/Reference_Checklist.csv`.

Every applicable and non-applicable requirement gets a row, so the row count is
packages x requirements. The development run is 6 packages x 18 requirements =
108 rows in both CSVs.

## Columns that look alike across files

This is the part that trips people up. The same value is named differently in
each file:

| Meaning | `submission.csv` | `evidence_trace.csv` | `findings_report.json` |
| --- | --- | --- | --- |
| The quote pulled from the contract | `draft_evidence` | `draft_evidence_quote` | `contract_evidence.draft_quote` |
| Where that quote lives | `draft_location` (one sentence) | `evidence_file`, `evidence_pages`, `evidence_line_numbers`, `evidence_line_ids` (split into parts) | `contract_evidence.lines[]` (one object per line) |
| Decision confidence | `confidence` (0.00–1.00) | `model_confidence_percent` (0–100) | `decision.confidence` and `confidence_factors.model_confidence` (0.00–1.00) |
| The rule that was applied | `reference_evidence` | not carried | `criteria.challenge_reference_rule` |

Two naming traps worth calling out:

- **`model_confidence_percent` is not the model's raw confidence.** It is
  `confidence * 100`, and `confidence` is already a composite of the model's
  self-reported number and the knowledge base retrieval score. Same for
  `confidence_factors.model_confidence` in the JSON. The raw model number is
  never written to disk. See [Confidence](#the-three-percentages) below.
- **`draft_` does not mean unfinished.** It means "the document under review",
  as opposed to `reference_`, which means "the authority being compared
  against". Every `draft_*` / `reference_*` pair is the two sides of one
  comparison.

## Concepts shared by all the finding files

### Applicability vs label

Two independent decisions, and both must be read together:

- `applicability_decision` — `APPLIES` or `DOES_NOT_APPLY`. Does this
  requirement bind this project at all? Decided deterministically from
  `Project_Metadata.json` by `contract_review/applicability.py`, not by the
  model.
- `predicted_label` — `FLAG` or `NO_FLAG`. Does the contract deviate from the
  requirement?

`DOES_NOT_APPLY` always forces `NO_FLAG`. So `NO_FLAG` on its own is ambiguous:
it means either "checked and compliant" or "never checked because it does not
apply". The development run splits 64 / 16 between those two cases. Filter on
`applicability_decision == APPLIES` before you read `NO_FLAG` as compliance.

### Severity

Challenge taxonomy only: `Critical`, `High`, `Medium`, `Low`, `Info`.

`NO_FLAG` is always `Info`, which means `Info` is the "nothing to report" value
rather than a low-grade finding. For a `FLAG`, the checklist's own
`Severity_Guidance` column wins over whatever the model proposed, because the
model drifts between adjacent levels (`contract_review/pipeline.py`,
`_clean_severity`).

### The three percentages

`evidence_trace.csv` carries three different percentages. They measure
unrelated things and a run can be high on one and low on another:

| Column | Range | Answers |
| --- | --- | --- |
| `evidence_match_percent` | 0–100 | Is the quote really in the contract at the cited lines? Pure text fidelity, computed by `contract_review/evidence.py`. |
| `rag_retrieval_score_percent` | 0–100 | How well did the Bedrock knowledge base find reference material for this requirement? Affects confidence only. |
| `model_confidence_percent` | 0–100 | How sure is the composite decision? `0.7 * model self-report + 0.3 * retrieval factor`, times 100. |

A row can be 100% verbatim and still low confidence: the quote is definitely in
the document, but the judgement about it is uncertain. The reverse also
happens.

### What the reference sources are not

`rag_reference_sources` lists the knowledge base files retrieved for the
requirement. They are used **only** to compute the retrieval component of
confidence — they are not sent to the model and they are not the scoring
authority. The authority is the `Challenge_Reference_Rule` column of
`References/Reference_Checklist.csv`.

## Where the files are written

- CLI: `--out <dir>`, default `output/`. See `contract_review/cli.py`.
- API: the project's output directory, one per project, served by
  `dora_api/main.py` and listed in the workspace UI.

The committed `output/dev/` and `output/validation/` folders currently hold only
the two CSVs; they predate the JSON report being added to the CLI.
