"""API configuration and paths."""
from __future__ import annotations

import os
from pathlib import Path

# Base directory for project workspace storage
WORKSPACE_DIR = Path(os.environ.get("DORA_WORKSPACE", str(Path(__file__).resolve().parents[1] / "dora_workspace")))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# Max upload size per file: 50MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024

# CORS: allow frontend dev server
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
