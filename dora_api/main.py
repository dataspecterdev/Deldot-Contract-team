"""DORA API — FastAPI application.

Endpoints:
  POST   /api/projects                      - Create a project
  GET    /api/projects                      - List all projects
  GET    /api/projects/{id}                 - Get project info
  DELETE /api/projects/{id}                 - Delete project (incognito cleanup)
  POST   /api/projects/{id}/upload          - Upload PDFs
  GET    /api/projects/{id}/files           - List uploaded files
  POST   /api/projects/{id}/analyze         - Trigger analysis
  GET    /api/projects/{id}/status          - Get analysis status
  GET    /api/projects/{id}/outputs         - List output files
  GET    /api/projects/{id}/outputs/{name}  - Download an output file
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, MAX_UPLOAD_SIZE
from .models import ProjectCreate, ProjectInfo, ProjectMode
from . import project_manager
from .analysis import run_analysis

app = FastAPI(
    title="DORA",
    description="DelDOT Orchestrated Review Assistant — Contract Clause Risk Flagging API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for running analysis in background without blocking
_executor = ThreadPoolExecutor(max_workers=2)


# --- Project CRUD ---

@app.post("/api/projects", status_code=201)
async def create_project(body: ProjectCreate):
    meta = project_manager.create_project(body.name, body.mode)
    return meta


@app.get("/api/projects")
async def list_projects():
    return project_manager.list_projects()


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    try:
        return project_manager.get_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@app.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(project_id: str):
    project_manager.delete_project(project_id)


# --- File Upload ---

@app.post("/api/projects/{project_id}/upload")
async def upload_files(project_id: str, files: list[UploadFile] = File(...)):
    try:
        upload_dir = project_manager.get_upload_dir(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    uploaded = []
    skipped = []
    for file in files:
        if not file.filename:
            continue
        # Preserve the relative path so same-name files in different folders don't collide.
        # Browsers send paths like "folder/sub/file.pdf" for folder uploads.
        relative_path = file.filename.replace("\\", "/")
        basename = relative_path.split("/")[-1]
        lower_name = basename.lower()
        if not (lower_name.endswith(".pdf") or lower_name.endswith(".json")):
            skipped.append(relative_path)
            continue

        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File {relative_path} exceeds 50MB limit.",
            )

        # Store in subdirectory to preserve folder structure
        dest = upload_dir / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        uploaded.append({"file_name": relative_path, "size_bytes": len(content)})

    return {"uploaded": uploaded, "total": len(uploaded), "skipped": skipped}


@app.get("/api/projects/{project_id}/files")
async def list_files(project_id: str):
    try:
        return project_manager.list_uploads(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@app.delete("/api/projects/{project_id}/files/{file_path:path}")
async def delete_file(project_id: str, file_path: str):
    try:
        upload_dir = project_manager.get_upload_dir(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    full_path = upload_dir / file_path
    # Security: ensure the resolved path is inside upload_dir
    if not str(full_path.resolve()).startswith(str(upload_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    full_path.unlink()
    # Clean up empty parent directories
    parent = full_path.parent
    while parent != upload_dir:
        if not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
        else:
            break
    return {"deleted": file_path}


# --- Package Grouping ---

@app.post("/api/projects/{project_id}/organize")
async def organize_files(project_id: str, body: dict):
    """Move files into named package groups (subfolders).

    Body: { "groups": { "Harbor_Crossing": ["file1.pdf", "file2.pdf"], "Pine_Grove": ["file3.pdf"] } }
    Files are moved from their current location into the named subfolder.
    """
    try:
        upload_dir = project_manager.get_upload_dir(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    groups = body.get("groups", {})
    if not groups:
        raise HTTPException(status_code=400, detail="No groups provided")

    moved = []
    errors = []
    for group_name, file_paths in groups.items():
        # Sanitize group name
        safe_name = group_name.strip().replace("/", "_").replace("\\", "_")
        if not safe_name:
            continue
        group_dir = upload_dir / safe_name
        group_dir.mkdir(parents=True, exist_ok=True)

        for file_path in file_paths:
            source = upload_dir / file_path
            if not source.exists():
                errors.append(f"Not found: {file_path}")
                continue
            if not str(source.resolve()).startswith(str(upload_dir.resolve())):
                errors.append(f"Invalid path: {file_path}")
                continue
            dest = group_dir / source.name
            # If dest already exists (same name), make unique
            if dest.exists() and dest != source:
                stem = source.stem
                suffix = source.suffix
                counter = 1
                while dest.exists():
                    dest = group_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            source.rename(dest)
            moved.append({"from": file_path, "to": dest.relative_to(upload_dir).as_posix()})

        # Clean up empty parent directories of moved files
        for file_path in file_paths:
            parent = (upload_dir / file_path).parent
            while parent != upload_dir and parent.exists():
                if not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break

    return {"moved": moved, "errors": errors}


@app.get("/api/projects/{project_id}/packages")
async def list_packages(project_id: str):
    """List detected package groups in the upload folder."""
    try:
        upload_dir = project_manager.get_upload_dir(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    packages = []
    loose_files = []

    # Check for subfolders that contain PDFs
    for child in sorted(upload_dir.iterdir()):
        if child.is_dir():
            pdfs = list(child.rglob("*.pdf"))
            jsons = list(child.rglob("*.json"))
            if pdfs or jsons:
                packages.append({
                    "name": child.name,
                    "file_count": len(pdfs) + len(jsons),
                    "files": [f.relative_to(upload_dir).as_posix() for f in sorted(pdfs + jsons)],
                })

    # Check for root-level loose files
    for f in sorted(upload_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in (".pdf", ".json"):
            loose_files.append(f.name)

    return {
        "packages": packages,
        "loose_files": loose_files,
        "needs_grouping": len(loose_files) > 0 and len(packages) > 0 or len(loose_files) > 1,
    }


# --- Analysis ---

@app.post("/api/projects/{project_id}/analyze")
async def trigger_analysis(project_id: str):
    try:
        meta = project_manager.get_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    if meta["status"] == "analyzing":
        raise HTTPException(status_code=409, detail="Analysis already in progress")

    if meta["file_count"] == 0:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Run analysis in background thread
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, run_analysis, project_id)

    return {"status": "analyzing", "message": "Analysis started"}


@app.get("/api/projects/{project_id}/status")
async def get_status(project_id: str):
    try:
        meta = project_manager.get_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "project_id": project_id,
        "status": meta["status"],
        "error": meta.get("error"),
    }


# --- Outputs ---

@app.get("/api/projects/{project_id}/outputs")
async def list_outputs(project_id: str):
    try:
        return project_manager.list_outputs(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@app.get("/api/projects/{project_id}/outputs/{file_name}")
async def download_output(project_id: str, file_name: str):
    try:
        output_dir = project_manager.get_output_dir(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    file_path = output_dir / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    media_type = "application/json" if file_path.suffix == ".json" else "text/csv"
    return FileResponse(
        path=str(file_path),
        filename=file_name,
        media_type=media_type,
    )


# --- Health ---

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "DORA"}


# --- Serve React Frontend (production build) ---
# This MUST come last so /api routes are matched first.

_FRONTEND_DIR = Path(__file__).resolve().parents[1] / "dora-ui" / "dist"

if _FRONTEND_DIR.exists():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="assets")

    # Serve favicon and other root-level static files
    @app.get("/dora-icon.svg")
    async def favicon_svg():
        icon = _FRONTEND_DIR / "dora-icon.svg"
        if icon.exists():
            return FileResponse(str(icon), media_type="image/svg+xml")
        raise HTTPException(status_code=404)

    @app.get("/favicon.ico")
    async def favicon_ico():
        # Serve the SVG as favicon fallback
        icon = _FRONTEND_DIR / "dora-icon.svg"
        if icon.exists():
            return FileResponse(str(icon), media_type="image/svg+xml")
        raise HTTPException(status_code=404)

    # SPA fallback: serve index.html for all non-API, non-asset routes
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        # Don't catch /api routes (shouldn't get here, but just in case)
        if full_path.startswith("api"):
            raise HTTPException(status_code=404)
        # Try to serve the file directly first (for other static files)
        file_path = _FRONTEND_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html (SPA routing)
        index = _FRONTEND_DIR / "index.html"
        return HTMLResponse(index.read_text(encoding="utf-8"))
