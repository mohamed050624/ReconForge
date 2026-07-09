"""AI package archive builder for ReconForge V1."""

from __future__ import annotations

import shutil
import tarfile
from pathlib import Path

from reconforge_v1.models import RunPaths


def copy_if_exists(source: Path, destination: Path) -> None:
    """Copy a file if it exists."""
    if not source.exists():
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def write_ai_package(paths: RunPaths) -> Path:
    """
    Build a single AI package archive.

    This archive is the only file the user should need to upload to an AI
    assistant for analysis.
    """
    package_dir = paths.root / "ai_package"
    archive_path = paths.root / f"{paths.program}_ai_package.tar.gz"

    if package_dir.exists():
        shutil.rmtree(package_dir)

    package_dir.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        paths.reports_dir / "ai_handoff.md",
        paths.reports_dir / "program_ai_context.json",
        paths.reports_dir / "ai_prompt.md",
        paths.reports_dir / "program_report.md",
        paths.scope_dir / "policy_notes.md",
        paths.scope_dir / "in_scope_web_roots.txt",
        paths.scope_dir / "excluded_assets.txt",
        paths.scope_dir / "mobile_assets.txt",
        paths.raw_dir / "tool_status.json",
        paths.clean_dir / "roots.txt",
        paths.clean_dir / "subdomains_all.txt",
        paths.clean_dir / "subdomains_resolved.txt",
        paths.clean_dir / "live_hosts.txt",
        paths.clean_dir / "urls_unique.txt",
        paths.clean_dir / "api_base_hosts.txt",
        paths.clean_dir / "api_endpoints.txt",
        paths.clean_dir / "api_params.txt",
        paths.clean_dir / "graphql_candidates.txt",
        paths.clean_dir / "swagger_openapi_candidates.txt",
        paths.clean_dir / "auth_endpoints.txt",
        paths.clean_dir / "upload_endpoints.txt",
        paths.clean_dir / "interesting_urls.txt",
        paths.clean_dir / "high_signal_assets.txt",
        paths.clean_dir / "params.txt",
        paths.clean_dir / "js_files.txt",
        paths.clean_dir / "technologies.txt",
    ]

    for source in files_to_copy:
        try:
            relative = source.relative_to(paths.root)
        except ValueError:
            relative = Path(source.name)

        copy_if_exists(source, package_dir / relative)

    readme = f"""# ReconForge AI Package: {paths.program}

Upload this archive to the AI assistant.

Main files:
- `03_reports/ai_handoff.md`
- `03_reports/program_ai_context.json`
- `03_reports/ai_prompt.md`
- `00_scope/policy_notes.md`

How the AI should use this:
1. Read `ai_handoff.md` first.
2. Use `program_ai_context.json` for structured analysis.
3. Use files in `02_clean/` for detailed evidence.
4. Respect `policy_notes.md` and scope restrictions.
5. If more data is needed, ask the user for one safe command at a time.

Rules for follow-up commands:
- Only ask for non-destructive inspection commands.
- Do not ask for DoS, brute force, credential attacks, exploitation, or fuzzing.
- Prefer commands like:
  - `head -100 <file>`
  - `grep -i "keyword" <file>`
  - `wc -l <file>`
  - `cat <small-file>`
  - `python3 reconforge_one.py --program {paths.program} --profile report-only --verbose`
"""

    (package_dir / "SEND_THIS_TO_AI.md").write_text(readme, encoding="utf-8")

    if archive_path.exists():
        archive_path.unlink()

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(package_dir, arcname=f"{paths.program}_ai_package")

    return archive_path
