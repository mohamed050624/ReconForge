"""General utility helpers for ReconForge V1."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from reconforge_v1.constants import DOMAIN_RE


def utc_now() -> str:
    """Return current UTC timestamp."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_name(value: str) -> str:
    """Convert an arbitrary value into a filesystem-safe name."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    cleaned = cleaned.strip(".-_")
    if not cleaned:
        raise ValueError("Name produced an empty safe value.")
    return cleaned


def clean_domain(value: str) -> str | None:
    """Normalize URL/domain/wildcard into a clean hostname."""
    item = value.strip().lower()

    if not item:
        return None

    if item.startswith(("http://", "https://")):
        parsed = urlparse(item)
        item = parsed.hostname or ""

    item = item.strip().strip("/")

    if item.startswith("*."):
        item = item[2:]

    item = item.lstrip("*").strip()

    if ":" in item:
        item = item.split(":", 1)[0]

    if not DOMAIN_RE.match(item):
        return None

    return item


def normalize_url(value: str) -> str | None:
    """Normalize a URL and remove obvious trailing junk."""
    url = value.strip()

    if not url.startswith(("http://", "https://")):
        return None

    url = url.rstrip(".,;)'\"<>]}")

    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return None

    host = parsed.hostname
    if not host:
        return None

    return url


def unique_sorted(values: Iterable[str]) -> list[str]:
    """Return sorted unique non-empty values."""
    return sorted({value.strip() for value in values if value and value.strip()})


def read_lines(path: Path) -> list[str]:
    """Read clean lines from a file if it exists."""
    if not path.exists():
        return []

    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def write_lines(path: Path, values: Iterable[str]) -> None:
    """Write unique sorted lines to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = unique_sorted(values)
    path.write_text("\n".join(data) + ("\n" if data else ""), encoding="utf-8")


def append_text(path: Path, text: str) -> None:
    """Append text to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(text)
