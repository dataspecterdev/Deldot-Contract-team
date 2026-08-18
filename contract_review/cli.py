"""Command line entry point.

Examples
--------
Run one development package and score it::

    python -m contract_review.cli --package Contract_Clause_Risk_Flagging/Development/Pine_Grove --score

Run every development package::

    python -m contract_review.cli --set development --score

Run the unlabeled validation packages::

    python -m contract_review.cli --set validation --out output/validation
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import reporting, scoring
from .bedrock_client import BedrockClient
from .config import BEDROCK, DEVELOPMENT_DIR, OUTPUT_DIR, VALIDATION_DIR
from .extraction import discover_packages
from .json_report import write_json_report
from .models import ContractPackage, Finding
from .pipeline import ReviewPipeline


def _resolve_packages(args: argparse.Namespace) -> list[Path]:
    if args.package:
        return [Path(p) for p in args.package]
    if args.set == "development":
        return discover_packages(DEVELOPMENT_DIR)
    if args.set == "validation":
        return discover_packages(VALIDATION_DIR)
    return discover_packages(DEVELOPMENT_DIR) + discover_packages(VALIDATION_DIR)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="contract_review",
        description="Flag missing, modified, conflicting or non-standard contract provisions.",
    )
    parser.add_argument(
        "--package",
        action="append",
        help="Path to a single package directory. Repeatable.",
    )
    parser.add_argument(
        "--set",
        choices=("development", "validation", "all"),
        default="development",
        help="Which bundled package set to run when --package is not given.",
    )
    parser.add_argument("--out", default=str(OUTPUT_DIR), help="Output directory.")
    parser.add_argument(
        "--requirement",
        action="append",
        help="Limit the run to specific requirement ids, e.g. --requirement CC-02.",
    )
    parser.add_argument("--workers", type=int, default=4, help="Parallel requirement analyses.")
    parser.add_argument("--model-id", default=None, help="Override the Bedrock model id.")
    parser.add_argument("--kb-id", default=None, help="Override the knowledge base id.")
    parser.add_argument(
        "--score",
        action="store_true",
        help="Score the run against Development_Labels.csv.",
    )
    args = parser.parse_args(argv)

    packages = _resolve_packages(args)
    if not packages:
        parser.error("No packages found. Pass --package or check the challenge directories.")

    config = BEDROCK
    if args.model_id or args.kb_id:
        from dataclasses import replace

        config = replace(
            config,
            model_id=args.model_id or config.model_id,
            knowledge_base_id=args.kb_id or config.knowledge_base_id,
        )

    from .checklist import load_requirements

    requirements = list(load_requirements())
    if args.requirement:
        wanted = {r.strip().upper() for r in args.requirement}
        requirements = [r for r in requirements if r.requirement_id.upper() in wanted]
        if not requirements:
            parser.error(f"No requirements matched {sorted(wanted)}")

    print(f"model : {config.model_id}")
    print(f"kb    : {config.knowledge_base_id} ({config.region})")
    print(f"packages: {', '.join(p.name for p in packages)}")
    print(f"requirements: {len(requirements)}")
    print()

    pipeline = ReviewPipeline(
        client=BedrockClient(config),
        requirements=requirements,
        max_workers=args.workers,
        progress=lambda message: print(message, flush=True),
    )

    all_findings: list[Finding] = []
    package_map: dict[str, ContractPackage] = {}
    for directory in packages:
        result = pipeline.run_package(directory)
        all_findings.extend(result.findings)
        package_map[result.package.package_id] = result.package
        print()

    out_dir = Path(args.out)
    submission_path = reporting.write_submission(all_findings, out_dir / "submission.csv")
    trace_path = reporting.write_evidence_trace(all_findings, package_map, out_dir / "evidence_trace.csv")
    json_path = write_json_report(all_findings, package_map, out_dir / "findings_report.json")

    print(reporting.summarize(all_findings))
    print()
    print(f"submission     -> {submission_path}")
    print(f"evidence trace -> {trace_path}")
    print(f"findings JSON  -> {json_path}")
    print(
        f"tokens: {pipeline.client.input_tokens:,} in / {pipeline.client.output_tokens:,} out"
    )

    if args.score:
        print()
        print("=" * 78)
        print(scoring.score(all_findings).report())

    return 0


if __name__ == "__main__":
    sys.exit(main())
