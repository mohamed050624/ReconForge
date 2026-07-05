"""WhatWeb integration for ReconForge V1."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.tool_runner import ToolRunResult, ToolRunner
from core.workspace import WorkspacePaths


HTTPX_INPUT_FILENAME = "live_hosts_httpx.txt"
WHATWEB_INPUT_FILENAME = "live_hosts_whatweb_input.txt"
OUTPUT_FILENAME = "technologies_whatweb.txt"


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


def write_whatweb_input(urls: list[str], output_path: Path) -> None:
    """Write live URLs into a WhatWeb input file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(urls) + "\n", encoding="utf-8")


def build_command(input_file: Path) -> list[str]:
    """
    Build the WhatWeb command.

    Flags:
    - -i: input file containing URLs
    - --no-errors: reduce noisy connection errors
    """
    return [
        "whatweb",
        "-i",
        str(input_file),
        "--no-errors",
    ]


def run_whatweb(
    target: str,
    workspace: WorkspacePaths,
    runner: ToolRunner,
    logger: logging.Logger,
) -> ToolRunResult:
    """Run WhatWeb against live hosts discovered by HTTPX."""
    del target

    live_urls = collect_live_urls(workspace)
    whatweb_input = workspace.processed_dir / WHATWEB_INPUT_FILENAME
    output_file = workspace.raw_dir / OUTPUT_FILENAME

    if not live_urls:
        message = (
            "No live URLs found for WhatWeb. "
            "Run httpx first and make sure live_hosts_httpx.txt exists."
        )
        logger.error(message)
        return ToolRunResult(
            tool_name="whatweb",
            command=[],
            return_code=1,
            stdout="",
            stderr=message,
            output_file=output_file,
            success=False,
            dry_run=runner.dry_run,
        )

    write_whatweb_input(urls=live_urls, output_path=whatweb_input)

    command = build_command(whatweb_input)

    logger.info("Starting WhatWeb for %s live URLs.", len(live_urls))
    result = runner.run(command=command, output_file=output_file)

    if result.success:
        logger.info("WhatWeb output: %s", output_file)
    else:
        logger.error("WhatWeb failed.")

    return result
