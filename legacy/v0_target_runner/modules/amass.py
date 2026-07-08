"""Amass integration for ReconForge V1."""

from __future__ import annotations

import logging

from core.tool_runner import ToolRunResult, ToolRunner
from core.workspace import WorkspacePaths


OUTPUT_FILENAME = "subdomains_amass.txt"


def build_command(target: str) -> list[str]:
    """
    Build the Amass command.

    V1 uses passive mode to keep ReconForge focused on authorized,
    non-destructive reconnaissance.
    """
    return [
        "amass",
        "enum",
        "-passive",
        "-d",
        target,
    ]


def run_amass(
    target: str,
    workspace: WorkspacePaths,
    runner: ToolRunner,
    logger: logging.Logger,
) -> ToolRunResult:
    """Run Amass passive enumeration and save discovered subdomains."""
    output_file = workspace.raw_dir / OUTPUT_FILENAME
    command = build_command(target)

    logger.info("Starting Amass passive enumeration for target: %s", target)
    result = runner.run(command=command, output_file=output_file)

    if result.success:
        logger.info("Amass output: %s", output_file)
    else:
        logger.error("Amass failed for target: %s", target)

    return result
