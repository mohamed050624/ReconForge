"""Configuration loading utilities for ReconForge.

This module is intentionally small for V1. It loads a YAML configuration file,
merges it with safe defaults, and returns a plain dictionary that the rest of the
application can use without knowing anything about YAML.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    """Raised when the ReconForge configuration cannot be loaded."""


DEFAULT_CONFIG: dict[str, Any] = {
    "workspace": {
        "base_dir": "workspaces",
    },
    "runner": {
        "timeout_seconds": 300,
        "dry_run": False,
    },
    "tools": {
        "subfinder": {"enabled": True},
        "assetfinder": {"enabled": True},
        "amass": {"enabled": False},
        "httpx": {"enabled": True},
        "whatweb": {"enabled": True},
        "katana": {"enabled": True},
        "gau": {"enabled": True},
        "waybackurls": {"enabled": True},
    },
}


def load_config(config_path: Path | str = "config.yaml") -> dict[str, Any]:
    """Load ReconForge configuration from YAML.

    Missing configuration files are allowed in Fast V1 mode. In that case, the
    default configuration is returned. This keeps the CLI usable immediately
    after cloning the repository.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        A dictionary containing default values merged with file values.

    Raises:
        ConfigError: If the YAML file is invalid or does not contain a mapping.
    """
    path = Path(config_path)
    config = deepcopy(DEFAULT_CONFIG)

    if not path.exists():
        return config

    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML configuration: {path}") from exc
    except OSError as exc:
        raise ConfigError(f"Unable to read configuration: {path}") from exc

    if loaded is None:
        return config

    if not isinstance(loaded, dict):
        raise ConfigError("Configuration file must contain a YAML mapping.")

    return _deep_merge(config, loaded)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override values into base values."""
    result = deepcopy(base)

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)

    return result
