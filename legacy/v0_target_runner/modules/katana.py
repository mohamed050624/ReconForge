"""Katana integration for ReconForge V1."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.tool_runner import ToolRunResult, ToolRunner
from core.workspace import WorkspacePaths


HTTPX_INPUT_FILENAME = "live_hosts_httpx.txt"
KATANA_INPUT_FILENAME = "live_hosts_katana_input.txt"
OUTPUT_FILENAME = "urls_katana.txt"


URL_PATTERN = re.compile(r"^https?://[^\s\[]+")


def extract_url(line: str) -> str | None:
    """
    Extract the URL from a single HTTPX output line.

    Example HTTPX lines:
        https://example.com [200] [Example Domain]
        http://api.example.com [403] [Forbidden]
    """
    value = line.strip()

    if not value:
        return None

    match = URL_PATTERN.match(value)

    if match:
        return match.group(0)

    if value.startswith(("http://", "https://")):
        return value.split()[0]

    return None


def collect_live_urls(workspace: WorkspacePaths) -> list[str]:
    """Collect live URLs from HTTPX output."""
    input_file = workspace.raw_dir / HTTPX_INPUT_FILENAME

    if not input_file.exists():
        return []

    urls: set[str] = set()

    for line in input_file.read_text(encoding="utf-8").splitlines():
        url = extract_url(line)

        if url:
            urls.add(url)

    return sorted(urls)


def write_katana_input(urls: list[str], output_path: Path) -> None:
    """Write live URLs into a Katana input file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(urls) + "\n", encoding="utf-8")


def build_command(input_file: Path) -> list[str]:
    """
    Build the Katana command.

    Flags:
    - -list: input file containing live URLs
    - -d 2: crawl depth 2 for safe V1 default
    - -silent: clean output
    """
    return [
        "katana",
        "-list",
        str(input_file),
        "-d",
        "2",
        "-silent",
    ]


def run_katana(
    target: str,
    workspace: WorkspacePaths,
    runner: ToolRunner,
    logger: logging.Logger,
) -> ToolRunResult:
    """Run Katana against live hosts discovered by HTTPX."""
    del target

    live_urls = collect_live_urls(workspace)
    katana_input = workspace.processed_dir / KATANA_INPUT_FILENAME
    output_file = workspace.raw_dir / OUTPUT_FILENAME

    if not live_urls:
        message = (
            "No live URLs found for Katana. "
            "Run httpx first and make sure live_hosts_httpx.txt exists."
        )
        logger.error(message)
        return ToolRunResult(
            tool_name="katana",
            command=[],
            return_code=1,
            stdout="",
            stderr=message,
            output_file=output_file,
            success=False,
            dry_run=runner.dry_run,
        )

    write_katana_input(urls=live_urls, output_path=katana_input)

    command = build_command(katana_input)

    logger.info("Starting Katana for %s live URLs.", len(live_urls))
    result = runner.run(command=command, output_file=output_file)

    if result.success:
        logger.info("Katana output: %s", output_file)
    else:
        logger.error("Katana failed.")

    return result
