"""ReconForge V1 data models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    """Important folders for one program-level run."""

    program: str
    root: Path
    scope_dir: Path
    raw_dir: Path
    clean_dir: Path
    reports_dir: Path
    logs_dir: Path


@dataclass
class ToolStatus:
    """Tool execution status for reporting."""

    tool: str
    command: list[str]
    return_code: int
    success: bool
    output_file: str
    stderr_sample: str
    skipped_reason: str | None = None


@dataclass
class ScopeData:
    """Parsed scope data."""

    roots: list[str]
    mobile_assets: list[str]
    excluded_assets: list[str]
