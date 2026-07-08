"""HTTPX integration for ReconForge V1."""

from __future__ import annotations

import logging
from pathlib import Path

from core.tool_runner import ToolRunResult, ToolRunner
from core.workspace import WorkspacePaths


INPUT_FILENAMES = (
    "subdomains_subfinder.txt",
    "subdomains_assetfinder.txt",
    "subdomains_amass.txt",
)

COMBINED_INPUT_FILENAME = "subdomains_combined.txt"
OUTPUT_FILENAME = "live_hosts_httpx.txt"


def collect_subdomains(workspace: WorkspacePaths) -> list[str]:
    """
    Collect, normalize, and deduplicate subdomains from previous modules.

    Reads from:
    - raw/subdomains_subfinder.txt
    - raw/subdomains_assetfinder.txt
    - raw/subdomains_amass.txt
    """
    subdomains: set[str] = set()

    for filename in INPUT_FILENAMES:
        path = workspace.raw_dir / filename

        if not path.exists():
            continue

        for line in path.read_text(encoding="utf-8").splitlines():
            value = line.strip().lower()

            if value:
                subdomains.add(value)

    return sorted(subdomains)


def write_combined_input(subdomains: list[str], output_path: Path) -> None:
    """Write combined subdomains into a file for HTTPX input."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(subdomains) + "\n", encoding="utf-8")


def build_command(input_file: Path) -> list[str]:
    """
    Build the HTTPX command.

    Flags:
    - -l: read input list from file
    - -silent: cleaner output
    - -status-code: include HTTP status code
    - -title: include page title
    - -tech-detect: detect common technologies
    """
    return [
        "httpx",
        "-l",
        str(input_file),
        "-silent",
        "-status-code",
        "-title",
        "-tech-detect",
    ]


def run_httpx(
    target: str,
    workspace: WorkspacePaths,
    runner: ToolRunner,
    logger: logging.Logger,
) -> ToolRunResult:
    """Run HTTPX against combined subdomain results."""
    del target

    combined_input = workspace.processed_dir / COMBINED_INPUT_FILENAME
    output_file = workspace.raw_dir / OUTPUT_FILENAME

    subdomains = collect_subdomains(workspace)

    if not subdomains:
        message = (
            "No subdomains found for HTTPX. "
            "Run subfinder, assetfinder, and/or amass first."
        )
        logger.error(message)
        return ToolRunResult(
            tool_name="httpx",
            command=[],
            return_code=1,
            stdout="",
            stderr=message,
            output_file=output_file,
            success=False,
            dry_run=runner.dry_run,
        )

    write_combined_input(subdomains=subdomains, output_path=combined_input)

    command = build_command(combined_input)

    logger.info("Starting HTTPX for %s hosts.", len(subdomains))
    result = runner.run(command=command, output_file=output_file)

    if result.success:
        logger.info("HTTPX output: %s", output_file)
    else:
        logger.error("HTTPX failed.")

    return result
