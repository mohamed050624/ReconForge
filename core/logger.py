"""Logging setup for ReconForge."""

from __future__ import annotations

import logging
from pathlib import Path


LOGGER_NAME = "reconforge"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(log_file: Path | None = None, verbose: bool = False) -> logging.Logger:
    """Configure and return the ReconForge logger.

    The function is idempotent: calling it multiple times replaces previous
    handlers instead of duplicating log lines.

    Args:
        log_file: Optional file path to write logs to.
        verbose: If True, console logging uses DEBUG level.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
