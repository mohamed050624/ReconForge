"""ReconForge Fast V1 command-line entrypoint.

This is the first working foundation layer. It creates a workspace, loads config,
sets up logging, and prepares the shared ToolRunner. Tool integrations will be
wired in the next implementation batches.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from core.config import ConfigError, load_config
from core.logger import setup_logger
from core.tool_runner import ToolRunner
from core.workspace import WorkspaceError, create_workspace


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse ReconForge CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="reconforge",
        description=(
            "ReconForge V1: authorized reconnaissance orchestration framework."
        ),
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Authorized target domain or program identifier.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to ReconForge YAML config. Defaults to config.yaml.",
    )
    parser.add_argument(
        "--workspace-dir",
        default=None,
        help="Override workspace base directory from config.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Override command timeout in seconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare the run without executing external tools.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug console logging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run ReconForge Fast V1 foundation workflow."""
    args = parse_args(argv)

    try:
        config = load_config(args.config)
        workspace_base = _get_workspace_base(config, args.workspace_dir)
        workspace = create_workspace(args.target, workspace_base)
    except (ConfigError, WorkspaceError) as exc:
        fallback_logger = setup_logger(verbose=args.verbose)
        fallback_logger.error("Startup failed: %s", exc)
        return 1

    logger = setup_logger(workspace.logs / "reconforge.log", verbose=args.verbose)
    timeout_seconds = _get_timeout(config, args.timeout)
    dry_run = bool(args.dry_run or config.get("runner", {}).get("dry_run", False))

    runner = ToolRunner(
        timeout_seconds=timeout_seconds,
        dry_run=dry_run,
        logger=logger,
    )

    logger.info("ReconForge Fast V1 started.")
    logger.info("Target: %s", workspace.target)
    logger.info("Workspace: %s", workspace.root)
    logger.info("Timeout: %s seconds", timeout_seconds)
    logger.info("Dry run: %s", dry_run)
    logger.debug("Loaded config: %s", config)
    logger.debug("ToolRunner initialized: %s", runner)

    print("ReconForge Fast V1 foundation initialized successfully.")
    print(f"Target: {workspace.target}")
    print(f"Workspace: {workspace.root}")
    print("Next step: wire Subfinder as the first recon module.")

    return 0


def _get_workspace_base(config: dict[str, Any], override: str | None) -> Path:
    if override:
        return Path(override)

    workspace_config = config.get("workspace", {})
    base_dir = workspace_config.get("base_dir", "workspaces")
    return Path(str(base_dir))


def _get_timeout(config: dict[str, Any], override: int | None) -> int:
    if override is not None:
        return override

    runner_config = config.get("runner", {})
    timeout = runner_config.get("timeout_seconds", 300)

    try:
        timeout_value = int(timeout)
    except (TypeError, ValueError):
        return 300

    return max(timeout_value, 1)


if __name__ == "__main__":
    sys.exit(main())
