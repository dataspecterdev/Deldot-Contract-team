"""Bridge between the DORA API and the contract_review pipeline.

This module sets up the contract package structure from uploaded PDFs, runs the
review pipeline, and writes outputs to the project's output directory.
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

from . import project_manager


def _prepare_package(project_id: str) -> Path:
    """Build a contract package directory from uploaded PDFs.

    The contract_review pipeline expects:
      project_dir/
        Project_Metadata.json
        Document_Index.csv
        Docs/
          *.pdf
    """
    upload_dir = project_manager.get_upload_dir(project_id)
    output_dir = project_manager.get_output_dir(project_id)

    # Create a temporary package directory inside outputs
    package_dir = output_dir / "_package"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir()
    docs_dir = package_dir / "Docs"
    docs_dir.mkdir()

    # Copy PDFs to Docs/
    pdfs = list(upload_dir.glob("*.pdf"))
    if not pdfs:
        raise ValueError("No PDF files uploaded. Upload at least one contract PDF.")

    doc_rows: list[dict[str, str]] = []
    for pdf in sorted(pdfs):
        shutil.copy2(pdf, docs_dir / pdf.name)
        # Infer document type from filename
        doc_type = pdf.stem.replace("_", " ")
        doc_rows.append({
            "File_Name": pdf.name,
            "Document_Type": doc_type,
            "Package_Status": "Current",
        })

    # Write Document_Index.csv
    index_path = package_dir / "Document_Index.csv"
    with index_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["File_Name", "Document_Type", "Package_Status"])
        writer.writeheader()
        writer.writerows(doc_rows)

    # Write a default Project_Metadata.json
    # Users can customize this later; for now, provide sensible defaults
    meta = _read_or_create_metadata(project_id, pdfs)
    meta_path = package_dir / "Project_Metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return package_dir


def _read_or_create_metadata(project_id: str, pdfs: list[Path]) -> dict[str, Any]:
    """Check if user uploaded a metadata JSON, otherwise create defaults."""
    upload_dir = project_manager.get_upload_dir(project_id)

    # Check if the user uploaded a Project_Metadata.json
    user_meta = upload_dir / "Project_Metadata.json"
    if user_meta.exists():
        return json.loads(user_meta.read_text(encoding="utf-8"))

    # Also check for .json files alongside PDFs
    json_files = list(upload_dir.glob("*.json"))
    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            if "package_id" in data or "project_title" in data:
                return data
        except (json.JSONDecodeError, OSError):
            continue

    # Default metadata — conservative assumptions
    project_meta = project_manager.get_project(project_id)
    return {
        "package_id": project_meta["name"].replace(" ", "_"),
        "project_title": project_meta["name"],
        "federal_aid": True,
        "buy_america_baba_applicable": True,
        "assumed_contract_value": 5000000,
        "issued_addenda": [
            pdf.stem for pdf in pdfs if "addendum" in pdf.stem.lower()
        ],
        "subcontracting_planned": True,
        "claim_event": False,
        "delay_event": False,
        "changed_work_event": False,
    }


def run_analysis(project_id: str, progress_callback=None) -> dict[str, Any]:
    """Run the contract_review pipeline on a project's uploaded PDFs.

    Returns a summary dict with output file paths.
    """
    from contract_review.bedrock_client import BedrockClient
    from contract_review.config import BEDROCK
    from contract_review.json_report import write_json_report
    from contract_review.models import ContractPackage, Finding
    from contract_review.pipeline import ReviewPipeline
    from contract_review import reporting

    project_manager.update_status(project_id, "analyzing")

    try:
        package_dir = _prepare_package(project_id)
        output_dir = project_manager.get_output_dir(project_id)

        def _progress(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        client = BedrockClient()
        pipeline = ReviewPipeline(
            client=client,
            max_workers=4,
            progress=_progress,
        )

        result = pipeline.run_package(package_dir)

        # Write outputs
        submission_path = reporting.write_submission(
            result.findings, output_dir / "submission.csv"
        )
        trace_path = reporting.write_evidence_trace(
            result.findings,
            {result.package.package_id: result.package},
            output_dir / "evidence_trace.csv",
        )
        json_path = write_json_report(
            result.findings,
            {result.package.package_id: result.package},
            output_dir / "findings_report.json",
        )

        # Write a run summary
        summary = {
            "package_id": result.package.package_id,
            "total_findings": len(result.findings),
            "flags": sum(1 for f in result.findings if f.predicted_label == "FLAG"),
            "compliant": sum(1 for f in result.findings if f.predicted_label == "NO_FLAG"),
            "tokens_in": client.input_tokens,
            "tokens_out": client.output_tokens,
            "output_files": [
                submission_path.name,
                trace_path.name,
                json_path.name,
            ],
        }
        (output_dir / "run_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

        # Clean up the temporary package directory
        shutil.rmtree(package_dir, ignore_errors=True)

        project_manager.update_status(project_id, "complete")
        return summary

    except Exception as exc:
        project_manager.update_status(project_id, "error", str(exc))
        raise
