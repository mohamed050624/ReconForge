"""Clean output processing for ReconForge V1."""

from __future__ import annotations

import logging
from typing import Iterable
from urllib.parse import parse_qsl, urlparse

from reconforge_v1.constants import (
    API_HOST_KEYWORDS,
    API_PATH_KEYWORDS,
    AUTH_KEYWORDS,
    GRAPHQL_KEYWORDS,
    INTERESTING_PATH_KEYWORDS,
    JS_EXTENSIONS,
    STATIC_EXTENSIONS,
    SWAGGER_OPENAPI_KEYWORDS,
    UPLOAD_KEYWORDS,
    URL_RE,
)
from reconforge_v1.models import RunPaths, ToolStatus
from reconforge_v1.tools import extract_httpx_urls, run_dnsx_or_fallback, run_httpx
from reconforge_v1.utils import (
    clean_domain,
    normalize_url,
    read_lines,
    unique_sorted,
    write_lines,
)


def collect_domains_from_raw(paths: RunPaths, roots: list[str]) -> list[str]:
    """Collect subdomains from raw discovery outputs."""
    values: list[str] = []
    values.extend(roots)

    for filename in ("subfinder.txt", "assetfinder.txt", "amass.txt"):
        for line in read_lines(paths.raw_dir / filename):
            cleaned = clean_domain(line)
            if cleaned:
                values.append(cleaned)

    return unique_sorted(values)


def collect_urls_from_raw(paths: RunPaths) -> list[str]:
    """
    Collect URLs from raw outputs.

    ProjectDiscovery httpx output is line-based and starts with the live URL,
    so we explicitly parse it before regex extraction.
    """
    urls: list[str] = []

    httpx_path = paths.raw_dir / "httpx.txt"
    if httpx_path.exists():
        urls.extend(extract_httpx_urls(read_lines(httpx_path)))

    for filename in ("gau.txt", "waybackurls.txt", "katana.txt", "httpx.txt"):
        path = paths.raw_dir / filename
        if not path.exists():
            continue

        content = path.read_text(encoding="utf-8", errors="replace")
        for match in URL_RE.findall(content):
            normalized = normalize_url(match)
            if normalized:
                urls.append(normalized)

    return unique_sorted(urls)


def get_url_path_lower(url: str) -> str:
    """Return lowercased URL path."""
    return (urlparse(url).path or "").lower()


def is_static_asset(url: str) -> bool:
    """Return True if URL looks like a static asset."""
    path = get_url_path_lower(url)
    return path.endswith(STATIC_EXTENSIONS)


def looks_like_api_host(host: str) -> bool:
    """Return True if hostname looks API-related."""
    host_lower = host.lower()
    return any(keyword in host_lower for keyword in API_HOST_KEYWORDS)


def looks_like_api_url(url: str) -> bool:
    """Return True if URL looks API-related."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if looks_like_api_host(host):
        return True

    return any(keyword in path for keyword in API_PATH_KEYWORDS)


def contains_any(value: str, keywords: Iterable[str]) -> bool:
    """Case-insensitive keyword containment check."""
    lower = value.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def extract_params(urls: list[str]) -> list[str]:
    """Extract unique query parameter names."""
    params: set[str] = set()

    for url in urls:
        parsed = urlparse(url)
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
            if key:
                params.add(key)

    return sorted(params)


def filter_urls(urls: list[str], predicate) -> list[str]:
    """Filter URLs by predicate."""
    return sorted({url for url in urls if predicate(url)})


def extract_js_files(urls: list[str]) -> list[str]:
    """Extract JS file URLs."""
    return filter_urls(
        urls,
        lambda url: get_url_path_lower(url).endswith(JS_EXTENSIONS),
    )


def extract_interesting_urls(urls: list[str]) -> list[str]:
    """Extract high-signal URLs based on path keywords and parameters."""
    interesting: set[str] = set()

    for url in urls:
        parsed = urlparse(url)
        signal_text = f"{parsed.netloc}{parsed.path}{parsed.query}".lower()

        if contains_any(signal_text, INTERESTING_PATH_KEYWORDS):
            interesting.add(url)

        if parsed.query:
            interesting.add(url)

    return sorted(interesting)


def build_clean_outputs(
    roots: list[str],
    paths: RunPaths,
    logger: logging.Logger,
    timeout: int,
    dry_run: bool,
    should_resolve: bool = True,
) -> list[ToolStatus]:
    """Clean raw outputs and write normalized program-level files."""
    statuses: list[ToolStatus] = []

    write_lines(paths.clean_dir / "roots.txt", roots)

    subdomains = collect_domains_from_raw(paths, roots)
    write_lines(paths.clean_dir / "subdomains_all.txt", subdomains)

    if should_resolve:
        status = run_dnsx_or_fallback(
            domains_file=paths.clean_dir / "subdomains_all.txt",
            output_file=paths.clean_dir / "subdomains_resolved.txt",
            logger=logger,
            timeout=timeout,
            dry_run=dry_run,
        )
        statuses.append(status)
    else:
        write_lines(paths.clean_dir / "subdomains_resolved.txt", subdomains)

    resolved = read_lines(paths.clean_dir / "subdomains_resolved.txt")
    if not resolved:
        resolved = subdomains
        write_lines(paths.clean_dir / "subdomains_resolved.txt", resolved)

    return statuses


def build_url_clean_outputs(paths: RunPaths) -> None:
    """Build URL/API/interesting endpoint outputs."""
    httpx_lines = read_lines(paths.raw_dir / "httpx.txt")
    live_urls = extract_httpx_urls(httpx_lines)
    write_lines(paths.clean_dir / "live_hosts.txt", live_urls)

    urls = collect_urls_from_raw(paths)
    write_lines(paths.clean_dir / "urls_all.txt", urls)

    non_static_urls = [url for url in urls if not is_static_asset(url)]
    write_lines(paths.clean_dir / "urls_unique.txt", non_static_urls)

    js_files = extract_js_files(urls)
    write_lines(paths.clean_dir / "js_files.txt", js_files)

    params = extract_params(non_static_urls)
    write_lines(paths.clean_dir / "params.txt", params)

    api_endpoints = filter_urls(non_static_urls, looks_like_api_url)
    write_lines(paths.clean_dir / "api_endpoints.txt", api_endpoints)

    api_params = [
        url
        for url in api_endpoints
        if urlparse(url).query
    ]
    write_lines(paths.clean_dir / "api_params.txt", api_params)

    graphql_candidates = filter_urls(
        non_static_urls,
        lambda url: contains_any(url, GRAPHQL_KEYWORDS),
    )
    write_lines(paths.clean_dir / "graphql_candidates.txt", graphql_candidates)

    swagger_candidates = filter_urls(
        non_static_urls,
        lambda url: contains_any(url, SWAGGER_OPENAPI_KEYWORDS),
    )
    write_lines(paths.clean_dir / "swagger_openapi_candidates.txt", swagger_candidates)

    auth_endpoints = filter_urls(
        non_static_urls,
        lambda url: contains_any(url, AUTH_KEYWORDS),
    )
    write_lines(paths.clean_dir / "auth_endpoints.txt", auth_endpoints)

    upload_endpoints = filter_urls(
        non_static_urls,
        lambda url: contains_any(url, UPLOAD_KEYWORDS),
    )
    write_lines(paths.clean_dir / "upload_endpoints.txt", upload_endpoints)

    interesting_urls = extract_interesting_urls(non_static_urls)
    write_lines(paths.clean_dir / "interesting_urls.txt", interesting_urls)

    technologies = read_lines(paths.raw_dir / "whatweb.txt")
    write_lines(paths.clean_dir / "technologies.txt", technologies)

    api_hosts: set[str] = set()
    for url in api_endpoints:
        host = urlparse(url).hostname
        if host:
            api_hosts.add(host)
    for host in read_lines(paths.clean_dir / "subdomains_all.txt"):
        if looks_like_api_host(host):
            api_hosts.add(host)
    write_lines(paths.clean_dir / "api_base_hosts.txt", api_hosts)

    high_signal = sorted(
        set(read_lines(paths.clean_dir / "api_base_hosts.txt"))
        | set(read_lines(paths.clean_dir / "graphql_candidates.txt")[:100])
        | set(read_lines(paths.clean_dir / "swagger_openapi_candidates.txt")[:100])
        | set(read_lines(paths.clean_dir / "auth_endpoints.txt")[:100])
        | set(read_lines(paths.clean_dir / "upload_endpoints.txt")[:100])
    )
    write_lines(paths.clean_dir / "high_signal_assets.txt", high_signal)
