"""Configuration loading for ReconForge."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "workspace": {
        "base_dir": "workspaces",
    },
    "runner": {
        "timeout_seconds": 300,
        "dry_run": False,
    },
    "tools": {
        "subfinder": {
            "enabled": True,
        },
        "assetfinder": {
            "enabled": True,
        },
        "amass": {
            "enabled": False,
        },
        "httpx": {
            "enabled": True,
        },
        "whatweb": {
            "enabled": True,
        },
        "katana": {
            "enabled": True,
        },
        "gau": {
            "enabled": True,
        },
        "waybackurls": {
            "enabled": True,
        },
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override values into base recursively."""
    merged = deepcopy(base)

    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value

    return merged


def load_config(config_path: Path | str = "config.yaml") -> dict[str, Any]:
    """
    Load YAML config.

    If config.yaml does not exist or is empty, safe defaults are used.
    """
    path = Path(config_path)

    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)

    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a YAML object: {path}")

    return _deep_merge(DEFAULT_CONFIG, loaded)
