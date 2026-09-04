"""Project lifecycle management: create, list, delete, incognito cleanup."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import WORKSPACE_DIR
from .models import ProjectMode


def _project_dir(project_id: str) -> Path:
    # Project IDs are generated server-side, but every path entry point still
    # validates them so a crafted URL cannot escape the workspace.
    if not project_id or project_id in {".", ".."} or "/" in project_id or "\\" in project_id:
        raise FileNotFoundError(f"Project {project_id} not found")
    return WORKSPACE_DIR / project_id


def _metadata_path(project_id: str) -> Path:
    return _project_dir(project_id) / "project.json"


def _read_metadata(project_id: str) -> dict[str, Any]:
    meta_path = _metadata_path(project_id)
    if not meta_path.exists():
        raise FileNotFoundError(f"Project {project_id} not found")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _write_metadata(project_id: str, meta: dict[str, Any]) -> None:
    _metadata_path(project_id).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def create_project(name: str, mode: ProjectMode) -> dict[str, Any]:
    """Create a new project workspace directory."""
    project_id = str(uuid.uuid4())[:12]
    project_path = _project_dir(project_id)
    project_path.mkdir(parents=True)
    (project_path / "uploads").mkdir()
    (project_path / "outputs").mkdir()

    meta = {
        "id": project_id,
        "name": name,
        "mode": mode.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
    }
    _write_metadata(project_id, meta)
    return meta


def get_project(project_id: str) -> dict[str, Any]:
    """Read project metadata."""
    meta = _read_metadata(project_id)
    uploads_dir = _project_dir(project_id) / "uploads"
    meta["file_count"] = len([
        f for f in uploads_dir.rglob("*")
        if f.is_file() and (f.suffix.lower() in (".pdf", ".json"))
    ]) if uploads_dir.exists() else 0
    return meta


def list_projects() -> list[dict[str, Any]]:
    """List all projects in workspace."""
    projects = []
    if not WORKSPACE_DIR.exists():
        return projects
    for child in sorted(WORKSPACE_DIR.iterdir()):
        meta_path = child / "project.json"
        if child.is_dir() and meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                uploads_dir = child / "uploads"
                meta["file_count"] = len([
                    f for f in uploads_dir.rglob("*")
                    if f.is_file() and (f.suffix.lower() in (".pdf", ".json"))
                ]) if uploads_dir.exists() else 0
                projects.append(meta)
            except (json.JSONDecodeError, OSError):
                continue
    return projects


def delete_project(project_id: str) -> None:
    """Delete project and all files."""
    project_path = _project_dir(project_id)
    if project_path.exists():
        shutil.rmtree(project_path, ignore_errors=True)


def update_status(project_id: str, status: str, error: str | None = None) -> None:
    """Update project status."""
    meta = _read_metadata(project_id)
    meta["status"] = status
    if error:
        meta["error"] = error
    else:
        meta.pop("error", None)
    _write_metadata(project_id, meta)


def get_upload_dir(project_id: str) -> Path:
    path = _project_dir(project_id) / "uploads"
    if not path.exists():
        raise FileNotFoundError(f"Project {project_id} not found")
    return path


def get_output_dir(project_id: str) -> Path:
    # Do not let a read for a nonexistent project create a phantom directory.
    _read_metadata(project_id)
    path = _project_dir(project_id) / "outputs"
    path.mkdir(exist_ok=True)
    return path


def list_uploads(project_id: str) -> list[dict[str, Any]]:
    """List uploaded files (PDFs and JSONs) for a project, preserving folder paths."""
    uploads_dir = get_upload_dir(project_id)
    files = []
    for f in sorted(uploads_dir.rglob("*")):
        if not f.is_file():
            continue
        lower = f.name.lower()
        if not (lower.endswith(".pdf") or lower.endswith(".json")):
            continue
        stat = f.stat()
        # Relative path from the uploads directory
        rel_path = f.relative_to(uploads_dir).as_posix()
        files.append({
            "file_name": rel_path,
            "size_bytes": stat.st_size,
            "uploaded_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return files


def list_outputs(project_id: str) -> list[dict[str, Any]]:
    """List output files for a project."""
    output_dir = get_output_dir(project_id)
    files = []
    for f in sorted(output_dir.iterdir()):
        if f.is_file():
            ext = f.suffix.lstrip(".")
            file_type = ext if ext in ("csv", "json", "pdf") else "other"
            files.append({
                "file_name": f.name,
                "file_type": file_type,
                "size_bytes": f.stat().st_size,
                "download_url": f"/api/projects/{project_id}/outputs/{f.name}",
            })
    return files
