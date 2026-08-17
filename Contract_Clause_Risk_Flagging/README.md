# Contract Clause Risk Flagging

## Objective
Develop an evidence-grounded AI solution that reviews transportation contract packages against the supplied reference checklist and identifies missing, modified, conflicting, outdated, or non-standard provisions for human review.

## Package contents
- `References/Reference_Checklist.csv` - challenge reference requirements and applicability rules.
- `Development/` - labeled development packages for solution testing and calibration.
- `Validation/` - unlabeled packages for independent solution validation.
- `Submission/Submission_Schema.csv` - required result format.
- `Evaluation/` - scoring criteria and severity guidance.

## Core evaluation behaviors
Solutions are evaluated on:
- applicability determination;
- cross-document precedence and Addendum handling;
- semantic deviation detection without unnecessary false positives;
- evidence-grounded findings.

## Submission expectation
Return one structured decision for each contract-package and requirement combination using the supplied submission schema.

The reference checklist is the scoring authority for this challenge. Findings are decision-support outputs and should remain traceable to contract-package evidence and subject to human review.
