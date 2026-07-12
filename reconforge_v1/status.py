"""Tool status output helpers for ReconForge V1."""

from __future__ import annotations

import json
from dataclasses import asdict

from reconforge_v1.models import RunPaths, ToolStatus


def write_tool_statuses(paths: RunPaths, statuses: list[ToolStatus]) -> None:
    """Write tool statuses to JSON."""
    (paths.raw_dir / "tool_status.json").write_text(
        json.dumps([asdict(status) for status in statuses], indent=2) + "\n",
        encoding="utf-8",
    )
