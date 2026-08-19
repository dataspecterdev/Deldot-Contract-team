# Case Study: DelDOT Contract Clause Risk Flagging

## Overview
We built an evidence-grounded AI pipeline that reviews DelDOT transportation contract packages against the challenge reference checklist (CC-01..CC-18). The goal: for every package × requirement combination, return a single, auditable decision (FLAG / NO_FLAG) grounded in extracted evidence. Key constraints were high precision with minimal false positives, traceable evidence locations, and clear precedence handling across addenda.

## Top-level directories (brief)
- Contract_Clause_Risk_Flagging/ – Main project: code, labeled Development packages, Validation and Submission schemas, and the frozen scorer. Contains the implementation of the four-layer gate (applicability → precedence → detectors → LLM adjudicator).
- docs/ – Sphinx documentation scaffold and build helpers.
- .github/ – CI and workflow configuration.
- LICENSE, README.md – license and this overview.

## The problem we solved (brief)
Transportation contract packages quote, paraphrase, and reference clauses in many formats (cover pages, addenda, shorthand, spelled numbers vs digits, months vs years), which causes naive semantic matching and retrieval to produce false positives and misses. Our main challenges were:
- Precedence & addenda: identifying which clause governs when multiple documents quote or reprint clauses.
- Shorthand & ambiguity: short references like “the stated period” or “required proof of insurance” that match checklist language but carry no concrete numbers or process.
- Cross-document retrieval noise: RAG can surface the correct clause but also irrelevant cover-page text that confuses the model.
- Unit/format variance: numbers spelled out vs digits, months vs years, and parity like “36 months” vs “3 years”.

## How we addressed it (high level)
- Four-layer gate: metadata applicability rules and precedence computations run before any model call; deterministic detectors settle obvious matches and only uncertain clauses reach the LLM.
- Deterministic detectors: invariant tests per requirement to avoid unnecessary LLM calls and prevent over-flagging.
- Hybrid RAG policy: use RAG retrieval only when evidence contains a concrete weakening (e.g., explicit "80%"), otherwise prefer rule-based NO_FLAG.
- Normalizers: standardize units and numeric forms prior to comparison.

If you want, I can (1) expand the README with a short example workflow and commands to run the frozen scorer, or (2) add an explicit “Branches” section listing git branches and what they contain — tell me which you prefer.
