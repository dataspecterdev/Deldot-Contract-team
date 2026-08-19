"""Bridge between the DORA API and the contract_review pipeline.

Supports both single-package and multi-package uploads:
- If top-level subfolders contain PDFs (or a Project_Metadata.json), each is
  treated as a separate contract package and analyzed independently.
- If PDFs live directly in the upload root with no subfolder structure, they're
  treated as a single package.

Results are grouped by package_id in the JSON report and the submission CSV
contains rows from all packages.
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

from . import project_manager


def _sanitize_package_id(raw: str) -> str:
    """Sanitize package_id to be CSV-safe and human-readable.

    Strips commas, newlines, and excess whitespace that would break CSV output.
    Truncates to a reasonable length.
    """
    if not raw or not isinstance(raw, str):
        return "unknown_package"
    # Remove characters that break CSV
    cleaned = raw.replace(",", "").replace("\n", " ").replace("\r", "")
    # Collapse whitespace
    cleaned = " ".join(cleaned.split())
    # Replace spaces with underscores for IDs
    cleaned = cleaned.strip().replace(" ", "_")
    # Truncate to something reasonable (max 60 chars)
    if len(cleaned) > 60:
        cleaned = cleaned[:60]
    # If it's empty after cleaning, fallback
    return cleaned if cleaned else "unknown_package"


# ---------------------------------------------------------------------------
# Package detection
# ---------------------------------------------------------------------------

def _detect_packages(upload_dir: Path) -> list[Path]:
    """Detect separate contract packages within the uploads.

    Strategy:
    1. If any immediate child folder contains PDFs or a Project_Metadata.json,
       each such folder is a separate package.
    2. Otherwise the entire upload_dir is one package.
    """
    child_packages: list[Path] = []
    for child in sorted(upload_dir.iterdir()):
        if not child.is_dir():
            continue
        has_pdfs = any(child.rglob("*.pdf"))
        has_meta = (child / "Project_Metadata.json").exists()
        if has_pdfs or has_meta:
            child_packages.append(child)

    if child_packages:
        # Also check: are there loose PDFs at root level alongside folders?
        root_pdfs = [f for f in upload_dir.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]
        if root_pdfs:
            # Treat root-level PDFs as an additional unnamed package
            child_packages.insert(0, upload_dir)
        return child_packages

    # No subfolder structure — everything is one package
    return [upload_dir]


# ---------------------------------------------------------------------------
# Single package preparation
# ---------------------------------------------------------------------------

def _prepare_single_package(source_dir: Path, output_base: Path, package_name: str) -> Path:
    """Build a contract package directory from a source folder.

    The contract_review pipeline expects:
      package_dir/
        Project_Metadata.json
        Document_Index.csv
        Docs/
          *.pdf
    """
    package_dir = output_base / f"_pkg_{package_name}"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    docs_dir = package_dir / "Docs"
    docs_dir.mkdir()

    # Collect PDFs recursively from source
    pdfs = list(source_dir.rglob("*.pdf"))
    if not pdfs:
        return package_dir  # empty — will be skipped

    doc_rows: list[dict[str, str]] = []
    seen_names: dict[str, int] = {}
    for pdf in sorted(pdfs):
        dest_name = pdf.name
        if dest_name in seen_names:
            seen_names[dest_name] += 1
            parent_name = pdf.parent.name if pdf.parent != source_dir else ""
            if parent_name and parent_name != "Docs":
                dest_name = f"{parent_name}_{pdf.stem}{pdf.suffix}"
            else:
                dest_name = f"{pdf.stem}_{seen_names[pdf.name]}{pdf.suffix}"
        else:
            seen_names[dest_name] = 1

        shutil.copy2(pdf, docs_dir / dest_name)
        doc_type = pdf.stem.replace("_", " ")
        doc_rows.append({
            "File_Name": dest_name,
            "Document_Type": doc_type,
            "Package_Status": "Current",
        })

    # Write Document_Index.csv
    index_path = package_dir / "Document_Index.csv"
    with index_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["File_Name", "Document_Type", "Package_Status"])
        writer.writeheader()
        writer.writerows(doc_rows)

    # Write Project_Metadata.json
    meta = _find_or_create_metadata(source_dir, package_name, pdfs)
    (package_dir / "Project_Metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    return package_dir


def _find_or_create_metadata(source_dir: Path, package_name: str, pdfs: list[Path]) -> dict[str, Any]:
    """Look for a Project_Metadata.json in the source, otherwise create defaults."""
    # Direct metadata file
    meta_path = source_dir / "Project_Metadata.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data["package_id"] = _sanitize_package_id(data.get("package_id", package_name))
                return data
        except (json.JSONDecodeError, OSError):
            pass

    # Any JSON with package_id or project_title
    for jf in sorted(source_dir.rglob("*.json")):
        # Skip files that are clearly not metadata (too large, or named oddly)
        if jf.stat().st_size > 50000:
            continue
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            if isinstance(data, dict) and ("package_id" in data or "project_title" in data):
                data["package_id"] = _sanitize_package_id(data.get("package_id", package_name))
                return data
        except (json.JSONDecodeError, OSError):
            continue

    # Default metadata
    return {
        "package_id": _sanitize_package_id(package_name),
        "project_title": package_name.replace("_", " "),
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


# ---------------------------------------------------------------------------
# Main analysis runner
# ---------------------------------------------------------------------------

def run_analysis(project_id: str, model_id: str | None = None, progress_callback=None) -> dict[str, Any]:
    """Run the contract_review pipeline on uploaded PDFs.

    Detects multiple packages (subfolders) and runs each independently.
    Results are combined into unified output files with per-package grouping.
    """
    from contract_review.bedrock_client import BedrockClient
    from contract_review.config import BEDROCK
    from contract_review.json_report import write_json_report
    from contract_review.pdf_report import write_pdf_report
    from contract_review.models import ContractPackage, Finding
    from contract_review.pipeline import ReviewPipeline
    from contract_review import reporting
    from dataclasses import replace

    project_manager.update_status(project_id, "analyzing")

    try:
        upload_dir = project_manager.get_upload_dir(project_id)
        output_dir = project_manager.get_output_dir(project_id)

        def _progress(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        # Detect packages
        package_sources = _detect_packages(upload_dir)
        if not package_sources:
            raise ValueError("No PDF files found. Upload at least one contract PDF.")

        # Verify at least one package has PDFs
        has_any_pdfs = any(any(src.rglob("*.pdf")) for src in package_sources)
        if not has_any_pdfs:
            raise ValueError("No PDF files found in any package folder.")

        # Use specified model or default
        config = BEDROCK
        if model_id:
            config = replace(config, model_id=model_id)

        client = BedrockClient(config)
        pipeline = ReviewPipeline(
            client=client,
            max_workers=4,
            progress=_progress,
        )

        all_findings: list[Finding] = []
        package_map: dict[str, ContractPackage] = {}
        package_summaries: list[dict[str, Any]] = []

        for source in package_sources:
            # Determine package name from folder
            if source == upload_dir:
                pkg_name = project_manager.get_project(project_id)["name"]
            else:
                # Don't use generic folder names like "Docs" as the package ID
                folder_name = source.name
                if folder_name.lower() in ("docs", "documents", "pdfs", "files", "uploads"):
                    pkg_name = project_manager.get_project(project_id)["name"]
                else:
                    pkg_name = folder_name

            pdfs_in_source = list(source.rglob("*.pdf"))
            if not pdfs_in_source:
                continue

            _progress(f"\n{'='*60}")
            _progress(f"Processing package: {pkg_name} ({len(pdfs_in_source)} PDFs)")
            _progress(f"{'='*60}")

            package_dir = _prepare_single_package(source, output_dir, pkg_name)

            # Skip if no PDFs were found
            if not list((package_dir / "Docs").glob("*.pdf")):
                shutil.rmtree(package_dir, ignore_errors=True)
                continue

            result = pipeline.run_package(package_dir)
            all_findings.extend(result.findings)
            package_map[result.package.package_id] = result.package

            package_summaries.append({
                "package_id": result.package.package_id,
                "package_name": pkg_name,
                "total_findings": len(result.findings),
                "flags": sum(1 for f in result.findings if f.predicted_label == "FLAG"),
                "compliant": sum(1 for f in result.findings if f.predicted_label == "NO_FLAG"),
            })

            # Clean up temp package dir
            shutil.rmtree(package_dir, ignore_errors=True)

        if not all_findings:
            raise ValueError("No findings generated. Check that PDFs contain extractable text.")

        # Write combined outputs
        submission_path = reporting.write_submission(
            all_findings, output_dir / "submission.csv"
        )
        trace_path = reporting.write_evidence_trace(
            all_findings, package_map, output_dir / "evidence_trace.csv"
        )
        json_path = write_json_report(
            all_findings, package_map, output_dir / "findings_report.json"
        )
        pdf_path = write_pdf_report(
            all_findings, package_map, output_dir / "findings_summary.pdf"
        )

        # Write run summary
        summary = {
            "packages_analyzed": len(package_summaries),
            "packages": package_summaries,
            "totals": {
                "total_findings": len(all_findings),
                "flags": sum(1 for f in all_findings if f.predicted_label == "FLAG"),
                "compliant": sum(1 for f in all_findings if f.predicted_label == "NO_FLAG"),
            },
            "tokens_in": client.input_tokens,
            "tokens_out": client.output_tokens,
            "output_files": [
                submission_path.name,
                trace_path.name,
                json_path.name,
                pdf_path.name,
            ],
        }
        (output_dir / "run_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

        project_manager.update_status(project_id, "complete")
        return summary

    except Exception as exc:
        project_manager.update_status(project_id, "error", str(exc))
        raise
