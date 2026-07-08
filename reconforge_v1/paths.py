"""Workspace path helpers for ReconForge V1."""

from __future__ import annotations

from pathlib import Path

from reconforge_v1.models import RunPaths
from reconforge_v1.utils import safe_name


def build_paths(program: str, out_dir: Path) -> RunPaths:
    """Create and return program-level folder structure."""
    program_name = safe_name(program)
    root = out_dir / program_name

    paths = RunPaths(
        program=program_name,
        root=root,
        scope_dir=root / "00_scope",
        raw_dir=root / "01_raw",
        clean_dir=root / "02_clean",
        reports_dir=root / "03_reports",
        logs_dir=root / "04_logs",
    )

    for directory in (
        paths.root,
        paths.scope_dir,
        paths.raw_dir,
        paths.clean_dir,
        paths.reports_dir,
        paths.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    return paths
