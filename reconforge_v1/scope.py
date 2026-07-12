"""Scope parsing and policy helpers for ReconForge V1."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from reconforge_v1.constants import MOBILE_ASSET_TYPES, WEB_ASSET_TYPES
from reconforge_v1.models import RunPaths, ScopeData
from reconforge_v1.utils import clean_domain, read_lines, write_lines


def create_policy_template(paths: RunPaths) -> None:
    """Create policy_notes.md if missing."""
    policy_path = paths.scope_dir / "policy_notes.md"

    if policy_path.exists():
        return

    content = f"""# Policy Notes for {paths.program}

Paste the official Bug Bounty / penetration testing policy here.

## Program URL

PASTE_OFFICIAL_PROGRAM_URL_HERE

## In Scope

Paste official in-scope assets here.

## Out of Scope

Paste official out-of-scope assets here.

## Rules / Restrictions

Paste official testing rules here.

Recommended safety notes:
- Only test assets clearly listed as in scope.
- Do not test assets listed as out of scope.
- Do not perform denial-of-service testing.
- Do not perform social engineering.
- Do not perform credential attacks.
- Do not access, modify, or exfiltrate user data.
- Stop and report if sensitive data is accidentally exposed.
"""
    policy_path.write_text(content, encoding="utf-8")


def parse_scope_csv(path: Path) -> ScopeData:
    """Parse HackerOne-style scope CSV."""
    roots: set[str] = set()
    mobile_assets: list[str] = []
    excluded_assets: list[str] = []

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        required = {
            "identifier",
            "asset_type",
            "eligible_for_bounty",
            "eligible_for_submission",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "scope CSV is missing required columns: "
                + ", ".join(sorted(missing))
            )

        for row in reader:
            identifier = (row.get("identifier") or "").strip()
            asset_type = (row.get("asset_type") or "").strip().upper()
            bounty = (row.get("eligible_for_bounty") or "").strip().lower()
            submission = (row.get("eligible_for_submission") or "").strip().lower()

            is_allowed = bounty == "true" and submission == "true"

            if asset_type in WEB_ASSET_TYPES and is_allowed:
                cleaned = clean_domain(identifier)
                if cleaned:
                    roots.add(cleaned)
                continue

            if asset_type in MOBILE_ASSET_TYPES and is_allowed:
                mobile_assets.append(f"{identifier} [{asset_type}]")
                continue

            excluded_assets.append(
                f"{identifier} [{asset_type}] bounty={bounty} submission={submission}"
            )

    return ScopeData(
        roots=sorted(roots),
        mobile_assets=sorted(mobile_assets),
        excluded_assets=sorted(excluded_assets),
    )


def parse_roots(args: argparse.Namespace, paths: RunPaths) -> ScopeData:
    """Resolve roots from --root, --roots-file, and/or --scope-csv."""
    roots: set[str] = set()
    mobile_assets: list[str] = []
    excluded_assets: list[str] = []

    for raw_root in args.root or []:
        cleaned = clean_domain(raw_root)
        if cleaned:
            roots.add(cleaned)

    if args.roots_file:
        for raw_root in read_lines(Path(args.roots_file)):
            cleaned = clean_domain(raw_root)
            if cleaned:
                roots.add(cleaned)

    if args.scope_csv:
        scope_csv_path = Path(args.scope_csv)
        scope_data = parse_scope_csv(scope_csv_path)
        roots.update(scope_data.roots)
        mobile_assets.extend(scope_data.mobile_assets)
        excluded_assets.extend(scope_data.excluded_assets)

        destination = paths.scope_dir / "scope.csv"
        if scope_csv_path.resolve() != destination.resolve():
            destination.write_text(
                scope_csv_path.read_text(encoding="utf-8", errors="replace"),
                encoding="utf-8",
            )

    if not roots and args.profile != "report-only":
        raise ValueError("Provide --root, --roots-file, or --scope-csv.")

    return ScopeData(
        roots=sorted(roots),
        mobile_assets=sorted(set(mobile_assets)),
        excluded_assets=sorted(set(excluded_assets)),
    )


def write_scope_files(paths: RunPaths, scope_data: ScopeData) -> None:
    """Write parsed scope files."""
    write_lines(paths.clean_dir / "roots.txt", scope_data.roots)
    write_lines(paths.scope_dir / "in_scope_web_roots.txt", scope_data.roots)
    write_lines(paths.scope_dir / "mobile_assets.txt", scope_data.mobile_assets)
    write_lines(paths.scope_dir / "excluded_assets.txt", scope_data.excluded_assets)


def apply_policy_file(paths: RunPaths, policy_file: str | None) -> None:
    """Copy user-provided policy notes into the run scope folder."""
    if not policy_file:
        return

    source = Path(policy_file)
    if not source.exists():
        raise FileNotFoundError(f"Policy file not found: {source}")

    destination = paths.scope_dir / "policy_notes.md"
    content = source.read_text(encoding="utf-8", errors="replace")
    destination.write_text(content, encoding="utf-8")
