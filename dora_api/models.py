"""Pydantic models for API request/response shapes."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProjectMode(str, Enum):
    standard = "standard"
    incognito = "incognito"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    mode: ProjectMode = ProjectMode.standard


class ProjectInfo(BaseModel):
    id: str
    name: str
    mode: ProjectMode
    created_at: str
    file_count: int
    status: str  # "ready" | "analyzing" | "complete" | "error"


class UploadedFile(BaseModel):
    file_name: str
    size_bytes: int
    uploaded_at: str


class AnalysisStatus(BaseModel):
    project_id: str
    status: str
    progress: str | None = None
    error: str | None = None


class OutputFile(BaseModel):
    file_name: str
    file_type: str  # "csv" | "json"
    size_bytes: int
    download_url: str
