"""ReconForge One-Shot Program Recon.

A practical, program-first reconnaissance orchestrator for authorized Bug Bounty
and penetration testing workflows.

This script is intentionally passive/non-destructive by default:
- no exploitation
- no brute force
- no credential attacks
- no DoS
- no aggressive fuzzing

It collects, cleans, summarizes, and prepares AI-ready context.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import shutil
import socket
import subprocess
import sys
import tarfile
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlparse

from reconforge_v1.constants import (
    API_HOST_KEYWORDS,
    API_PATH_KEYWORDS,
    AUTH_KEYWORDS,
    DOMAIN_RE,
    GRAPHQL_KEYWORDS,
    INTERESTING_PATH_KEYWORDS,
    JS_EXTENSIONS,
    MOBILE_ASSET_TYPES,
    PROFILE_TOOLS,
    STATIC_EXTENSIONS,
    SWAGGER_OPENAPI_KEYWORDS,
    UPLOAD_KEYWORDS,
    URL_RE,
    WEB_ASSET_TYPES,
)
from reconforge_v1.logging_config import setup_logger
from reconforge_v1.models import RunPaths, ScopeData, ToolStatus
from reconforge_v1.paths import build_paths
from reconforge_v1.utils import (
    append_text,
    clean_domain,
    normalize_url,
    read_lines,
    safe_name,
    utc_now,
    unique_sorted,
    write_lines,
)


def create_policy_template(paths: RunPaths) -> None:
    """Create policy_notes.md if missing."""
    policy_path = paths.scope_dir / "policy_notes.md"

    if policy_path.exists():
        return

    content = f"""# Policy Notes for {paths.program}

Paste the official Bug Bounty / penetration testing policy here.

## Program URL

PASTE_OFFICIAL_PROGRAM_URL_HERE

## In Scope

Paste official in-scope assets here.

## Out of Scope

Paste official out-of-scope assets here.

## Rules / Restrictions

Paste official testing rules here.

Recommended safety notes:
- Only test assets clearly listed as in scope.
- Do not test assets listed as out of scope.
- Do not perform denial-of-service testing.
- Do not perform social engineering.
- Do not perform credential attacks.
- Do not access, modify, or exfiltrate user data.
- Stop and report if sensitive data is accidentally exposed.
"""
    policy_path.write_text(content, encoding="utf-8")


def parse_scope_csv(path: Path) -> ScopeData:
    """Parse HackerOne-style scope CSV."""
    roots: set[str] = set()
    mobile_assets: list[str] = []
    excluded_assets: list[str] = []

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        required = {
            "identifier",
            "asset_type",
            "eligible_for_bounty",
            "eligible_for_submission",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "scope CSV is missing required columns: "
                + ", ".join(sorted(missing))
            )

        for row in reader:
            identifier = (row.get("identifier") or "").strip()
            asset_type = (row.get("asset_type") or "").strip().upper()
            bounty = (row.get("eligible_for_bounty") or "").strip().lower()
            submission = (row.get("eligible_for_submission") or "").strip().lower()

            is_allowed = bounty == "true" and submission == "true"

            if asset_type in WEB_ASSET_TYPES and is_allowed:
                cleaned = clean_domain(identifier)
                if cleaned:
                    roots.add(cleaned)
                continue

            if asset_type in MOBILE_ASSET_TYPES and is_allowed:
                mobile_assets.append(f"{identifier} [{asset_type}]")
                continue

            excluded_assets.append(
                f"{identifier} [{asset_type}] bounty={bounty} submission={submission}"
            )

    return ScopeData(
        roots=sorted(roots),
        mobile_assets=sorted(mobile_assets),
        excluded_assets=sorted(excluded_assets),
    )


def parse_roots(args: argparse.Namespace, paths: RunPaths) -> ScopeData:
    """Resolve roots from --root, --roots-file, and/or --scope-csv."""
    roots: set[str] = set()
    mobile_assets: list[str] = []
    excluded_assets: list[str] = []

    for raw_root in args.root or []:
        cleaned = clean_domain(raw_root)
        if cleaned:
            roots.add(cleaned)

    if args.roots_file:
        for raw_root in read_lines(Path(args.roots_file)):
            cleaned = clean_domain(raw_root)
            if cleaned:
                roots.add(cleaned)

    if args.scope_csv:
        scope_csv_path = Path(args.scope_csv)
        scope_data = parse_scope_csv(scope_csv_path)
        roots.update(scope_data.roots)
        mobile_assets.extend(scope_data.mobile_assets)
        excluded_assets.extend(scope_data.excluded_assets)

        destination = paths.scope_dir / "scope.csv"
        if scope_csv_path.resolve() != destination.resolve():
            destination.write_text(
                scope_csv_path.read_text(encoding="utf-8", errors="replace"),
                encoding="utf-8",
            )

    if not roots and args.profile != "report-only":
        raise ValueError("Provide --root, --roots-file, or --scope-csv.")

    return ScopeData(
        roots=sorted(roots),
        mobile_assets=sorted(set(mobile_assets)),
        excluded_assets=sorted(set(excluded_assets)),
    )


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


def collect_domains_from_raw(paths: RunPaths, roots: list[str]) -> list[str]:
    """Collect subdomains from raw discovery outputs."""
    values: list[str] = []
    values.extend(roots)

    for filename in ("subfinder.txt", "assetfinder.txt", "amass.txt"):
        for line in read_lines(paths.raw_dir / filename):
            cleaned = clean_domain(line)
            if cleaned:
                values.append(cleaned)

    return unique_sorted(values)


def collect_urls_from_raw(paths: RunPaths) -> list[str]:
    """
    Collect URLs from raw outputs.

    ProjectDiscovery httpx output is line-based and starts with the live URL,
    so we explicitly parse it before regex extraction.
    """
    urls: list[str] = []

    httpx_path = paths.raw_dir / "httpx.txt"
    if httpx_path.exists():
        urls.extend(extract_httpx_urls(read_lines(httpx_path)))

    for filename in ("gau.txt", "waybackurls.txt", "katana.txt", "httpx.txt"):
        path = paths.raw_dir / filename
        if not path.exists():
            continue

        content = path.read_text(encoding="utf-8", errors="replace")
        for match in URL_RE.findall(content):
            normalized = normalize_url(match)
            if normalized:
                urls.append(normalized)

    return unique_sorted(urls)


def get_url_path_lower(url: str) -> str:
    """Return lowercased URL path."""
    return (urlparse(url).path or "").lower()


def is_static_asset(url: str) -> bool:
    """Return True if URL looks like a static asset."""
    path = get_url_path_lower(url)
    return path.endswith(STATIC_EXTENSIONS)


def looks_like_api_host(host: str) -> bool:
    """Return True if hostname looks API-related."""
    host_lower = host.lower()
    return any(keyword in host_lower for keyword in API_HOST_KEYWORDS)


def looks_like_api_url(url: str) -> bool:
    """Return True if URL looks API-related."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if looks_like_api_host(host):
        return True

    return any(keyword in path for keyword in API_PATH_KEYWORDS)


def contains_any(value: str, keywords: Iterable[str]) -> bool:
    """Case-insensitive keyword containment check."""
    lower = value.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def extract_params(urls: list[str]) -> list[str]:
    """Extract unique query parameter names."""
    params: set[str] = set()

    for url in urls:
        parsed = urlparse(url)
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
            if key:
                params.add(key)

    return sorted(params)


def filter_urls(urls: list[str], predicate) -> list[str]:
    """Filter URLs by predicate."""
    return sorted({url for url in urls if predicate(url)})


def extract_js_files(urls: list[str]) -> list[str]:
    """Extract JS file URLs."""
    return filter_urls(
        urls,
        lambda url: get_url_path_lower(url).endswith(JS_EXTENSIONS),
    )


def extract_interesting_urls(urls: list[str]) -> list[str]:
    """Extract high-signal URLs based on path keywords and parameters."""
    interesting: set[str] = set()

    for url in urls:
        parsed = urlparse(url)
        signal_text = f"{parsed.netloc}{parsed.path}{parsed.query}".lower()

        if contains_any(signal_text, INTERESTING_PATH_KEYWORDS):
            interesting.add(url)

        if parsed.query:
            interesting.add(url)

    return sorted(interesting)


def build_clean_outputs(
    roots: list[str],
    paths: RunPaths,
    logger: logging.Logger,
    timeout: int,
    dry_run: bool,
    should_resolve: bool = True,
) -> list[ToolStatus]:
    """Clean raw outputs and write normalized program-level files."""
    statuses: list[ToolStatus] = []

    write_lines(paths.clean_dir / "roots.txt", roots)

    subdomains = collect_domains_from_raw(paths, roots)
    write_lines(paths.clean_dir / "subdomains_all.txt", subdomains)

    if should_resolve:
        status = run_dnsx_or_fallback(
            domains_file=paths.clean_dir / "subdomains_all.txt",
            output_file=paths.clean_dir / "subdomains_resolved.txt",
            logger=logger,
            timeout=timeout,
            dry_run=dry_run,
        )
        statuses.append(status)
    else:
        write_lines(paths.clean_dir / "subdomains_resolved.txt", subdomains)

    resolved = read_lines(paths.clean_dir / "subdomains_resolved.txt")
    if not resolved:
        resolved = subdomains
        write_lines(paths.clean_dir / "subdomains_resolved.txt", resolved)

    return statuses


def build_url_clean_outputs(paths: RunPaths) -> None:
    """Build URL/API/interesting endpoint outputs."""
    httpx_lines = read_lines(paths.raw_dir / "httpx.txt")
    live_urls = extract_httpx_urls(httpx_lines)
    write_lines(paths.clean_dir / "live_hosts.txt", live_urls)

    urls = collect_urls_from_raw(paths)
    write_lines(paths.clean_dir / "urls_all.txt", urls)

    non_static_urls = [url for url in urls if not is_static_asset(url)]
    write_lines(paths.clean_dir / "urls_unique.txt", non_static_urls)

    js_files = extract_js_files(urls)
    write_lines(paths.clean_dir / "js_files.txt", js_files)

    params = extract_params(non_static_urls)
    write_lines(paths.clean_dir / "params.txt", params)

    api_endpoints = filter_urls(non_static_urls, looks_like_api_url)
    write_lines(paths.clean_dir / "api_endpoints.txt", api_endpoints)

    api_params = [
        url
        for url in api_endpoints
        if urlparse(url).query
    ]
    write_lines(paths.clean_dir / "api_params.txt", api_params)

    graphql_candidates = filter_urls(
        non_static_urls,
        lambda url: contains_any(url, GRAPHQL_KEYWORDS),
    )
    write_lines(paths.clean_dir / "graphql_candidates.txt", graphql_candidates)

    swagger_candidates = filter_urls(
        non_static_urls,
        lambda url: contains_any(url, SWAGGER_OPENAPI_KEYWORDS),
    )
    write_lines(paths.clean_dir / "swagger_openapi_candidates.txt", swagger_candidates)

    auth_endpoints = filter_urls(
        non_static_urls,
        lambda url: contains_any(url, AUTH_KEYWORDS),
    )
    write_lines(paths.clean_dir / "auth_endpoints.txt", auth_endpoints)

    upload_endpoints = filter_urls(
        non_static_urls,
        lambda url: contains_any(url, UPLOAD_KEYWORDS),
    )
    write_lines(paths.clean_dir / "upload_endpoints.txt", upload_endpoints)

    interesting_urls = extract_interesting_urls(non_static_urls)
    write_lines(paths.clean_dir / "interesting_urls.txt", interesting_urls)

    technologies = read_lines(paths.raw_dir / "whatweb.txt")
    write_lines(paths.clean_dir / "technologies.txt", technologies)

    api_hosts: set[str] = set()
    for url in api_endpoints:
        host = urlparse(url).hostname
        if host:
            api_hosts.add(host)
    for host in read_lines(paths.clean_dir / "subdomains_all.txt"):
        if looks_like_api_host(host):
            api_hosts.add(host)
    write_lines(paths.clean_dir / "api_base_hosts.txt", api_hosts)

    high_signal = sorted(
        set(read_lines(paths.clean_dir / "api_base_hosts.txt"))
        | set(read_lines(paths.clean_dir / "graphql_candidates.txt")[:100])
        | set(read_lines(paths.clean_dir / "swagger_openapi_candidates.txt")[:100])
        | set(read_lines(paths.clean_dir / "auth_endpoints.txt")[:100])
        | set(read_lines(paths.clean_dir / "upload_endpoints.txt")[:100])
    )
    write_lines(paths.clean_dir / "high_signal_assets.txt", high_signal)


def sample(values: list[str], limit: int = 50) -> list[str]:
    """Return bounded sample for reports/context."""
    return values[:limit]


def count_by_host(urls: list[str]) -> list[dict[str, int | str]]:
    """Count URLs by host."""
    counter: Counter[str] = Counter()

    for url in urls:
        host = urlparse(url).hostname
        if host:
            counter[host] += 1

    return [
        {"host": host, "count": count}
        for host, count in counter.most_common(50)
    ]


def read_policy(paths: RunPaths) -> str:
    """Read policy notes."""
    return (paths.scope_dir / "policy_notes.md").read_text(
        encoding="utf-8",
        errors="replace",
    )


def build_context(paths: RunPaths, tool_statuses: list[ToolStatus]) -> dict:
    """Build program-level AI context."""
    roots = read_lines(paths.clean_dir / "roots.txt")
    subdomains = read_lines(paths.clean_dir / "subdomains_all.txt")
    resolved = read_lines(paths.clean_dir / "subdomains_resolved.txt")
    live_hosts = read_lines(paths.clean_dir / "live_hosts.txt")
    urls = read_lines(paths.clean_dir / "urls_unique.txt")
    api_hosts = read_lines(paths.clean_dir / "api_base_hosts.txt")
    api_endpoints = read_lines(paths.clean_dir / "api_endpoints.txt")
    api_params = read_lines(paths.clean_dir / "api_params.txt")
    graphql = read_lines(paths.clean_dir / "graphql_candidates.txt")
    swagger = read_lines(paths.clean_dir / "swagger_openapi_candidates.txt")
    auth = read_lines(paths.clean_dir / "auth_endpoints.txt")
    uploads = read_lines(paths.clean_dir / "upload_endpoints.txt")
    params = read_lines(paths.clean_dir / "params.txt")
    js_files = read_lines(paths.clean_dir / "js_files.txt")
    interesting = read_lines(paths.clean_dir / "interesting_urls.txt")
    technologies = read_lines(paths.clean_dir / "technologies.txt")
    high_signal = read_lines(paths.clean_dir / "high_signal_assets.txt")
    mobile_assets = read_lines(paths.scope_dir / "mobile_assets.txt")
    excluded_assets = read_lines(paths.scope_dir / "excluded_assets.txt")

    return {
        "schema_version": "reconforge.one.v1",
        "generated_at": utc_now(),
        "program": paths.program,
        "workspace": str(paths.root),
        "purpose": (
            "AI-ready reconnaissance context for authorized Bug Bounty "
            "and penetration testing manual review."
        ),
        "safety_boundaries": {
            "authorized_scope_required": True,
            "no_exploitation_automation": True,
            "no_destructive_testing": True,
            "no_denial_of_service": True,
            "no_credential_attacks": True,
            "no_social_engineering": True,
            "human_reviewer_required": True,
        },
        "summary": {
            "root_targets": len(roots),
            "subdomains_discovered": len(subdomains),
            "subdomains_resolved": len(resolved),
            "live_hosts": len(live_hosts),
            "urls": len(urls),
            "api_hosts": len(api_hosts),
            "api_endpoints": len(api_endpoints),
            "api_urls_with_params": len(api_params),
            "parameters": len(params),
            "graphql_candidates": len(graphql),
            "swagger_openapi_candidates": len(swagger),
            "auth_endpoints": len(auth),
            "upload_endpoints": len(uploads),
            "js_files": len(js_files),
            "technology_fingerprints": len(technologies),
            "mobile_assets_not_scanned": len(mobile_assets),
            "excluded_assets": len(excluded_assets),
        },
        "scope": {
            "roots": roots,
            "mobile_assets_not_scanned": mobile_assets,
            "excluded_assets": sample(excluded_assets, 200),
        },
        "assets": {
            "subdomains_sample": sample(subdomains, 200),
            "resolved_subdomains_sample": sample(resolved, 200),
            "live_hosts_sample": sample(live_hosts, 200),
            "high_signal_assets": sample(high_signal, 200),
        },
        "urls": {
            "top_hosts_by_url_count": count_by_host(urls),
            "interesting_urls_sample": sample(interesting, 300),
            "all_urls_file": "02_clean/urls_unique.txt",
        },
        "api_attack_surface": {
            "api_hosts": sample(api_hosts, 200),
            "api_endpoints_sample": sample(api_endpoints, 300),
            "api_params_sample": sample(api_params, 200),
            "graphql_candidates": sample(graphql, 200),
            "swagger_openapi_candidates": sample(swagger, 200),
            "auth_endpoints_sample": sample(auth, 200),
            "upload_endpoints_sample": sample(uploads, 200),
            "parameters": sample(params, 300),
        },
        "javascript": {
            "js_files_sample": sample(js_files, 200),
        },
        "technology_fingerprints_sample": sample(technologies, 200),
        "tool_statuses": [asdict(status) for status in tool_statuses],
        "important_files": {
            "policy_notes": "00_scope/policy_notes.md",
            "roots": "02_clean/roots.txt",
            "subdomains": "02_clean/subdomains_all.txt",
            "live_hosts": "02_clean/live_hosts.txt",
            "urls": "02_clean/urls_unique.txt",
            "api_endpoints": "02_clean/api_endpoints.txt",
            "interesting_urls": "02_clean/interesting_urls.txt",
            "ai_handoff": "03_reports/ai_handoff.md",
        },
    }


def md_list(values: list[str], limit: int = 30) -> str:
    """Render values as Markdown bullet list."""
    if not values:
        return "_No data._"

    rendered = "\n".join(f"- `{value}`" for value in values[:limit])
    remaining = len(values) - limit

    if remaining > 0:
        rendered += f"\n- _...and {remaining} more._"

    return rendered


def build_program_report(context: dict) -> str:
    """Build Markdown program report."""
    summary = context["summary"]
    api = context["api_attack_surface"]
    assets = context["assets"]
    urls = context["urls"]

    lines = [
        f"# ReconForge One Program Report: {context['program']}",
        "",
        f"Generated at: `{context['generated_at']}`",
        "",
        "## Safety Boundaries",
        "",
        "- Authorized scope required.",
        "- Passive and non-destructive reconnaissance only.",
        "- No exploitation automation.",
        "- No DoS, credential attacks, social engineering, or destructive testing.",
        "",
        "## Summary",
        "",
        f"- Root targets: **{summary['root_targets']}**",
        f"- Subdomains discovered: **{summary['subdomains_discovered']}**",
        f"- Resolved subdomains: **{summary['subdomains_resolved']}**",
        f"- Live hosts: **{summary['live_hosts']}**",
        f"- URLs collected: **{summary['urls']}**",
        f"- API hosts: **{summary['api_hosts']}**",
        f"- API endpoints: **{summary['api_endpoints']}**",
        f"- Parameters: **{summary['parameters']}**",
        f"- GraphQL candidates: **{summary['graphql_candidates']}**",
        f"- Swagger/OpenAPI candidates: **{summary['swagger_openapi_candidates']}**",
        f"- Auth endpoints: **{summary['auth_endpoints']}**",
        f"- Upload endpoints: **{summary['upload_endpoints']}**",
        f"- JS files: **{summary['js_files']}**",
        "",
        "## High Signal Assets",
        "",
        md_list(assets["high_signal_assets"], 50),
        "",
        "## Live Hosts Sample",
        "",
        md_list(assets["live_hosts_sample"], 50),
        "",
        "## API Attack Surface",
        "",
        "### API Hosts",
        "",
        md_list(api["api_hosts"], 50),
        "",
        "### API Endpoints Sample",
        "",
        md_list(api["api_endpoints_sample"], 80),
        "",
        "### GraphQL Candidates",
        "",
        md_list(api["graphql_candidates"], 50),
        "",
        "### Swagger / OpenAPI Candidates",
        "",
        md_list(api["swagger_openapi_candidates"], 50),
        "",
        "### Auth Endpoints",
        "",
        md_list(api["auth_endpoints_sample"], 50),
        "",
        "### Upload Endpoints",
        "",
        md_list(api["upload_endpoints_sample"], 50),
        "",
        "### Parameters",
        "",
        md_list(api["parameters"], 80),
        "",
        "## Interesting URLs",
        "",
        md_list(urls["interesting_urls_sample"], 100),
        "",
        "## Important Files",
        "",
    ]

    for name, path in context["important_files"].items():
        lines.append(f"- **{name}:** `{path}`")

    lines.extend(
        [
            "",
            "## Manual Review Focus",
            "",
            "- Confirm every reviewed asset is inside official scope.",
            "- Prioritize API authorization, IDOR/BOLA, session handling, exposed docs, and upload logic.",
            "- Review admin/dev/staging-looking hosts manually.",
            "- Review archived URLs for forgotten endpoints.",
            "- Treat unclear assets as needing scope verification.",
            "",
        ]
    )

    return "\n".join(lines)


def build_ai_prompt(program: str) -> str:
    """Build reusable AI prompt."""
    return f"""You are assisting with an authorized Bug Bounty reconnaissance review for {program}.

I will provide:
1. ReconForge One AI handoff
2. Program-level AI context JSON
3. Official policy notes copied from the program page

Important rules:
- Only analyze assets that are clearly in scope.
- Do not suggest testing assets listed as excluded or out of scope.
- Do not suggest denial-of-service testing.
- Do not suggest credential attacks.
- Do not suggest social engineering.
- Do not suggest destructive testing.
- Do not suggest exploitation automation.
- If an asset is unclear, mark it as "Needs scope verification".
- Focus on safe manual testing ideas only.

Task:
Analyze the ReconForge handoff and produce a prioritized manual testing plan.

Return:

1. Scope confirmation
- Clearly in-scope assets
- Assets needing scope verification
- Excluded/out-of-scope assets to avoid

2. Attack surface summary
- Subdomains
- Live hosts
- Technologies
- URLs
- API surface
- Interesting patterns

3. Top priority assets table
Columns:
- Priority
- Asset / URL
- Why it matters
- Suggested safe manual review

4. API review plan
Focus on:
- API authorization
- IDOR/BOLA
- Auth/session logic
- GraphQL authorization
- Swagger/OpenAPI exposure
- Upload/media logic
- Excessive data exposure

5. Interesting endpoints and parameters

6. Likely vulnerability categories for manual review

7. Non-destructive validation plan

8. Missing reconnaissance data

9. Final risk-ranked manual testing order
"""


def build_ai_handoff(context: dict, program_report: str, policy_notes: str) -> str:
    """Build AI handoff Markdown."""
    prompt = build_ai_prompt(context["program"])

    return "\n\n".join(
        [
            f"# ReconForge One AI Handoff: {context['program']}",
            "## Read This First",
            (
                "This handoff was generated from passive, non-destructive "
                "reconnaissance for authorized Bug Bounty / penetration testing review."
            ),
            "## Official Policy Notes Copied by User",
            policy_notes,
            "## Program Recon Report",
            program_report,
            "## AI Prompt",
            prompt,
            "## Full JSON Context",
            (
                "Use `program_ai_context.json` for structured data. "
                "Large full lists are stored in `02_clean/`."
            ),
        ]
    )


def copy_if_exists(source: Path, destination: Path) -> None:
    """Copy a file if it exists."""
    if not source.exists():
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def write_ai_package(paths: RunPaths) -> Path:
    """
    Build a single AI package archive.

    This archive is the only file the user should need to upload to an AI
    assistant for analysis.
    """
    package_dir = paths.root / "ai_package"
    archive_path = paths.root / f"{paths.program}_ai_package.tar.gz"

    if package_dir.exists():
        shutil.rmtree(package_dir)

    package_dir.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        paths.reports_dir / "ai_handoff.md",
        paths.reports_dir / "program_ai_context.json",
        paths.reports_dir / "ai_prompt.md",
        paths.reports_dir / "program_report.md",
        paths.scope_dir / "policy_notes.md",
        paths.scope_dir / "in_scope_web_roots.txt",
        paths.scope_dir / "excluded_assets.txt",
        paths.scope_dir / "mobile_assets.txt",
        paths.raw_dir / "tool_status.json",
        paths.clean_dir / "roots.txt",
        paths.clean_dir / "subdomains_all.txt",
        paths.clean_dir / "subdomains_resolved.txt",
        paths.clean_dir / "live_hosts.txt",
        paths.clean_dir / "urls_unique.txt",
        paths.clean_dir / "api_base_hosts.txt",
        paths.clean_dir / "api_endpoints.txt",
        paths.clean_dir / "api_params.txt",
        paths.clean_dir / "graphql_candidates.txt",
        paths.clean_dir / "swagger_openapi_candidates.txt",
        paths.clean_dir / "auth_endpoints.txt",
        paths.clean_dir / "upload_endpoints.txt",
        paths.clean_dir / "interesting_urls.txt",
        paths.clean_dir / "high_signal_assets.txt",
        paths.clean_dir / "params.txt",
        paths.clean_dir / "js_files.txt",
        paths.clean_dir / "technologies.txt",
    ]

    for source in files_to_copy:
        try:
            relative = source.relative_to(paths.root)
        except ValueError:
            relative = Path(source.name)

        copy_if_exists(source, package_dir / relative)

    readme = f"""# ReconForge AI Package: {paths.program}

Upload this archive to the AI assistant.

Main files:
- `03_reports/ai_handoff.md`
- `03_reports/program_ai_context.json`
- `03_reports/ai_prompt.md`
- `00_scope/policy_notes.md`

How the AI should use this:
1. Read `ai_handoff.md` first.
2. Use `program_ai_context.json` for structured analysis.
3. Use files in `02_clean/` for detailed evidence.
4. Respect `policy_notes.md` and scope restrictions.
5. If more data is needed, ask the user for one safe command at a time.

Rules for follow-up commands:
- Only ask for non-destructive inspection commands.
- Do not ask for DoS, brute force, credential attacks, exploitation, or fuzzing.
- Prefer commands like:
  - `head -100 <file>`
  - `grep -i "keyword" <file>`
  - `wc -l <file>`
  - `cat <small-file>`
  - `python3 reconforge_one.py --program {paths.program} --profile report-only --verbose`
"""

    (package_dir / "SEND_THIS_TO_AI.md").write_text(readme, encoding="utf-8")

    if archive_path.exists():
        archive_path.unlink()

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(package_dir, arcname=f"{paths.program}_ai_package")

    return archive_path


def write_reports(paths: RunPaths, context: dict) -> None:
    """Write program report, AI context, AI handoff, and AI prompt."""
    program_report = build_program_report(context)
    policy_notes = read_policy(paths)
    ai_prompt = build_ai_prompt(paths.program)
    ai_handoff = build_ai_handoff(context, program_report, policy_notes)

    (paths.reports_dir / "program_report.md").write_text(
        program_report + "\n",
        encoding="utf-8",
    )
    (paths.reports_dir / "program_ai_context.json").write_text(
        json.dumps(context, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (paths.reports_dir / "ai_prompt.md").write_text(
        ai_prompt + "\n",
        encoding="utf-8",
    )
    (paths.reports_dir / "ai_handoff.md").write_text(
        ai_handoff + "\n",
        encoding="utf-8",
    )


def write_scope_files(paths: RunPaths, scope_data: ScopeData) -> None:
    """Write parsed scope files."""
    write_lines(paths.scope_dir / "in_scope_web_roots.txt", scope_data.roots)
    write_lines(paths.scope_dir / "mobile_assets.txt", scope_data.mobile_assets)
    write_lines(paths.scope_dir / "excluded_assets.txt", scope_data.excluded_assets)


def write_tool_statuses(paths: RunPaths, statuses: list[ToolStatus]) -> None:
    """Write tool statuses to JSON."""
    (paths.raw_dir / "tool_status.json").write_text(
        json.dumps([asdict(status) for status in statuses], indent=2) + "\n",
        encoding="utf-8",
    )


def apply_policy_file(paths: RunPaths, policy_file: str | None) -> None:
    """Copy a provided policy file into the run folder."""
    if not policy_file:
        return

    source = Path(policy_file).expanduser()

    if not source.exists():
        raise FileNotFoundError(f"Policy file not found: {source}")

    destination = paths.scope_dir / "policy_notes.md"
    destination.write_text(
        source.read_text(encoding="utf-8", errors="replace"),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(
        prog="reconforge_one.py",
        description="One-shot program-level passive recon for authorized testing.",
    )

    parser.add_argument(
        "--program",
        required=True,
        help="Program/run name, e.g. facebook, tiktok, hackerone-tiktok.",
    )

    parser.add_argument(
        "--root",
        action="append",
        help="In-scope root domain. Can be used multiple times.",
    )

    parser.add_argument(
        "--roots-file",
        help="File containing in-scope root domains.",
    )

    parser.add_argument(
        "--scope-csv",
        help="HackerOne-style scope CSV.",
    )

    parser.add_argument(
        "--policy-file",
        help="Optional Markdown/text file containing official program policy notes.",
    )

    parser.add_argument(
        "--out-dir",
        default="recon_runs",
        help="Output base directory. Default: recon_runs",
    )

    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_TOOLS),
        default="standard",
        help="Run profile: light, standard, deep, report-only.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Timeout per tool command in seconds. Default: 900",
    )

    parser.add_argument(
        "--max-heavy-hosts",
        type=int,
        default=100,
        help=(
            "Maximum live hosts passed to heavier tools such as whatweb and katana "
            "in standard/deep profiles. Default: 100"
        ),
    )

    parser.add_argument(
        "--limit-roots",
        type=int,
        default=None,
        help="Limit number of roots for testing.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands and create structure without executing tools.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logs.",
    )

    return parser.parse_args()


def main() -> int:
    """Run ReconForge One."""
    args = parse_args()

    paths = build_paths(program=args.program, out_dir=Path(args.out_dir))
    create_policy_template(paths)

    logger = setup_logger(paths.logs_dir / "reconforge_one.log", args.verbose)

    logger.info("ReconForge One started.")
    logger.info("Program: %s", paths.program)
    logger.info("Profile: %s", args.profile)
    logger.info("Workspace: %s", paths.root)
    logger.info("Dry run: %s", args.dry_run)

    try:
        apply_policy_file(paths, getattr(args, "policy_file", None))
    except Exception as exc:
        logger.error("Policy file error: %s", exc)
        return 2

    try:
        scope_data = parse_roots(args, paths)
    except Exception as exc:
        logger.error("Scope error: %s", exc)
        return 2

    if args.limit_roots is not None:
        scope_data.roots = scope_data.roots[: args.limit_roots]

    write_scope_files(paths, scope_data)

    tools = PROFILE_TOOLS[args.profile]
    statuses: list[ToolStatus] = []

    if args.profile != "report-only":
        logger.info("Root targets: %s", len(scope_data.roots))
        logger.info("Tools: %s", ", ".join(tools) or "none")

        statuses.extend(
            run_subdomain_tools(
                roots=scope_data.roots,
                paths=paths,
                tools=tools,
                logger=logger,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
        )

    statuses.extend(
        build_clean_outputs(
            roots=scope_data.roots,
            paths=paths,
            logger=logger,
            timeout=args.timeout,
            dry_run=args.dry_run,
            should_resolve=True,
        )
    )

    if args.profile != "report-only":
        statuses.append(
            run_httpx(
                input_file=paths.clean_dir / "subdomains_resolved.txt",
                output_file=paths.raw_dir / "httpx.txt",
                logger=logger,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
        )

        build_url_clean_outputs(paths)

        statuses.extend(
            run_url_tools(
                live_hosts_file=paths.clean_dir / "live_hosts.txt",
                roots=scope_data.roots,
                paths=paths,
                tools=tools,
                profile=args.profile,
                logger=logger,
                timeout=args.timeout,
                dry_run=args.dry_run,
                max_heavy_hosts=args.max_heavy_hosts,
            )
        )

    build_url_clean_outputs(paths)

    write_tool_statuses(paths, statuses)
    context = build_context(paths, statuses)
    write_reports(paths, context)
    ai_package_path = write_ai_package(paths)

    logger.info("AI package generated: %s", ai_package_path)
    logger.info("ReconForge One completed.")

    print("ReconForge One completed.")
    print(f"Workspace: {paths.root}")
    print(f"AI Handoff: {paths.reports_dir / 'ai_handoff.md'}")
    print(f"AI Context: {paths.reports_dir / 'program_ai_context.json'}")
    print(f"AI Package: {ai_package_path}")
    print(f"Policy notes: {paths.scope_dir / 'policy_notes.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
