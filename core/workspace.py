"""Workspace management for ReconForge.

A workspace is the per-target directory where ReconForge stores raw tool output,
processed data, reports, and logs. Keeping this logic isolated prevents every
module from inventing its own folder layout, because chaos already has enough
market share.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    """Resolved paths for a single ReconForge target workspace."""

    target: str
    root: Path
    logs: Path
    raw: Path
    processed: Path
    reports: Path


class WorkspaceError(RuntimeError):
    """Raised when workspace creation fails."""


def create_workspace(target: str, base_dir: Path | str = "workspaces") -> WorkspacePaths:
    """Create and return the workspace structure for a target.

    Args:
        target: Authorized target domain or program identifier.
        base_dir: Directory where all target workspaces are stored.

    Returns:
        WorkspacePaths with all important directories resolved.

    Raises:
        WorkspaceError: If target is empty or directories cannot be created.
    """
    safe_target = sanitize_target_name(target)
    root = Path(base_dir).expanduser().resolve() / safe_target

    paths = WorkspacePaths(
        target=target,
        root=root,
        logs=root / "logs",
        raw=root / "raw",
        processed=root / "processed",
        reports=root / "reports",
    )

    try:
        for directory in (
            paths.root,
            paths.logs,
            paths.raw,
            paths.processed,
            paths.reports,
        ):
            directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkspaceError(f"Unable to create workspace at {root}") from exc

    return paths


def sanitize_target_name(target: str) -> str:
    """Convert a target string into a safe directory name."""
    cleaned = target.strip().lower()

    if not cleaned:
        raise WorkspaceError("Target cannot be empty.")

    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = cleaned.strip("/")
    cleaned = re.sub(r"[^a-z0-9._-]+", "_", cleaned)
    cleaned = cleaned.strip("._-")

    if not cleaned:
        raise WorkspaceError("Target does not contain a valid workspace name.")

    return cleaned
