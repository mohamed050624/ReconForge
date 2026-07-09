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
from pathlib import Path

from reconforge_v1.context import build_context
from reconforge_v1.constants import PROFILE_TOOLS
from reconforge_v1.logging_config import setup_logger
from reconforge_v1.models import ToolStatus
from reconforge_v1.package import write_ai_package
from reconforge_v1.paths import build_paths
from reconforge_v1.processing import build_clean_outputs, build_url_clean_outputs
from reconforge_v1.reports import write_reports
from reconforge_v1.scope import (
    apply_policy_file,
    create_policy_template,
    parse_roots,
    write_scope_files,
)
from reconforge_v1.status import write_tool_statuses
from reconforge_v1.tools import run_httpx, run_subdomain_tools, run_url_tools


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
