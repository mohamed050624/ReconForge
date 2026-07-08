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

from reconforge_v1.context import build_context, read_policy
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
from reconforge_v1.processing import build_clean_outputs, build_url_clean_outputs
from reconforge_v1.reports import (
    build_ai_handoff,
    build_ai_prompt,
    build_program_report,
)
from reconforge_v1.scope import (
    apply_policy_file,
    create_policy_template,
    parse_roots,
    write_scope_files,
)
from reconforge_v1.tools import (
    extract_httpx_urls,
    run_dnsx_or_fallback,
    run_httpx,
    run_subdomain_tools,
    run_url_tools,
)
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


def write_tool_statuses(paths: RunPaths, statuses: list[ToolStatus]) -> None:
    """Write tool statuses to JSON."""
    (paths.raw_dir / "tool_status.json").write_text(
        json.dumps([asdict(status) for status in statuses], indent=2) + "\n",
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
