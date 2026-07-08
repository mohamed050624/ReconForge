"""Target normalization helpers for ReconForge."""

from __future__ import annotations

import re
from urllib.parse import urlparse


class InvalidTargetError(ValueError):
    """Raised when a target value is empty or invalid."""


def normalize_target(raw_target: str) -> str:
    """
    Normalize a user-supplied target into a clean domain/host.

    Examples:
        https://example.com/path -> example.com
        http://sub.example.com:443 -> sub.example.com
        *.example.com -> example.com
    """
    target = raw_target.strip()

    if not target:
        raise InvalidTargetError("Target cannot be empty.")

    if "://" not in target:
        target = f"//{target}"

    parsed = urlparse(target)
    hostname = parsed.hostname

    if not hostname:
        raise InvalidTargetError(f"Invalid target: {raw_target}")

    hostname = hostname.lower().strip()

    if hostname.startswith("*."):
        hostname = hostname[2:]

    if not re.match(r"^[a-z0-9.-]+$", hostname):
        raise InvalidTargetError(f"Invalid hostname: {hostname}")

    return hostname


def workspace_safe_name(target: str) -> str:
    """
    Convert a normalized target into a safe folder name.
    """
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", target)
    safe_name = safe_name.strip("._-")

    if not safe_name:
        raise InvalidTargetError("Target produced an empty workspace name.")

    return safe_name
