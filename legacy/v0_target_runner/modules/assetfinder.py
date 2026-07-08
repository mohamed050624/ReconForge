"""Assetfinder integration for ReconForge V1."""

from __future__ import annotations

import logging

from core.tool_runner import ToolRunResult, ToolRunner
from core.workspace import WorkspacePaths


OUTPUT_FILENAME = "subdomains_assetfinder.txt"


def build_command(target: str) -> list[str]:
    """
    Build the Assetfinder command.

    --subs-only keeps output focused on subdomains of the target domain.
    """
    return [
        "assetfinder",
        "--subs-only",
        target,
    ]


def run_assetfinder(
    target: str,
    workspace: WorkspacePaths,
    runner: ToolRunner,
    logger: logging.Logger,
) -> ToolRunResult:
    """Run Assetfinder and save discovered subdomains."""
    output_file = workspace.raw_dir / OUTPUT_FILENAME
    command = build_command(target)

    logger.info("Starting Assetfinder for target: %s", target)
    result = runner.run(command=command, output_file=output_file)

    if result.success:
        logger.info("Assetfinder output: %s", output_file)
    else:
        logger.error("Assetfinder failed for target: %s", target)

    return result
