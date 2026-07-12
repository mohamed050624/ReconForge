"""Subfinder integration for ReconForge V1."""

from __future__ import annotations

import logging

from core.tool_runner import ToolRunResult, ToolRunner
from core.workspace import WorkspacePaths


OUTPUT_FILENAME = "subdomains_subfinder.txt"


def build_command(target: str) -> list[str]:
    """
    Build the Subfinder command.

    Uses passive discovery and quiet output suitable for saving to a text file.
    """
    return [
        "subfinder",
        "-d",
        target,
        "-silent",
    ]


def run_subfinder(
    target: str,
    workspace: WorkspacePaths,
    runner: ToolRunner,
    logger: logging.Logger,
) -> ToolRunResult:
    """Run Subfinder and save discovered subdomains."""
    output_file = workspace.raw_dir / OUTPUT_FILENAME
    command = build_command(target)

    logger.info("Starting Subfinder for target: %s", target)
    result = runner.run(command=command, output_file=output_file)

    if result.success:
        logger.info("Subfinder output: %s", output_file)
    else:
        logger.error("Subfinder failed for target: %s", target)

    return result
