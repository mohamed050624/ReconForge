"""Shared command runner for ReconForge tool integrations."""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from core.logger import LOGGER_NAME


@dataclass(frozen=True)
class ToolResult:
    """Result returned after running an external command."""

    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str
    output_file: Path | None = None
    skipped: bool = False
    reason: str | None = None

    @property
    def succeeded(self) -> bool:
        """Return True when the command completed successfully."""
        return self.return_code == 0 and not self.skipped


class ToolRunner:
    """Run external recon tools through one controlled interface."""

    def __init__(
        self,
        timeout_seconds: int = 300,
        dry_run: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.dry_run = dry_run
        self.logger = logger or logging.getLogger(LOGGER_NAME)

    def run(
        self,
        command: Sequence[str],
        output_file: Path | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ToolResult:
        """Run a command and optionally write stdout to a file.

        Args:
            command: Command as a sequence, never as a shell string.
            output_file: Optional file where stdout is written.
            cwd: Optional working directory.
            env: Optional environment variables.

        Returns:
            ToolResult containing stdout, stderr, and status.
        """
        normalized = tuple(str(part) for part in command if str(part).strip())

        if not normalized:
            raise ValueError("Command cannot be empty.")

        executable = normalized[0]
        command_text = " ".join(normalized)

        if shutil.which(executable) is None:
            reason = f"Executable not found: {executable}"
            self.logger.warning("Skipping command. %s", reason)
            return ToolResult(
                command=normalized,
                return_code=127,
                stdout="",
                stderr=reason,
                output_file=output_file,
                skipped=True,
                reason=reason,
            )

        if self.dry_run:
            self.logger.info("Dry run: %s", command_text)
            return ToolResult(
                command=normalized,
                return_code=0,
                stdout="",
                stderr="",
                output_file=output_file,
                skipped=True,
                reason="dry_run",
            )

        self.logger.info("Running command: %s", command_text)

        try:
            completed = subprocess.run(
                normalized,
                cwd=cwd,
                env=dict(env) if env is not None else None,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stderr = f"Command timed out after {self.timeout_seconds} seconds."
            self.logger.error("%s Command: %s", stderr, command_text)
            return ToolResult(
                command=normalized,
                return_code=124,
                stdout=exc.stdout or "",
                stderr=stderr,
                output_file=output_file,
                skipped=False,
                reason="timeout",
            )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""

        if output_file is not None and stdout:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(stdout, encoding="utf-8")

        if completed.returncode == 0:
            self.logger.info("Command completed successfully: %s", executable)
        else:
            self.logger.warning(
                "Command failed with code %s: %s",
                completed.returncode,
                command_text,
            )

        return ToolResult(
            command=normalized,
            return_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            output_file=output_file,
        )
