# `evidence_trace.csv`

The cross-check companion to [`submission.csv`](submission_csv.md). Same rows,
same order, keyed by the same `document_id` + `requirement_id` pair — but instead
of the submission's prose it carries resolved file, page and line numbers plus
three quality percentages, so a reviewer can open the PDF and confirm each
finding rather than trusting it.

Columns are fixed in code as `EVIDENCE_TRACE_FIELDS` in
`contract_review/reporting.py`; written by `write_evidence_trace`.

Six columns are copied straight from the submission (`document_id`,
`requirement_id`, `predicted_label`, `severity`, `applicability_decision`,
`governing_document`) so this file stands alone during review. Their meaning is
identical — see the [submission reference](submission_csv.md). The remaining
twelve are documented below.

## Location columns

These four all describe the same set of cited lines at different granularities.
All are empty when nothing could be located.

### `evidence_file`

The file(s) where the quoted text was actually found. Deduplicated and sorted,
joined with `; ` when a finding spans more than one PDF.

**Not the same as `governing_document`.** `governing_document` is the document
that *controls* the provision after precedence and addendum resolution;
`evidence_file` is where the text was *found*. When they disagree, the clause is
sitting somewhere other than where the precedence rules expect it — 3 of the 108
development rows are like this, and they are worth a look.

### `evidence_pages`

1-based page numbers, deduplicated and sorted, comma-separated: `1` or `4, 5`.

### `evidence_line_numbers`

1-based line numbers **within their page**, comma-separated: `13, 14, 15`.

Two things to watch:

- These numbers are only meaningful alongside `evidence_pages`. Line 12 of page
  1 and line 12 of page 4 both appear here as `12`.
- Unlike `evidence_pages` and `evidence_file`, this list is **not**
  deduplicated and stays in line order, so its length can differ from the page
  list's. Use `evidence_line_ids` when you need an unambiguous pairing.

### `evidence_line_ids`

The full provenance handles, one per cited line, in the form
`<file>|p<page>|L<line>`:

```
Special_Provisions.pdf|p2|L14
```

Joined with `; ` rather than `,` because the ids themselves contain `|` and
often sit next to commas in text. This is the canonical, unambiguous location —
the other three location columns are conveniences derived from it.

These are the same ids the model is shown in its prompt and asked to echo back,
which is what makes the citation checkable. Ids the model invents are dropped
before they reach this file and recorded in `notes`.

## Content columns

### `evidence_section_heading`

The section heading in force at the cited lines, e.g. `Federal requirements`.
The first non-empty heading among the cited lines, so a multi-line citation
reports one heading, not all of them.

### `draft_evidence_quote`

Identical value to `draft_evidence` in the submission and
`contract_evidence.draft_quote` in the JSON report. Renamed here to make it
obvious it is a quote whose fidelity is being reported by the next column.

## The three percentages

Different questions, different answers. This is the most common
misreading of the file, so treat them separately.

### `evidence_match_percent`

`0.0`–`100.0`. **Is the quote actually there?** How much of
`draft_evidence_quote` is genuinely present at the cited lines, computed by
`contract_review/evidence.py`:

- `100.0` — the normalised quote is contained verbatim in the cited lines.
- Multi-part quotes (split on `[...]`, `…`, ` / `, ` | `) are verified fragment
  by fragment, and the score is the fraction of fragments found verbatim.
- Otherwise a `difflib` similarity ratio.
- Below 60% similarity, the pipeline searches the rest of the package for a
  better home for the quote. If it finds one, the location columns are rewritten
  to point there and `notes` says so.
- `0.0` with lines cited means lines were given but no quote.

Comparison is normalisation-tolerant: case, whitespace runs, curly quotes and
en/em dashes are all folded first, so `100.0` means "verbatim modulo
typography", not "byte-identical".

### `rag_retrieval_score_percent`

`0.0`–`100.0`. **How well did the knowledge base match the requirement?** The
highest Bedrock retrieval score among the chunks returned for this requirement,
x 100.

This is a property of the *requirement*, not of the contract — the retrieval is
cached per requirement and reused across packages, so the same `CC-##` shows the
same value in every package. It contributes 30% of the confidence and nothing
else. Low values are not findings.

### `model_confidence_percent`

`0`–`100`, no decimals. **How sure is the decision?**

The name is misleading: this is the composite confidence from the submission's
`confidence` column x 100, which already blends the model's self-report with the
retrieval score (`0.7 * model + 0.3 * retrieval`). The model's unadjusted number
is not written to any output file.

### Reading them together

| Pattern | Interpretation |
| --- | --- |
| High match, high confidence | Solid finding, quote verified. |
| High match, low confidence | The text is definitely there; the judgement about it is uncertain. Review the reasoning, not the citation. |
| Low match, high confidence | The model is sure but paraphrased. Check the quote against the PDF first. |
| `0` confidence | The model call failed; `notes` starts with `analysis error:`. Not a compliance result. |

## Provenance and status columns

### `rag_reference_sources`

Knowledge base source file names retrieved for this requirement, deduplicated in
first-seen order, joined with `; `, e.g.
`CC-01_FHWA-1273.txt; CC-09_Buy_America_BABA.txt`.

These are **confidence inputs only**. They are not sent to the model prompt and
they are not the scoring authority — the checklist's `Challenge_Reference_Rule`
is. A source appearing here does not mean the finding was judged against it.

### `verification_status`

A derived trust label for the *citation*, deliberately independent of the
model's opinion. Computed by `_verification_status` in
`contract_review/reporting.py` from `applicability_decision` and
`evidence_match_percent` only:

| Value | Condition | What to do |
| --- | --- | --- |
| `NOT_APPLICABLE_NO_EVIDENCE_NEEDED` | `DOES_NOT_APPLY` | Nothing. No evidence was expected. |
| `UNLOCATED_REVIEW_MANUALLY` | No usable line ids | Find the clause by hand; the citation failed. |
| `VERBATIM_MATCH` | match >= 99% | Trust the quote. |
| `CLOSE_MATCH` | match >= 75% | Quote is close; skim the cited lines. |
| `WEAK_MATCH_REVIEW` | match > 0% | Treat the quote as a paraphrase. |
| `LINES_CITED_NO_QUOTE` | match == 0 with lines cited | Lines are pointed at, nothing was quoted. |

It says nothing about whether the *finding* is correct — only whether the
evidence behind it can be located and read. The development run is 92
`VERBATIM_MATCH` and 16 `NOT_APPLICABLE_NO_EVIDENCE_NEEDED`.

### `notes`

Pipeline diagnostics about how the evidence was resolved, joined with `; `.
Usually empty. Known messages:

| Note | Meaning |
| --- | --- |
| `unknown line id cited: <id>` | The model invented a line id; it was dropped. |
| `located by text search; model cited no valid line id` | Location came from searching for the quote, not from a citation. |
| `quoted evidence matched better outside the cited lines` | The quote was found elsewhere; location columns point at the better match. |
| `multi-part quote; every fragment verified verbatim at the cited lines` | Stitched quote, all fragments confirmed. |
| `multi-part quote; N% of fragments verified verbatim` | Stitched quote, partial confirmation. |
| `applicability excluded by project metadata` | Standard note on `DOES_NOT_APPLY` rows. |
| `analysis error: ...` | The model call failed; the row is a `NO_FLAG` placeholder with confidence 0. |

`notes` is about the mechanics of evidence gathering. It is not
`applicability_reason` (why the requirement applies), `explanation` (why the
clause matters), or `recommended_human_action` (what to do) — all three of those
live in the submission.

## Not carried here

Present in the submission but deliberately absent: `applicability_reason`,
`draft_location`, `reference_id`, `reference_location`, `reference_evidence`,
`explanation`, `recommended_human_action`. Join on
`document_id` + `requirement_id` if you need them.

`Line` objects also track `global_line`, `char_start` and `char_end`
(`contract_review/models.py`), but no output file exposes them.
