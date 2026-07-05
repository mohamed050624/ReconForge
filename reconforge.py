"""ReconForge Fast V1 CLI entrypoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from core.config import load_config
from core.logger import setup_logger
from core.targets import InvalidTargetError, normalize_target
from core.tool_runner import ToolRunner
from core.workspace import WorkspacePaths, create_workspace
from modules.assetfinder import run_assetfinder
from modules.subfinder import run_subfinder


ToolFunction = Callable[[str, WorkspacePaths, ToolRunner, object], object]


AVAILABLE_TOOLS: dict[str, ToolFunction] = {
    "subfinder": run_subfinder,
    "assetfinder": run_assetfinder,
}


def parse_tool_selection(raw_tools: str | None) -> list[str]:
    """
    Parse tool selection from CLI.

    Examples:
        --tools subfinder
        --tools subfinder,assetfinder
        --tools all
    """
    if raw_tools is None:
        return []

    values = [
        item.strip().lower()
        for item in raw_tools.replace(",", " ").split()
        if item.strip()
    ]

    if "all" in values:
        return list(AVAILABLE_TOOLS.keys())

    return values


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="ReconForge",
        description=(
            "ReconForge V1: authorized reconnaissance orchestration framework."
        ),
    )

    parser.add_argument(
        "--target",
        required=True,
        help="Authorized target domain or host, e.g. example.com",
    )

    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config YAML file. Default: config.yaml",
    )

    parser.add_argument(
        "--workspace-dir",
        default=None,
        help="Override workspace base directory.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Override external tool timeout in seconds.",
    )

    parser.add_argument(
        "--tools",
        default=None,
        help="Tools to run. Example: subfinder,assetfinder or all",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing external tools.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    return parser


def main() -> int:
    """Run ReconForge CLI."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        target = normalize_target(args.target)
    except InvalidTargetError as exc:
        print(f"Invalid target: {exc}", file=sys.stderr)
        return 2

    config = load_config(Path(args.config))

    workspace_base_dir = (
        args.workspace_dir
        or config.get("workspace", {}).get("base_dir", "workspaces")
    )

    workspace = create_workspace(target=target, base_dir=workspace_base_dir)
    log_file = workspace.logs_dir / "reconforge.log"
    logger = setup_logger(log_file=log_file, verbose=args.verbose)

    runner_config = config.get("runner", {})
    timeout_seconds = args.timeout or int(runner_config.get("timeout_seconds", 300))
    dry_run = bool(args.dry_run or runner_config.get("dry_run", False))

    runner = ToolRunner(
        timeout_seconds=timeout_seconds,
        dry_run=dry_run,
        logger=logger,
    )

    selected_tools = parse_tool_selection(args.tools)

    logger.info("ReconForge Fast V1 started.")
    logger.info("Target: %s", target)
    logger.info("Workspace: %s", workspace.root)
    logger.info("Timeout: %s seconds", timeout_seconds)
    logger.info("Dry run: %s", dry_run)
    logger.debug("Loaded config: %s", config)
    logger.debug("Selected tools: %s", selected_tools)

    if not selected_tools:
        print("ReconForge Fast V1 foundation initialized successfully.")
        print(f"Target: {target}")
        print(f"Workspace: {workspace.root}")
        print("Next step: run a tool, e.g. --tools subfinder")
        return 0

    unknown_tools = [
        tool_name for tool_name in selected_tools if tool_name not in AVAILABLE_TOOLS
    ]

    if unknown_tools:
        logger.error("Unknown tool(s): %s", ", ".join(unknown_tools))
        logger.error("Available tools: %s", ", ".join(AVAILABLE_TOOLS))
        return 2

    failed_tools: list[str] = []

    for tool_name in selected_tools:
        tool_config = config.get("tools", {}).get(tool_name, {})
        enabled = bool(tool_config.get("enabled", True))

        if not enabled:
            logger.info("Skipping disabled tool: %s", tool_name)
            continue

        tool_function = AVAILABLE_TOOLS[tool_name]
        result = tool_function(target, workspace, runner, logger)

        if hasattr(result, "success") and not result.success:
            failed_tools.append(tool_name)

    if failed_tools:
        logger.error("ReconForge completed with failed tools: %s", failed_tools)
        return 1

    logger.info("ReconForge Fast V1 run completed.")
    print("ReconForge Fast V1 run completed.")
    print(f"Workspace: {workspace.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
