"""Workspace management for ReconForge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.targets import workspace_safe_name


@dataclass(frozen=True)
class WorkspacePaths:
    """All important paths for a single ReconForge target workspace."""

    target: str
    root: Path
    logs_dir: Path
    raw_dir: Path
    processed_dir: Path
    reports_dir: Path


def create_workspace(target: str, base_dir: Path | str = "workspaces") -> WorkspacePaths:
    """
    Create and return the workspace directory structure for a target.

    Structure:
        workspaces/<target>/
        ├── logs/
        ├── raw/
        ├── processed/
        └── reports/
    """
    base_path = Path(base_dir).expanduser().resolve()
    target_dir_name = workspace_safe_name(target)
    root = base_path / target_dir_name

    logs_dir = root / "logs"
    raw_dir = root / "raw"
    processed_dir = root / "processed"
    reports_dir = root / "reports"

    for directory in (root, logs_dir, raw_dir, processed_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return WorkspacePaths(
        target=target,
        root=root,
        logs_dir=logs_dir,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        reports_dir=reports_dir,
    )
