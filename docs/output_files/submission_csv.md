# `submission.csv`

The deliverable file. One row per package x requirement pair, including
requirements that do not apply.

The column set and column **order** are not chosen by the code — they are read at
runtime from `Contract_Clause_Risk_Flagging/Submission/Submission_Schema.csv`
(`contract_review/checklist.py`, `submission_fields`). Rows are sorted by
`document_id`, then `requirement_id`. Written by
`contract_review/reporting.py`, `write_submission`.

Nothing in this file carries page or line numbers in machine-readable form. If
you need to programmatically re-open the source PDF, use
[`evidence_trace.csv`](evidence_trace_csv.md) instead.

## Columns

### `document_id`

The contract package this row is about. Taken from `package_id` in the package's
`Project_Metadata.json`, e.g. `DEV-HARBOR-CROSSING`. If that key is missing, the
package folder name is used instead.

### `requirement_id`

The checklist requirement being tested, `CC-01` to `CC-18`, from
`References/Reference_Checklist.csv`.

### `applicability_decision`

`APPLIES` or `DOES_NOT_APPLY`. Whether the requirement binds this project.

Decided deterministically from project metadata by
`contract_review/applicability.py` before any model call. The model does not get
a vote here, which is why this column is reliable on its own.

### `applicability_reason`

One sentence on why it applies or does not, grounded in the project metadata and
the checklist's `Applicability_Rule`. Example: "Project metadata marks this a
federal-aid contract funded under Title 23, so FHWA-1273 incorporation applies."

Not the same as `explanation` — see [Three prose columns](#three-prose-columns-that-are-easy-to-confuse).

### `predicted_label`

`FLAG` or `NO_FLAG`. Whether the contract deviates from the requirement.

`DOES_NOT_APPLY` rows are always `NO_FLAG`. Read this column together with
`applicability_decision`; `NO_FLAG` alone does not distinguish "compliant" from
"not applicable".

### `severity`

`Critical`, `High`, `Medium`, `Low`, or `Info`. Challenge taxonomy only.

`Info` is reserved for `NO_FLAG` rows, so it means "no finding" rather than "a
small finding". For `FLAG` rows the checklist's `Severity_Guidance` value
overrides the model's choice.

### `governing_document`

The package document that controls this requirement after precedence and
addendum resolution — the file whose text was treated as authoritative.

Resolved by `contract_review/precedence.py`:

1. A later addendum that explicitly revises the named provision governs it.
2. Otherwise, among documents that actually discuss the provision, the highest
   ranked under the DelDOT 105.6 order of precedence wins.
3. If nothing addresses it, the proposal is named, because that is where an
   omission would show.

This is **not** the same as `evidence_file` in the evidence trace. This column
says which document *should* control; `evidence_file` says where the quoted text
was *found*. They differ in 3 of the 108 development rows, which is exactly the
signal you want when a clause turns up somewhere other than where it belongs.

### `draft_location`

Human-readable location of the evidence inside the reviewed package, as one
string:

```
Proposal_and_General_Notices.pdf, p1, line 12 (section "Federal requirements")
```

Built by `contract_review/evidence.py`, `_format_location` from the lines that
were actually verified, so it describes the real file rather than the model's
description of it. Collapses consecutive lines into a range (`lines 13-15`) and
joins multiple files with `; `. If nothing could be located, the model's own
free-text guess is used as a fallback.

Empty for `DOES_NOT_APPLY` rows.

### `draft_evidence`

The quote from the reviewed package that supports the decision. "Draft" here
means the document under review, not an unfinished document.

Same value as `draft_evidence_quote` in the evidence trace and
`contract_evidence.draft_quote` in the JSON report. Whether the quote is
genuinely present in the PDF is not visible in this file — that is
`evidence_match_percent` in the evidence trace.

Empty for `DOES_NOT_APPLY` rows.

### `reference_id`

The reference requirement ID. In this implementation it is always set to the
same value as `requirement_id` (verified across all 108 development rows).

The schema keeps the two separate so that a submission could compare a row
against a different reference than the one that named it; this pipeline never
does, so treat the column as a required duplicate rather than as information.

### `reference_location`

Where the requirement lives in the authority, e.g.
`FHWA-1273, Section I. General, Paragraph 1 (CC-01)`. Falls back to
`<Reference_Source> - <Section>` from the checklist when the model does not
supply one.

Contrast with `draft_location`, which points into the contract being reviewed.
`reference_*` is the authority side of the comparison, `draft_*` is the contract
side.

### `reference_evidence`

The requirement text used for the comparison — the checklist's
`Challenge_Reference_Rule`, which is the scoring authority for the whole
pipeline.

Contrast with `draft_evidence`: `reference_evidence` is what the contract was
*supposed* to say, `draft_evidence` is what it *does* say.

### `explanation`

Why the finding is material, benign, superseded, or not applicable. The model's
reasoning about the comparison.

Distinct from `applicability_reason`, which only covers whether the requirement
applies at all.

### `confidence`

`0.00` to `1.00`, two decimals. A composite, not the model's raw self-report:

```
confidence = 0.7 * model_self_reported + 0.3 * (retrieval_score / 100)
```

Computed in `contract_review/pipeline.py`. A strong knowledge base match lifts
it, weak or missing retrieval tempers it. The raw model number is not preserved
anywhere in the outputs.

Fixed values worth recognising: `0.95` for `DOES_NOT_APPLY` rows, `0.00` when
the model call failed and the row is a placeholder (check `notes` in the
evidence trace for `analysis error:`).

`model_confidence_percent` in the evidence trace is this same number x 100,
despite the name.

### `recommended_human_action`

What a reviewer should do: review, confirm, or no action. Deliberately never a
legal conclusion. Defaults to "Review and confirm with contract
administration." for flags and "No action required." otherwise.

## Three prose columns that are easy to confuse

| Column | Scope | Written by |
| --- | --- | --- |
| `applicability_reason` | Only whether the requirement binds this project | The deterministic applicability engine |
| `explanation` | Whether the clause is a problem, and why | The model |
| `recommended_human_action` | What the reviewer should do next | The model, with a default |

The evidence trace adds a fourth, `notes`, which is neither legal reasoning nor
advice — it records how the evidence was located.

## Reading tips

- Real findings: `applicability_decision == APPLIES` and
  `predicted_label == FLAG`. 28 of 108 rows in the development run.
- Sort by `severity` then `confidence` descending to triage.
- To check a flag against the PDF, join to `evidence_trace.csv` on
  `document_id` + `requirement_id`.
