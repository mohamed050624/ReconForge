"""AI context generation for ReconForge V1."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict

from reconforge_v1.models import RunPaths, ToolStatus
from reconforge_v1.utils import read_lines, utc_now


def sample(values: list[str], limit: int = 50) -> list[str]:
    """Return bounded sample for reports/context."""
    return values[:limit]


def count_by_host(urls: list[str]) -> list[dict[str, int | str]]:
    """Count URLs by host."""
    counter: Counter[str] = Counter()

    for url in urls:
        host = urlparse(url).hostname
        if host:
            counter[host] += 1

    return [
        {"host": host, "count": count}
        for host, count in counter.most_common(50)
    ]


def read_policy(paths: RunPaths) -> str:
    """Read policy notes."""
    return (paths.scope_dir / "policy_notes.md").read_text(
        encoding="utf-8",
        errors="replace",
    )


def build_context(paths: RunPaths, tool_statuses: list[ToolStatus]) -> dict:
    """Build program-level AI context."""
    roots = read_lines(paths.clean_dir / "roots.txt")
    subdomains = read_lines(paths.clean_dir / "subdomains_all.txt")
    resolved = read_lines(paths.clean_dir / "subdomains_resolved.txt")
    live_hosts = read_lines(paths.clean_dir / "live_hosts.txt")
    urls = read_lines(paths.clean_dir / "urls_unique.txt")
    api_hosts = read_lines(paths.clean_dir / "api_base_hosts.txt")
    api_endpoints = read_lines(paths.clean_dir / "api_endpoints.txt")
    api_params = read_lines(paths.clean_dir / "api_params.txt")
    graphql = read_lines(paths.clean_dir / "graphql_candidates.txt")
    swagger = read_lines(paths.clean_dir / "swagger_openapi_candidates.txt")
    auth = read_lines(paths.clean_dir / "auth_endpoints.txt")
    uploads = read_lines(paths.clean_dir / "upload_endpoints.txt")
    params = read_lines(paths.clean_dir / "params.txt")
    js_files = read_lines(paths.clean_dir / "js_files.txt")
    interesting = read_lines(paths.clean_dir / "interesting_urls.txt")
    technologies = read_lines(paths.clean_dir / "technologies.txt")
    high_signal = read_lines(paths.clean_dir / "high_signal_assets.txt")
    mobile_assets = read_lines(paths.scope_dir / "mobile_assets.txt")
    excluded_assets = read_lines(paths.scope_dir / "excluded_assets.txt")

    return {
        "schema_version": "reconforge.one.v1",
        "generated_at": utc_now(),
        "program": paths.program,
        "workspace": str(paths.root),
        "purpose": (
            "AI-ready reconnaissance context for authorized Bug Bounty "
            "and penetration testing manual review."
        ),
        "safety_boundaries": {
            "authorized_scope_required": True,
            "no_exploitation_automation": True,
            "no_destructive_testing": True,
            "no_denial_of_service": True,
            "no_credential_attacks": True,
            "no_social_engineering": True,
            "human_reviewer_required": True,
        },
        "summary": {
            "root_targets": len(roots),
            "subdomains_discovered": len(subdomains),
            "subdomains_resolved": len(resolved),
            "live_hosts": len(live_hosts),
            "urls": len(urls),
            "api_hosts": len(api_hosts),
            "api_endpoints": len(api_endpoints),
            "api_urls_with_params": len(api_params),
            "parameters": len(params),
            "graphql_candidates": len(graphql),
            "swagger_openapi_candidates": len(swagger),
            "auth_endpoints": len(auth),
            "upload_endpoints": len(uploads),
            "js_files": len(js_files),
            "technology_fingerprints": len(technologies),
            "mobile_assets_not_scanned": len(mobile_assets),
            "excluded_assets": len(excluded_assets),
        },
        "scope": {
            "roots": roots,
            "mobile_assets_not_scanned": mobile_assets,
            "excluded_assets": sample(excluded_assets, 200),
        },
        "assets": {
            "subdomains_sample": sample(subdomains, 200),
            "resolved_subdomains_sample": sample(resolved, 200),
            "live_hosts_sample": sample(live_hosts, 200),
            "high_signal_assets": sample(high_signal, 200),
        },
        "urls": {
            "top_hosts_by_url_count": count_by_host(urls),
            "interesting_urls_sample": sample(interesting, 300),
            "all_urls_file": "02_clean/urls_unique.txt",
        },
        "api_attack_surface": {
            "api_hosts": sample(api_hosts, 200),
            "api_endpoints_sample": sample(api_endpoints, 300),
            "api_params_sample": sample(api_params, 200),
            "graphql_candidates": sample(graphql, 200),
            "swagger_openapi_candidates": sample(swagger, 200),
            "auth_endpoints_sample": sample(auth, 200),
            "upload_endpoints_sample": sample(uploads, 200),
            "parameters": sample(params, 300),
        },
        "javascript": {
            "js_files_sample": sample(js_files, 200),
        },
        "technology_fingerprints_sample": sample(technologies, 200),
        "tool_statuses": [asdict(status) for status in tool_statuses],
        "important_files": {
            "policy_notes": "00_scope/policy_notes.md",
            "roots": "02_clean/roots.txt",
            "subdomains": "02_clean/subdomains_all.txt",
            "live_hosts": "02_clean/live_hosts.txt",
            "urls": "02_clean/urls_unique.txt",
            "api_endpoints": "02_clean/api_endpoints.txt",
            "interesting_urls": "02_clean/interesting_urls.txt",
            "ai_handoff": "03_reports/ai_handoff.md",
        },
    }
