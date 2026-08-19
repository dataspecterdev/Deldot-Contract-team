# `findings_report.json`

The primary human-readable output. Same findings as the two CSVs, but nested by
package and enriched with two things neither CSV carries in full: the **verbatim
contract lines** behind each finding, and the **checklist criteria** it was judged
against.

Standalone by design — a reviewer needs neither CSV to use it. Built by
`contract_review/json_report.py`, `build_json_report`. Packages are sorted by
`package_id`, findings within a package by `requirement_id`.

## Shape

```
{
  "report_metadata": { ... },        // provenance of the report itself
  "summary": { ... },                // totals across all packages
  "packages": [
    {
      "package_id": "...",
      "summary": { ... },            // totals for this package only
      "findings": [
        {
          "requirement_id": "...",
          "document_id": "...",
          "decision":            { ... },   // what was concluded
          "criteria":            { ... },   // what it was judged against
          "contract_evidence":   { ... },   // what the contract actually says
          "confidence_factors":  { ... }    // why the confidence is what it is
        }
      ]
    }
  ]
}
```

The four blocks inside a finding are the useful division: conclusion, rule,
evidence, and the arithmetic behind the confidence.

## `report_metadata`

Fixed provenance text, not derived from the findings.

| Field | Meaning |
| --- | --- |
| `generated_at` | UTC ISO-8601 timestamp of report generation. |
| `report_type` | Always `contract_clause_risk_flagging`. |
| `scoring_authority` | States that `Reference_Checklist.csv` → `Challenge_Reference_Rule` is the authority. |
| `sources_role` | States that knowledge base sources feed confidence only. |
| `description` | Prose restating both of the above. |

The last two exist to prevent a specific misreading: retrieved knowledge base
text is a confidence input, never the yardstick.

## `summary` vs `packages[].summary`

Same field names, different scope. Read the path, not just the key.

Top-level `summary` — the whole run:

| Field | Meaning |
| --- | --- |
| `total_packages` | Packages in the report. |
| `total_requirements_checked` | Total findings across all packages (packages x requirements). |
| `total_flags` | `FLAG` rows across all packages. |
| `total_compliant` | Everything else, i.e. `total_requirements_checked - total_flags`. |

Per-package `packages[].summary` — one package:

| Field | Meaning |
| --- | --- |
| `total_requirements_checked` | Findings for this package. Same key as the top-level field, one package's worth. |
| `flags` | `FLAG` count for this package. Note the shorter name: `flags` is per-package, `total_flags` is run-wide. |
| `compliant` | `NO_FLAG` count for this package. |
| `flag_ids` | The `CC-##` ids that flagged, so you can jump straight to them. |

`compliant` and `total_compliant` both count `NO_FLAG`, which includes
`DOES_NOT_APPLY` rows. They are not "checked and found clean" counts. Filter on
`decision.applicability` if that is what you need.

## `packages[].package_id`

Same value as `document_id` in the CSVs and as `document_id` on each finding
inside this package — it is repeated at the finding level so a single finding
object is self-contained when extracted.

## `findings[].decision`

What was concluded. Every field here also appears in `submission.csv` under a
slightly different name.

| Field | CSV equivalent | Notes |
| --- | --- | --- |
| `applicability` | `applicability_decision` | `APPLIES` / `DOES_NOT_APPLY`. Renamed because the surrounding `decision` block already implies it is a decision. |
| `applicability_reason` | same | Why it applies. From the deterministic engine. |
| `predicted_label` | same | `FLAG` / `NO_FLAG`. |
| `severity` | same | `Info` for all `NO_FLAG` rows. |
| `confidence` | `confidence` | `0.0`–`1.0`, the composite. |
| `explanation` | same | Why the clause is material, benign, superseded or not applicable. |
| `recommended_action` | `recommended_human_action` | Shortened name, identical value. |

`decision.confidence` and `confidence_factors.model_confidence` are the *same
number*, not a decision value and its input. See
[`confidence_factors`](#findingsconfidence_factors).

## `findings[].criteria`

The rule the finding was judged against, copied from the matching row of
`References/Reference_Checklist.csv`. This block is why the report is usable
without the checklist open beside it.

| Field | Checklist column | Meaning |
| --- | --- | --- |
| `requirement_id` | `Requirement_ID` | `CC-##`. |
| `requirement_name` | `Requirement_Name` | Short title, e.g. "Performance and payment bonds". |
| `reference_source` | `Reference_Source` | Which authority, e.g. `FHWA-1273`, `DelDOT 105.6`. |
| `section` | `Section` | Section within that authority. |
| `challenge_reference_rule` | `Challenge_Reference_Rule` | **The scoring authority.** The concrete rule, with the numbers that discriminate between similar sections. |
| `review_expectation` | `Review_Expectation` | What a reviewer is expected to check. |
| `severity_guidance` | `Severity_Guidance` | The severity the challenge prescribes for this requirement. |

Two pairs to keep straight:

- `challenge_reference_rule` vs `review_expectation` — the first is the binding
  rule text used for scoring; the second is guidance on how to review. Only the
  first decides `FLAG` / `NO_FLAG`.
- `severity_guidance` (here) vs `decision.severity` — the first is the
  prescribed severity for the requirement, the second is what this finding was
  assigned. For flags they normally match, because the guidance value overrides
  the model. For `NO_FLAG` they differ: `decision.severity` becomes `Info` while
  `severity_guidance` keeps saying what the requirement *would* rate.

All seven fields are empty strings if the `requirement_id` is not in the
checklist.

## `findings[].contract_evidence`

What the contract actually says.

| Field | Meaning |
| --- | --- |
| `governing_document` | The file that controls this provision after precedence / addendum resolution. Same as the CSV column. |
| `draft_location` | The one-line human-readable location. Same as `submission.csv`. |
| `draft_quote` | The quote from the contract. Same value as `draft_evidence` (submission) and `draft_evidence_quote` (trace). |
| `evidence_match_percent` | `0.0`–`100.0`, how much of `draft_quote` is verbatim at the cited lines. |
| `lines` | Array of the actual cited lines, one object each. Empty when nothing was located. |

`draft_location` is the prose form of the same information in `lines` — a summary
string versus the structured list. `lines` is the one to parse.

### `contract_evidence.lines[]`

| Field | Meaning |
| --- | --- |
| `file_name` | The PDF the line lives in. |
| `page` | 1-based page number. |
| `line_number` | 1-based line number **within that page**, not a document-wide counter. |
| `line_id` | `<file>\|p<page>\|L<line>` — the canonical handle, and the id the model cited. |
| `text` | The verbatim line content from the contract. |
| `section_heading` | Heading context for that line, `""` if none. |

`line_number` is the same value the trace calls `evidence_line_numbers`, split
per line and paired with its own `page`, which removes the page/line ambiguity
the CSV has. `line_id` here is one id per object, where the trace joins them all
into one `; `-separated cell.

`text` is what makes this the report to read: it is the contract's own words,
pulled from the extraction index rather than from the model, so it cannot be a
paraphrase. Compare it against `draft_quote` to see exactly what the model did
with it. `contract_evidence.lines` is unique to this file — neither CSV carries
line text.

## `findings[].confidence_factors`

The arithmetic behind the confidence, exposed so a low number can be explained.

| Field | Meaning |
| --- | --- |
| `model_confidence` | `0.0`–`1.0`. **Despite the name, the composite**, identical to `decision.confidence`. |
| `retrieval_score_percent` | `0.0`–`100.0`. Best knowledge base retrieval score for this requirement, x 100. |
| `evidence_match_percent` | `0.0`–`100.0`. Repeated from `contract_evidence` so all three numbers sit together. |
| `sources_used_for_confidence` | Knowledge base file names retrieved. Confidence inputs only, never the scoring authority. |

The naming here is the one real trap in the file. `model_confidence` reads like
the model's raw self-report but is `0.7 * raw + 0.3 * (retrieval_score / 100)`,
computed in `contract_review/pipeline.py`. The raw value is discarded and appears
in no output. So `model_confidence` and `retrieval_score_percent` are **not
independent** — the second is already folded into the first.

`evidence_match_percent` *is* independent of both: it measures quote fidelity and
plays no part in the confidence calculation.

## Not in this file

`reference_id`, `reference_location` and `reference_evidence` from the submission
have no direct equivalent. Their content is superseded by the richer `criteria`
block: `reference_evidence` is the same text as
`criteria.challenge_reference_rule`, and `reference_location` is
`criteria.reference_source` + `criteria.section`.

The evidence trace's `verification_status` and `notes` are also absent. If you
need the trust label or the diagnostics, use
[`evidence_trace.csv`](evidence_trace_csv.md).
