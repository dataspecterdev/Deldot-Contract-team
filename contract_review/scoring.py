"""Score a run against Development_Labels.csv using the challenge metrics."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from .config import DEVELOPMENT_LABELS, FLAG
from .models import Finding


@dataclass
class Score:
    applicability_correct: int = 0
    applicability_total: int = 0

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0

    severity_correct: int = 0
    severity_total: int = 0

    evidence_located: int = 0
    evidence_total: int = 0

    mismatches: list[str] = field(default_factory=list)

    @property
    def applicability_accuracy(self) -> float:
        return self.applicability_correct / self.applicability_total if self.applicability_total else 0.0

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        if not (self.precision + self.recall):
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)

    @property
    def label_accuracy(self) -> float:
        total = self.true_positive + self.false_positive + self.false_negative + self.true_negative
        return (self.true_positive + self.true_negative) / total if total else 0.0

    @property
    def severity_agreement(self) -> float:
        return self.severity_correct / self.severity_total if self.severity_total else 0.0

    def report(self) -> str:
        lines = [
            "Applicability accuracy : "
            f"{self.applicability_accuracy:6.1%}  ({self.applicability_correct}/{self.applicability_total})",
            "Label accuracy         : "
            f"{self.label_accuracy:6.1%}  (TP {self.true_positive}, TN {self.true_negative}, "
            f"FP {self.false_positive}, FN {self.false_negative})",
            f"Flag precision         : {self.precision:6.1%}",
            f"Flag recall            : {self.recall:6.1%}",
            f"Flag F1                : {self.f1:6.1%}",
            "Severity agreement     : "
            f"{self.severity_agreement:6.1%}  ({self.severity_correct}/{self.severity_total}) on matched flags",
            "Evidence located       : "
            f"{self.evidence_located}/{self.evidence_total} applicable rows cite a package line",
        ]
        if self.mismatches:
            lines.append("")
            lines.append(f"Mismatches ({len(self.mismatches)}):")
            lines.extend(f"  {item}" for item in self.mismatches)
        return "\n".join(lines)


def load_labels(path: Path | None = None) -> dict[tuple[str, str], dict[str, str]]:
    csv_path = Path(path) if path else DEVELOPMENT_LABELS
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        return {
            ((row.get("Package_ID") or "").strip(), (row.get("Requirement_ID") or "").strip()): row
            for row in csv.DictReader(handle)
        }


def score(findings: list[Finding], labels_path: Path | None = None) -> Score:
    labels = load_labels(labels_path)
    result = Score()

    for finding in sorted(findings, key=lambda f: (f.document_id, f.requirement_id)):
        key = (finding.document_id, finding.requirement_id)
        expected = labels.get(key)
        if expected is None:
            continue

        want_applicability = (expected.get("Expected_Applicability") or "").strip()
        want_label = (expected.get("Expected_Label") or "").strip()
        want_severity = (expected.get("Expected_Severity") or "").strip()
        rationale = (expected.get("Rationale") or "").strip()

        result.applicability_total += 1
        if finding.applicability_decision == want_applicability:
            result.applicability_correct += 1
        else:
            result.mismatches.append(
                f"{finding.document_id} {finding.requirement_id} applicability: "
                f"expected {want_applicability}, got {finding.applicability_decision}"
            )

        got_flag = finding.predicted_label == FLAG
        want_flag = want_label == FLAG
        if want_flag and got_flag:
            result.true_positive += 1
        elif not want_flag and got_flag:
            result.false_positive += 1
            result.mismatches.append(
                f"{finding.document_id} {finding.requirement_id} FALSE POSITIVE "
                f"(expected NO_FLAG - {rationale}) -> {finding.explanation[:110]}"
            )
        elif want_flag and not got_flag:
            result.false_negative += 1
            result.mismatches.append(
                f"{finding.document_id} {finding.requirement_id} MISSED FLAG "
                f"(expected {want_severity} - {rationale}) -> {finding.explanation[:110]}"
            )
        else:
            result.true_negative += 1

        if want_flag and got_flag:
            result.severity_total += 1
            if finding.severity == want_severity:
                result.severity_correct += 1
            else:
                result.mismatches.append(
                    f"{finding.document_id} {finding.requirement_id} severity: "
                    f"expected {want_severity}, got {finding.severity}"
                )

        if finding.applicability_decision == "APPLIES":
            result.evidence_total += 1
            if finding.cited_line_ids:
                result.evidence_located += 1

    return result
