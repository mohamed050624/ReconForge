"""External tool runners for ReconForge V1."""

from __future__ import annotations

import logging
import re
import shutil
import socket
import subprocess
from pathlib import Path

from reconforge_v1.models import RunPaths, ToolStatus
from reconforge_v1.utils import append_text, read_lines, unique_sorted, write_lines


def run_command(
    *,
    tool: str,
    command: list[str],
    output_file: Path,
    logger: logging.Logger,
    timeout: int,
    dry_run: bool,
    stdin_text: str | None = None,
) -> ToolStatus:
    """Run an external command safely and capture stdout to a file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if shutil.which(command[0]) is None:
        reason = f"Executable not found: {command[0]}"
        logger.warning("%s skipped: %s", tool, reason)
        return ToolStatus(
            tool=tool,
            command=command,
            return_code=127,
            success=False,
            output_file=str(output_file),
            stderr_sample="",
            skipped_reason=reason,
        )

    if dry_run:
        logger.info("DRY RUN [%s]: %s", tool, " ".join(command))
        output_file.write_text("", encoding="utf-8")
        return ToolStatus(
            tool=tool,
            command=command,
            return_code=0,
            success=True,
            output_file=str(output_file),
            stderr_sample="",
            skipped_reason="dry-run",
        )

    logger.info("Running [%s]: %s", tool, " ".join(command))

    try:
        completed = subprocess.run(
            command,
            input=stdin_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")

        output_file.write_text(stdout, encoding="utf-8", errors="replace")
        logger.error("%s timed out after %s seconds.", tool, timeout)
        return ToolStatus(
            tool=tool,
            command=command,
            return_code=124,
            success=False,
            output_file=str(output_file),
            stderr_sample=f"Timed out after {timeout} seconds",
        )

    output_file.write_text(
        completed.stdout or "",
        encoding="utf-8",
        errors="replace",
    )

    stderr_sample = (completed.stderr or "").strip()[:1000]
    success = completed.returncode == 0

    if success:
        logger.info("%s completed successfully.", tool)
    else:
        logger.warning("%s exited with code %s.", tool, completed.returncode)
        if stderr_sample:
            logger.debug("%s stderr: %s", tool, stderr_sample)

    return ToolStatus(
        tool=tool,
        command=command,
        return_code=completed.returncode,
        success=success,
        output_file=str(output_file),
        stderr_sample=stderr_sample,
    )


def run_subdomain_tools(
    roots: list[str],
    paths: RunPaths,
    tools: list[str],
    logger: logging.Logger,
    timeout: int,
    dry_run: bool,
) -> list[ToolStatus]:
    """Run subdomain discovery tools per root and aggregate output files."""
    statuses: list[ToolStatus] = []

    tool_commands = {
        "subfinder": lambda root: ["subfinder", "-d", root, "-silent"],
        "assetfinder": lambda root: ["assetfinder", "--subs-only", root],
        "amass": lambda root: ["amass", "enum", "-passive", "-d", root],
    }

    for tool in ("subfinder", "assetfinder", "amass"):
        if tool not in tools:
            continue

        aggregate_output = paths.raw_dir / f"{tool}.txt"
        aggregate_output.write_text("", encoding="utf-8")

        for root in roots:
            per_root_output = paths.raw_dir / "per_root" / tool / f"{root}.txt"
            command = tool_commands[tool](root)

            status = run_command(
                tool=tool,
                command=command,
                output_file=per_root_output,
                logger=logger,
                timeout=timeout,
                dry_run=dry_run,
            )
            statuses.append(status)

            if per_root_output.exists():
                append_text(
                    aggregate_output,
                    per_root_output.read_text(
                        encoding="utf-8",
                        errors="replace",
                    ),
                )

    return statuses


def fallback_resolve_domains(domains: list[str], logger: logging.Logger) -> list[str]:
    """Resolve domains using Python socket fallback when dnsx is unavailable."""
    resolved: list[str] = []

    for domain in domains:
        try:
            socket.gethostbyname(domain)
        except OSError:
            continue
        resolved.append(domain)

    logger.info("Python resolver found %s resolved domains.", len(resolved))
    return sorted(set(resolved))


def run_dnsx_or_fallback(
    domains_file: Path,
    output_file: Path,
    logger: logging.Logger,
    timeout: int,
    dry_run: bool,
) -> ToolStatus:
    """Run dnsx if available, otherwise fallback to Python resolver."""
    if shutil.which("dnsx") is not None:
        return run_command(
            tool="dnsx",
            command=["dnsx", "-l", str(domains_file), "-silent"],
            output_file=output_file,
            logger=logger,
            timeout=timeout,
            dry_run=dry_run,
        )

    reason = "dnsx not found, using Python socket resolver fallback"
    logger.warning(reason)

    if dry_run:
        output_file.write_text("", encoding="utf-8")
        return ToolStatus(
            tool="dnsx",
            command=["dnsx", "-l", str(domains_file), "-silent"],
            return_code=0,
            success=True,
            output_file=str(output_file),
            stderr_sample="",
            skipped_reason="dry-run fallback",
        )

    resolved = fallback_resolve_domains(read_lines(domains_file), logger)
    write_lines(output_file, resolved)

    return ToolStatus(
        tool="dnsx",
        command=["python-socket-resolver"],
        return_code=0,
        success=True,
        output_file=str(output_file),
        stderr_sample="",
        skipped_reason=reason,
    )


def find_projectdiscovery_httpx(logger: logging.Logger) -> str:
    """
    Find the ProjectDiscovery httpx binary.

    Some systems have another binary named httpx that does not support
    ProjectDiscovery flags such as -l, -status-code, and -tech-detect.
    """
    candidates = ["httpx", "httpx-toolkit"]

    for candidate in candidates:
        if shutil.which(candidate) is None:
            continue

        try:
            completed = subprocess.run(
                [candidate, "-h"],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue

        help_text = f"{completed.stdout}\n{completed.stderr}"

        if "-l" in help_text and "-status-code" in help_text:
            logger.info("Using ProjectDiscovery httpx binary: %s", candidate)
            return candidate

    logger.warning(
        "Could not confirm ProjectDiscovery httpx. "
        "Falling back to 'httpx', but it may fail if this is the wrong binary."
    )
    return "httpx"


def run_httpx(
    input_file: Path,
    output_file: Path,
    logger: logging.Logger,
    timeout: int,
    dry_run: bool,
) -> ToolStatus:
    """Run ProjectDiscovery httpx against resolved hosts."""
    httpx_binary = find_projectdiscovery_httpx(logger)

    return run_command(
        tool="httpx",
        command=[
            httpx_binary,
            "-l",
            str(input_file),
            "-silent",
            "-status-code",
            "-title",
            "-tech-detect",
            "-follow-redirects",
        ],
        output_file=output_file,
        logger=logger,
        timeout=timeout,
        dry_run=dry_run,
    )


def extract_httpx_urls(lines: list[str]) -> list[str]:
    """Extract URLs from httpx output lines."""
    urls: list[str] = []

    for line in lines:
        match = re.match(r"^(https?://[^\s\[]+)", line.strip())
        if match:
            urls.append(match.group(1))

    return unique_sorted(urls)


def prepare_heavy_tool_input(
    live_hosts_file: Path,
    output_file: Path,
    max_hosts: int,
    logger: logging.Logger,
) -> Path:
    """
    Prepare a bounded live-host input file for heavier tools.

    Running whatweb/katana against hundreds or thousands of hosts can be slow.
    This keeps standard mode practical while preserving the full live_hosts.txt.
    """
    live_hosts = read_lines(live_hosts_file)

    selected = live_hosts[:max_hosts] if max_hosts > 0 else live_hosts

    write_lines(output_file, selected)

    logger.info(
        "Prepared heavy tool input: %s/%s live hosts -> %s",
        len(selected),
        len(live_hosts),
        output_file,
    )

    return output_file


def run_url_tools(
    live_hosts_file: Path,
    roots: list[str],
    paths: RunPaths,
    tools: list[str],
    profile: str,
    logger: logging.Logger,
    timeout: int,
    dry_run: bool,
    max_heavy_hosts: int,
) -> list[ToolStatus]:
    """Run URL collection and fingerprinting tools."""
    statuses: list[ToolStatus] = []

    live_urls = read_lines(live_hosts_file)
    root_input = "\n".join(roots) + "\n"

    heavy_hosts_file = prepare_heavy_tool_input(
        live_hosts_file=live_hosts_file,
        output_file=paths.clean_dir / "heavy_tool_live_hosts.txt",
        max_hosts=max_heavy_hosts,
        logger=logger,
    )

    if "whatweb" in tools:
        status = run_command(
            tool="whatweb",
            command=["whatweb", "-i", str(heavy_hosts_file), "--no-errors"],
            output_file=paths.raw_dir / "whatweb.txt",
            logger=logger,
            timeout=timeout,
            dry_run=dry_run,
        )
        statuses.append(status)

    if "gau" in tools:
        status = run_command(
            tool="gau",
            command=["gau"],
            output_file=paths.raw_dir / "gau.txt",
            logger=logger,
            timeout=timeout,
            dry_run=dry_run,
            stdin_text=root_input,
        )
        statuses.append(status)

    if "waybackurls" in tools:
        status = run_command(
            tool="waybackurls",
            command=["waybackurls"],
            output_file=paths.raw_dir / "waybackurls.txt",
            logger=logger,
            timeout=timeout,
            dry_run=dry_run,
            stdin_text=root_input,
        )
        statuses.append(status)

    if "katana" in tools:
        depth = "2" if profile == "deep" else "1"
        status = run_command(
            tool="katana",
            command=[
                "katana",
                "-list",
                str(heavy_hosts_file),
                "-d",
                depth,
                "-silent",
            ],
            output_file=paths.raw_dir / "katana.txt",
            logger=logger,
            timeout=timeout,
            dry_run=dry_run,
        )
        statuses.append(status)

    if not live_urls:
        logger.warning("No live URLs found before URL tool stage.")

    return statuses
