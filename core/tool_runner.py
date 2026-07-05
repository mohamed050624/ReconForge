"""Shared command runner for external reconnaissance tools."""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolRunResult:
    """Result returned after running an external tool."""

    tool_name: str
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    output_file: Path | None
    success: bool
    dry_run: bool


class ToolRunner:
    """
    Safe shared runner for all ReconForge tool wrappers.

    Design rules:
    - no shell=True
    - one execution path for all external tools
    - supports dry-run
    - writes stdout to output files when requested
    """

    def __init__(
        self,
        timeout_seconds: int = 300,
        dry_run: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.dry_run = dry_run
        self.logger = logger or logging.getLogger("reconforge")

    def run(
        self,
        command: list[str],
        output_file: Path | None = None,
        cwd: Path | None = None,
    ) -> ToolRunResult:
        """Run a command and optionally save stdout to a file."""
        if not command:
            raise ValueError("Command cannot be empty.")

        tool_name = command[0]

        if self.dry_run:
            self.logger.info("Dry run: %s", " ".join(command))
            return ToolRunResult(
                tool_name=tool_name,
                command=command,
                return_code=0,
                stdout="",
                stderr="",
                output_file=output_file,
                success=True,
                dry_run=True,
            )

        if shutil.which(tool_name) is None:
            message = f"Executable not found: {tool_name}"
            self.logger.error(message)
            return ToolRunResult(
                tool_name=tool_name,
                command=command,
                return_code=127,
                stdout="",
                stderr=message,
                output_file=output_file,
                success=False,
                dry_run=False,
            )

        self.logger.info("Running: %s", " ".join(command))

        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            message = (
                f"Tool timed out after {self.timeout_seconds} seconds: {tool_name}"
            )
            self.logger.error(message)
            return ToolRunResult(
                tool_name=tool_name,
                command=command,
                return_code=124,
                stdout=exc.stdout or "",
                stderr=message,
                output_file=output_file,
                success=False,
                dry_run=False,
            )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""

        if output_file is not None:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(stdout, encoding="utf-8")

        success = completed.returncode == 0

        if success:
            self.logger.info("%s completed successfully.", tool_name)
        else:
            self.logger.error(
                "%s failed with exit code %s.",
                tool_name,
                completed.returncode,
            )
            if stderr:
                self.logger.debug("stderr: %s", stderr.strip())

        return ToolRunResult(
            tool_name=tool_name,
            command=command,
            return_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            output_file=output_file,
            success=success,
            dry_run=False,
        )
