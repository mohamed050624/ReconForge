"""Logging setup for ReconForge."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logger(log_file: Path, verbose: bool = False) -> logging.Logger:
    """
    Configure the main ReconForge logger.

    Logs go to:
    - terminal
    - workspace log file
    """
    logger = logging.getLogger("reconforge")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False

    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
