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
    program: str | None = None


def create_workspace(
    target: str,
    base_dir: Path | str = "workspaces",
    program: str | None = None,
) -> WorkspacePaths:
    """
    Create and return the workspace directory structure for a target.

    Without program:
        workspaces/<target>/

    With program:
        workspaces/<program>/<target>/
    """
    base_path = Path(base_dir).expanduser().resolve()
    target_dir_name = workspace_safe_name(target)

    if program:
        program_dir_name = workspace_safe_name(program)
        root = base_path / program_dir_name / target_dir_name
        normalized_program = program_dir_name
    else:
        root = base_path / target_dir_name
        normalized_program = None

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
        program=normalized_program,
    )
