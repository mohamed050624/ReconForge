"""AI-ready context generation for ReconForge V1."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.workspace import WorkspacePaths
from report import load_report_data


AI_CONTEXT_FILENAME = "ai_context.json"


def _unique(values: list[str]) -> list[str]:
    """Return sorted unique values."""
    return sorted(set(values))


def _relative_path(path: Path, base: Path) -> str:
    """Return a safe relative path string when possible."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _existing_source_files(workspace: WorkspacePaths) -> dict[str, str]:
    """Return existing ReconForge output files used by the AI context."""
    candidates = {
        "subfinder_subdomains": workspace.raw_dir / "subdomains_subfinder.txt",
        "assetfinder_subdomains": workspace.raw_dir / "subdomains_assetfinder.txt",
        "combined_subdomains": workspace.processed_dir / "subdomains_combined.txt",
        "live_hosts": workspace.raw_dir / "live_hosts_httpx.txt",
        "technologies": workspace.raw_dir / "technologies_whatweb.txt",
        "katana_urls": workspace.raw_dir / "urls_katana.txt",
        "gau_urls": workspace.raw_dir / "urls_gau.txt",
        "waybackurls": workspace.raw_dir / "urls_waybackurls.txt",
        "markdown_report": workspace.reports_dir / "final_report.md",
    }

    return {
        key: _relative_path(path, workspace.root)
        for key, path in candidates.items()
        if path.exists()
    }


def build_ai_context(target: str, workspace: WorkspacePaths) -> dict[str, Any]:
    """
    Build AI-ready ReconForge context.

    This output is designed for safe, authorized manual testing analysis.
    It does not include exploitation instructions.
    """
    data = load_report_data(workspace)

    subdomains = _unique(data.get("all_subdomains", []))
    live_hosts = _unique(data.get("live_hosts", []))
    technologies = _unique(data.get("technologies", []))
    urls = _unique(data.get("all_urls", []))

    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "schema_version": "reconforge.v1.ai_context",
        "generated_at": generated_at,
        "target": target,
        "workspace": str(workspace.root),
        "purpose": (
            "AI-ready reconnaissance context for authorized Bug Bounty "
            "and penetration testing review."
        ),
        "safety_boundaries": {
            "authorized_scope_required": True,
            "no_exploitation_automation": True,
            "no_destructive_testing": True,
            "no_credential_attacks": True,
            "no_social_engineering": True,
            "human_reviewer_required": True,
        },
        "summary": {
            "unique_subdomains": len(subdomains),
            "live_hosts": len(live_hosts),
            "technology_fingerprints": len(technologies),
            "discovered_urls": len(urls),
        },
        "assets": {
            "subdomains": subdomains,
            "live_hosts": live_hosts,
            "technologies": technologies,
            "urls": urls,
        },
        "source_files": _existing_source_files(workspace),
        "recommended_ai_task": {
            "role": (
                "Act as a security analyst assisting with an authorized "
                "Bug Bounty reconnaissance review."
            ),
            "objective": (
                "Analyze the collected reconnaissance data and produce a "
                "safe manual testing plan prioritized by likely impact and "
                "testing value."
            ),
            "expected_output_sections": [
                "Scope confirmation checklist",
                "Attack surface summary",
                "High-priority assets",
                "Interesting endpoints and parameters",
                "Likely vulnerability categories to manually review",
                "Non-destructive validation ideas",
                "Missing reconnaissance data",
                "Risk-ranked testing order",
            ],
            "manual_review_focus": [
                "Authentication and authorization boundaries",
                "Access control issues",
                "Exposed admin or staging interfaces",
                "API endpoints",
                "Input handling and reflected parameters",
                "File upload surfaces",
                "Outdated or unusual technologies",
                "Archived endpoints that may still be reachable",
                "Sensitive files or accidental exposure indicators",
            ],
            "rules": [
                "Only analyze assets that are inside the authorized scope.",
                "Do not suggest destructive testing.",
                "Do not suggest credential attacks.",
                "Do not suggest persistence, evasion, malware, or exfiltration.",
                "Keep recommendations focused on ethical manual testing.",
                "Mark any uncertain asset as requiring scope verification.",
            ],
        },
    }


def generate_ai_context(target: str, workspace: WorkspacePaths) -> Path:
    """Generate AI context JSON and return its path."""
    output_path = workspace.reports_dir / AI_CONTEXT_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)

    context = build_ai_context(target=target, workspace=workspace)

    output_path.write_text(
        json.dumps(context, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return output_path
