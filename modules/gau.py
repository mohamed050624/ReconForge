"""GAU integration for ReconForge V1."""

from __future__ import annotations

import logging
from pathlib import Path

from core.tool_runner import ToolRunResult, ToolRunner
from core.workspace import WorkspacePaths


COMBINED_SUBDOMAINS_FILENAME = "subdomains_combined.txt"
GAU_INPUT_FILENAME = "gau_input_domains.txt"
OUTPUT_FILENAME = "urls_gau.txt"


def collect_domains(target: str, workspace: WorkspacePaths) -> list[str]:
    """
    Collect domains/subdomains for GAU.

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


def write_gau_input(domains: list[str], output_path: Path) -> None:
    """Write GAU input domains to a file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(domains) + "\n", encoding="utf-8")


def build_command(input_file: Path) -> list[str]:
    """
    Build the GAU command.

    GAU can read domains from stdin, so ToolRunner runs it through bash here.

    This is the only V1 exception to the direct argv style because GAU's
    common list mode is pipeline-based:
        cat domains.txt | gau
    """
    return [
        "bash",
        "-lc",
        f"cat {input_file} | gau",
    ]


def run_gau(
    target: str,
    workspace: WorkspacePaths,
    runner: ToolRunner,
    logger: logging.Logger,
) -> ToolRunResult:
    """Run GAU and save discovered historical URLs."""
    domains = collect_domains(target=target, workspace=workspace)
    input_file = workspace.processed_dir / GAU_INPUT_FILENAME
    output_file = workspace.raw_dir / OUTPUT_FILENAME

    write_gau_input(domains=domains, output_path=input_file)

    command = build_command(input_file)

    logger.info("Starting GAU for %s domain(s).", len(domains))
    result = runner.run(command=command, output_file=output_file)

    if result.success:
        logger.info("GAU output: %s", output_file)
    else:
        logger.error("GAU failed.")

    return result
