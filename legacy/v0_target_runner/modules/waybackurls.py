"""Waybackurls integration for ReconForge V1."""

from __future__ import annotations

import logging
import shlex
from pathlib import Path

from core.tool_runner import ToolRunResult, ToolRunner
from core.workspace import WorkspacePaths


COMBINED_SUBDOMAINS_FILENAME = "subdomains_combined.txt"
WAYBACKURLS_INPUT_FILENAME = "waybackurls_input_domains.txt"
OUTPUT_FILENAME = "urls_waybackurls.txt"


def collect_domains(target: str, workspace: WorkspacePaths) -> list[str]:
    """
    Collect domains/subdomains for waybackurls.

    Preferred input:
    - processed/subdomains_combined.txt

    Fallback:
    - normalized target
    """
    input_file = workspace.processed_dir / COMBINED_SUBDOMAINS_FILENAME

    domains: set[str] = set()

    if input_file.exists():
        for line in input_file.read_text(encoding="utf-8").splitlines():
            value = line.strip().lower()

            if value:
                domains.add(value)

    if not domains:
        domains.add(target)

    return sorted(domains)


def write_waybackurls_input(domains: list[str], output_path: Path) -> None:
    """Write waybackurls input domains to a file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(domains) + "\n", encoding="utf-8")


def build_command(input_file: Path) -> list[str]:
    """
    Build the waybackurls command.

    waybackurls reads line-delimited domains from stdin, so V1 uses bash -lc
    for this pipeline:
        cat domains.txt | waybackurls
    """
    quoted_input = shlex.quote(str(input_file))

    return [
        "bash",
        "-lc",
        f"cat {quoted_input} | waybackurls",
    ]


def run_waybackurls(
    target: str,
    workspace: WorkspacePaths,
    runner: ToolRunner,
    logger: logging.Logger,
) -> ToolRunResult:
    """Run waybackurls and save discovered archived URLs."""
    domains = collect_domains(target=target, workspace=workspace)
    input_file = workspace.processed_dir / WAYBACKURLS_INPUT_FILENAME
    output_file = workspace.raw_dir / OUTPUT_FILENAME

    write_waybackurls_input(domains=domains, output_path=input_file)

    command = build_command(input_file)

    logger.info("Starting waybackurls for %s domain(s).", len(domains))
    result = runner.run(command=command, output_file=output_file)

    if result.success:
        logger.info("waybackurls output: %s", output_file)
    else:
        logger.error("waybackurls failed.")

    return result
