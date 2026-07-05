"""Markdown report generation for ReconForge V1."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.workspace import WorkspacePaths


REPORT_FILENAME = "final_report.md"

RAW_FILES = {
    "subfinder_subdomains": "subdomains_subfinder.txt",
    "assetfinder_subdomains": "subdomains_assetfinder.txt",
    "live_hosts": "live_hosts_httpx.txt",
    "technologies": "technologies_whatweb.txt",
    "katana_urls": "urls_katana.txt",
    "gau_urls": "urls_gau.txt",
    "waybackurls": "urls_waybackurls.txt",
}

PROCESSED_FILES = {
    "combined_subdomains": "subdomains_combined.txt",
}


def _read_lines(path: Path) -> list[str]:
    """Read non-empty stripped lines from a file if it exists."""
    if not path.exists():
        return []

    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def _deduplicate(values: list[str]) -> list[str]:
    """Return sorted unique values."""
    return sorted(set(values))


def _format_sample(values: list[str], limit: int = 20) -> str:
    """Format a small sample list for Markdown output."""
    if not values:
        return "_No data collected yet._"

    sample = values[:limit]
    rendered = "\n".join(f"- `{item}`" for item in sample)

    remaining_count = len(values) - len(sample)

    if remaining_count > 0:
        rendered += f"\n- _...and {remaining_count} more._"

    return rendered


def _section(title: str, values: list[str], limit: int = 20) -> str:
    """Build a Markdown section with count and sample values."""
    unique_values = _deduplicate(values)

    return (
        f"## {title}\n\n"
        f"**Count:** {len(unique_values)}\n\n"
        f"{_format_sample(unique_values, limit=limit)}\n"
    )


def load_report_data(workspace: WorkspacePaths) -> dict[str, list[str]]:
    """Load all available ReconForge output files for reporting."""
    data: dict[str, list[str]] = {}

    for key, filename in RAW_FILES.items():
        data[key] = _read_lines(workspace.raw_dir / filename)

    for key, filename in PROCESSED_FILES.items():
        data[key] = _read_lines(workspace.processed_dir / filename)

    all_subdomains = (
        data.get("combined_subdomains")
        or data.get("subfinder_subdomains", [])
        + data.get("assetfinder_subdomains", [])
    )

    all_urls = (
        data.get("katana_urls", [])
        + data.get("gau_urls", [])
        + data.get("waybackurls", [])
    )

    data["all_subdomains"] = _deduplicate(all_subdomains)
    data["all_urls"] = _deduplicate(all_urls)

    return data


def build_markdown_report(target: str, workspace: WorkspacePaths) -> str:
    """Build the ReconForge Markdown report content."""
    data = load_report_data(workspace)

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    sections = [
        "# ReconForge V1 Report",
        "",
        "## Scan Metadata",
        "",
        f"- **Target:** `{target}`",
        f"- **Generated at:** `{generated_at}`",
        f"- **Workspace:** `{workspace.root}`",
        "",
        "## Executive Summary",
        "",
        f"- **Unique subdomains:** {len(data['all_subdomains'])}",
        f"- **Live hosts:** {len(_deduplicate(data['live_hosts']))}",
        f"- **Technology fingerprints:** {len(_deduplicate(data['technologies']))}",
        f"- **Discovered URLs:** {len(data['all_urls'])}",
        "",
        _section("Subdomains", data["all_subdomains"]),
        "",
        _section("Live Hosts", data["live_hosts"]),
        "",
        _section("Technology Fingerprints", data["technologies"]),
        "",
        _section("Discovered URLs", data["all_urls"], limit=30),
        "",
        "## Suggested Manual Review Areas",
        "",
        "- Review live hosts with unusual status codes or titles.",
        "- Prioritize admin panels, login pages, APIs, staging hosts, and old URLs.",
        "- Compare discovered technologies against known outdated stacks.",
        "- Inspect archived URLs for forgotten endpoints, parameters, and exposed files.",
        "- Confirm every asset is inside the authorized testing scope before manual testing.",
        "",
        "## Notes",
        "",
        "This report is generated from passive/authorized reconnaissance outputs.",
        "It does not perform exploitation or destructive testing.",
        "",
    ]

    return "\n".join(sections)


def generate_markdown_report(target: str, workspace: WorkspacePaths) -> Path:
    """Generate final Markdown report and return its path."""
    report_path = workspace.reports_dir / REPORT_FILENAME
    report_path.parent.mkdir(parents=True, exist_ok=True)

    content = build_markdown_report(target=target, workspace=workspace)
    report_path.write_text(content, encoding="utf-8")

    return report_path
