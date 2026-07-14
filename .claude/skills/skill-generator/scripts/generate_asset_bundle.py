#!/usr/bin/env python3
"""
generate_asset_bundle.py
=========================

Part of the reusable `skill-generator` skill. (V2)

Purpose
-------
Renders the templates in ../templates/ into a full asset bundle inside a
target project's `.claude/` directory. Supports two kinds of bundles:

  --kind skill (default): SKILL.md, manifest.json, role.md, prompt
    templates, workflow files, examples, validation checklist — under
    `.claude/{skills,manifests,roles,prompts,workflows}/<name>/`.

  --kind agent: SKILL.md, manifest.json, role.md only — under
    `.claude/agents/<name>/`.

This script is self-contained: it does not require any external package,
only the Python 3 standard library. It can be run from anywhere as long as
it can find its own `templates/` directory (assumed to be a sibling of
`scripts/`, i.e. `<skill_root>/templates/`).

V2 additions (see CHANGELOG.md for full detail):
  1. Automatically reads CLAUDE.md, docs/AI_CONSTITUTION.md, and
     docs/AI_FACTORY.md from the target project root before generating
     anything, and reports which were found/missing. Never fabricates the
     contents of a missing file.
  2. Automatically loads graphify-out/graph.json if present, computes
     basic graph stats, and (given --touches) detects directly-connected
     "affected modules" for architecture-aware asset generation.
  3. Automatically loads graphify-out/manifest.json if present to report a
     project-structure snapshot (tracked file count).
  4. Every generated skill's SKILL.md now always includes an "Engineering
     Rules (auto-injected)" section covering architecture, documentation,
     testing, and dependency rules.
  5. Adds --kind agent, producing SKILL.md + manifest.json + role.md under
     `.claude/agents/<name>/`.

Hard guarantees enforced by this script (unchanged from V1 — do not remove
without updating VALIDATION_CHECKLIST.md and role.md accordingly):
  1. Never overwrites an existing destination file unless --force is passed.
  2. Never writes outside the standard `.claude/` subfolders.
  3. Never touches any file that isn't one it's specifically generating.
  4. Always prints a per-file CREATED / SKIPPED report — nothing silent.

Usage
-----
    # Skill bundle (default), same shape as V1 plus auto-loaded context:
    python3 generate_asset_bundle.py --name my-skill \
        --description "Does X when the user asks for Y." \
        --target /path/to/project \
        --sections all

    # With dependency-impact detection via the architecture graph:
    python3 generate_asset_bundle.py --name my-skill \
        --description "..." --target /path/to/project \
        --touches "reconforge_v1/context.py,reconforge_v1/models.py"

    # Agent bundle (new in V2): SKILL.md + manifest.json + role.md only.
    python3 generate_asset_bundle.py --name my-agent \
        --description "..." --target /path/to/project --kind agent

    python3 generate_asset_bundle.py --name my-skill \
        --description "..." --target . --sections manifest,role --force

    python3 generate_asset_bundle.py --name my-skill \
        --description "..." --target . --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

GENERATOR_VERSION = "2.0.0"

# --- V2: required context documents, read automatically before any asset
# is generated. Paths are relative to --target (the project root). ---
CONTEXT_DOC_PATHS = {
    "CLAUDE.md": "CLAUDE.md",
    "docs/AI_CONSTITUTION.md": "docs/AI_CONSTITUTION.md",
    "docs/AI_FACTORY.md": "docs/AI_FACTORY.md",
}

GRAPH_PATH = "graphify-out/graph.json"
GRAPH_MANIFEST_PATH = "graphify-out/manifest.json"

# Maps a --sections keyword to (template_file, destination_path_template)
# destination_path_template is relative to <target>/.
# SKILL_ASSET_MAP is used for --kind skill (the V1 behavior, unchanged).
SKILL_ASSET_MAP = {
    "skill": {
        "template": "skill_md.template",
        "dest": ".claude/skills/{name}/SKILL.md",
    },
    "manifest": {
        "template": "manifest_json.template",
        "dest": ".claude/manifests/{name}/manifest.json",
    },
    "role": {
        "template": "role_md.template",
        "dest": ".claude/roles/{name}/role.md",
    },
    "prompts": {
        "template": "prompt_template.md.template",
        "dest": ".claude/prompts/{name}/core_task.md",
    },
    "workflows": {
        "template": "workflow_md.template",
        "dest": ".claude/workflows/{name}/workflow.md",
    },
    "examples": {
        "template": "example_md.template",
        "dest": ".claude/skills/{name}/examples/example_1.md",
    },
    "checklist": {
        "template": "validation_checklist.md.template",
        "dest": ".claude/skills/{name}/VALIDATION_CHECKLIST.md",
    },
}

# AGENT_ASSET_MAP is new in V2 (--kind agent): every generated Agent must
# include exactly SKILL.md, manifest.json, and role.md, under
# .claude/agents/<name>/ rather than split across skills/manifests/roles.
AGENT_ASSET_MAP = {
    "skill": {
        "template": "skill_md.template",
        "dest": ".claude/agents/{name}/SKILL.md",
    },
    "manifest": {
        "template": "manifest_json.template",
        "dest": ".claude/agents/{name}/manifest.json",
    },
    "role": {
        "template": "role_md.template",
        "dest": ".claude/agents/{name}/role.md",
    },
}

ALL_SKILL_SECTIONS = list(SKILL_ASSET_MAP.keys())
ALL_AGENT_SECTIONS = list(AGENT_ASSET_MAP.keys())  # always exactly these three


def slug_to_title(name: str) -> str:
    """Turn 'subdomain-recon' into 'Subdomain Recon'."""
    return " ".join(word.capitalize() for word in re.split(r"[-_]+", name) if word)


def render(template_text: str, context: dict) -> str:
    """Minimal {{placeholder}} substitution — no external templating deps."""
    out = template_text
    for key, value in context.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def validate_name(name: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9\-]*[a-z0-9]|[a-z0-9]", name):
        raise ValueError(
            f"Invalid skill name '{name}'. Use lowercase letters, digits, "
            "and hyphens only (e.g. 'subdomain-recon')."
        )


def load_templates(script_dir: Path) -> Path:
    templates_dir = script_dir.parent / "templates"
    if not templates_dir.is_dir():
        raise FileNotFoundError(
            f"Could not find templates directory at {templates_dir}. "
            "This script expects to live at <skill_root>/scripts/ with a "
            "sibling <skill_root>/templates/ directory."
        )
    return templates_dir


def _strip_leading_html_comment(text: str) -> str:
    """Fragments like engineering_rules_block.md.template carry their own
    <!-- ... --> documentation header (useful when viewing the template
    file directly), but that header shouldn't be duplicated inside the
    already-documented file it gets embedded into. Strip one leading
    HTML comment block, if present, and return the rest, stripped."""
    stripped = text.lstrip()
    if stripped.startswith("<!--"):
        end = stripped.find("-->")
        if end != -1:
            return stripped[end + 3 :].lstrip("\n")
    return text


def _read_text_safe(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, IsADirectoryError):
        return None


def load_context_docs(target: Path) -> dict:
    """V2, requirement 1: read CLAUDE.md, docs/AI_CONSTITUTION.md, and
    docs/AI_FACTORY.md from the target project root before generating
    anything. Never fabricates content for a file that isn't there —
    just reports found vs. missing."""
    found, missing = [], []
    for label, rel_path in CONTEXT_DOC_PATHS.items():
        text = _read_text_safe(target / rel_path)
        (found if text is not None else missing).append(label)
    return {"found": found, "missing": missing}


def load_architecture_graph(target: Path) -> dict | None:
    """V2, requirement 2: load graphify-out/graph.json if present and
    build a minimal id -> node / adjacency index for dependency analysis.
    Returns None if the file doesn't exist (not an error — just absent)."""
    graph_path = target / GRAPH_PATH
    text = _read_text_safe(graph_path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return {"error": f"{GRAPH_PATH} is invalid JSON: {e}"}

    nodes = data.get("nodes", [])
    edges = data.get("links", data.get("edges", []))

    by_id = {n["id"]: n for n in nodes if "id" in n}
    adjacency: dict[str, set[str]] = {}
    for e in edges:
        a, b = e.get("source"), e.get("target")
        if a is None or b is None:
            continue
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "by_id": by_id,
        "adjacency": adjacency,
    }


def load_graph_manifest(target: Path) -> dict | None:
    """V2, requirement 3: load graphify-out/manifest.json if present to
    understand project structure (the set of tracked files)."""
    manifest_path = target / GRAPH_MANIFEST_PATH
    text = _read_text_safe(manifest_path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return {"error": f"{GRAPH_MANIFEST_PATH} is invalid JSON: {e}"}
    return {"file_count": len(data)}


def compute_affected_modules(graph: dict | None, touches: list[str]) -> list[str]:
    """V2, requirement 2: given a list of file/symbol substrings the new
    skill or agent will touch, find directly-connected (1-hop) modules in
    the architecture graph. Returns [] if there's no graph or no touches
    supplied — this is a deliberate no-op, not a failure."""
    if not graph or "error" in graph or not touches:
        return []

    seed_ids = set()
    for t in touches:
        for node_id, node in graph["by_id"].items():
            haystack = f"{node.get('source_file', '')} {node.get('label', '')} {node_id}"
            if t and t in haystack:
                seed_ids.add(node_id)

    affected_files = set()
    for sid in seed_ids:
        for neighbor_id in graph["adjacency"].get(sid, ()):
            neighbor = graph["by_id"].get(neighbor_id)
            if neighbor and neighbor.get("source_file"):
                affected_files.add(neighbor["source_file"])

    return sorted(affected_files)


def build_context_report_block(context_docs: dict) -> str:
    lines = []
    for f in context_docs["found"]:
        lines.append(f"- ✅ Found: `{f}`")
    for f in context_docs["missing"]:
        lines.append(
            f"- ⚠️ Missing: `{f}` — flagged as a gap, not treated as "
            "\"no constraints exist.\""
        )
    return "\n".join(lines) if lines else "- (no context files checked)"


def build_graph_report_block(graph: dict | None, touches: list[str], affected: list[str]) -> str:
    if graph is None:
        return (
            f"- ⚠️ `{GRAPH_PATH}` not found — dependency analysis for this "
            "skill/agent falls back to direct source reading at run time."
        )
    if "error" in graph:
        return f"- ⚠️ `{GRAPH_PATH}` found but could not be parsed: {graph['error']}"

    lines = [f"- ✅ Loaded `{GRAPH_PATH}`: {graph['node_count']} nodes, {graph['edge_count']} edges."]
    if touches:
        lines.append(f"- `--touches` supplied: {', '.join(touches)}")
        if affected:
            lines.append("- Affected modules detected (1-hop dependents/dependencies):")
            lines.extend(f"  - `{f}`" for f in affected)
        else:
            lines.append(
                "- No connected modules matched the given `--touches` "
                "(check the values match a node's source_file or label)."
            )
    else:
        lines.append(
            "- No `--touches` supplied at generation time; pass "
            "`--touches path/to/file.py,other/module.py` to compute "
            "impacted modules for this skill's/agent's domain."
        )
    return "\n".join(lines)


def build_project_structure_block(graph_manifest: dict | None) -> str:
    if graph_manifest is None:
        return (
            f"- ⚠️ `{GRAPH_MANIFEST_PATH}` not found — no automated "
            "project-structure snapshot available."
        )
    if "error" in graph_manifest:
        return f"- ⚠️ `{GRAPH_MANIFEST_PATH}` found but could not be parsed: {graph_manifest['error']}"
    return f"- ✅ Loaded `{GRAPH_MANIFEST_PATH}`: {graph_manifest['file_count']} tracked files."


def generate(
    name: str,
    description: str,
    target: Path,
    kind: str,
    sections: list[str],
    touches: list[str],
    force: bool,
    dry_run: bool,
) -> int:
    script_dir = Path(__file__).resolve().parent
    templates_dir = load_templates(script_dir)

    asset_map = AGENT_ASSET_MAP if kind == "agent" else SKILL_ASSET_MAP

    # --- V2, requirements 1-3: automatic context loading, always run,
    # before any asset is generated, regardless of --sections. ---
    context_docs = load_context_docs(target)
    graph = load_architecture_graph(target)
    graph_manifest = load_graph_manifest(target)
    affected_modules = compute_affected_modules(graph, touches)

    engineering_rules_block = _strip_leading_html_comment(
        (templates_dir / "engineering_rules_block.md.template").read_text(encoding="utf-8")
    )

    # --- Kind-aware cross-references. Skill and agent bundles have
    # different destination layouts (agents don't get workflows/, prompts/,
    # examples/, or a validation checklist), so SKILL.md's internal
    # references must differ by kind rather than being hardcoded to the
    # skill layout. ---
    if kind == "agent":
        self_skill_path = f".claude/agents/{name}/SKILL.md"
        role_md_path = f".claude/agents/{name}/role.md"
        manifest_path = f".claude/agents/{name}/manifest.json"
        workflow_intro_block = (
            "This agent has no separate `workflow.md` file — the numbered "
            "steps below are the authoritative procedure."
        )
        validation_block = (
            "This agent bundle has no separate validation checklist file. "
            "Before treating any task from this agent as complete, verify: "
            "the implementation plan was shared before coding, no public API "
            "broke without explicit sign-off, no unrelated module changed, "
            "documentation was updated to match any architectural change, "
            "and tests exist for new/changed behavior."
        )
        related_assets_block = (
            f"- Role contract: `{role_md_path}`\n"
            f"- Manifest: `{manifest_path}`\n\n"
            "This is an agent bundle (`--kind agent`): it intentionally has "
            "no `prompts/`, `workflows/`, `examples/`, or validation-checklist "
            "files. See `role.md` for the full behavior/boundary contract."
        )
        role_relationship_block = (
            f"- `{self_skill_path}` — trigger conditions and workflow summary\n"
            f"- `{manifest_path}` — version and compatibility metadata"
        )
        allowed_write_paths = [f".claude/agents/{name}/"]
        assets_dict = {
            "skill_md": self_skill_path,
            "role_md": role_md_path,
            "manifest_json": manifest_path,
        }
    else:
        self_skill_path = f".claude/skills/{name}/SKILL.md"
        role_md_path = f".claude/roles/{name}/role.md"
        manifest_path = f".claude/manifests/{name}/manifest.json"
        workflow_intro_block = (
            f"This skill follows the procedure defined in\n"
            f"`.claude/workflows/{name}/workflow.md`. Read that file for the\n"
            "authoritative step-by-step sequence before acting.\n\n"
            "High-level summary:"
        )
        validation_block = (
            "Before considering a task from this skill complete, check it "
            f"against `.claude/skills/{name}/VALIDATION_CHECKLIST.md`."
        )
        related_assets_block = (
            f"- Role contract: `{role_md_path}`\n"
            f"- Manifest: `{manifest_path}`\n"
            f"- Prompt templates: `.claude/prompts/{name}/`\n"
            f"- Workflow: `.claude/workflows/{name}/workflow.md`\n"
            f"- Examples: `.claude/skills/{name}/examples/`\n"
            f"- Validation checklist: `.claude/skills/{name}/VALIDATION_CHECKLIST.md`"
        )
        role_relationship_block = (
            f"- `{self_skill_path}` — trigger conditions and workflow summary\n"
            f"- `.claude/workflows/{name}/workflow.md` — the exact procedure this role follows\n"
            f"- `{manifest_path}` — version and compatibility metadata"
        )
        allowed_write_paths = [
            f".claude/skills/{name}/",
            f".claude/workflows/{name}/",
            f".claude/prompts/{name}/",
            f".claude/roles/{name}/",
            f".claude/manifests/{name}/",
        ]
        assets_dict = {
            "skill_md": self_skill_path,
            "role_md": role_md_path,
            "workflow": f".claude/workflows/{name}/workflow.md",
            "prompts": f".claude/prompts/{name}/",
            "examples": f".claude/skills/{name}/examples/",
            "validation_checklist": f".claude/skills/{name}/VALIDATION_CHECKLIST.md",
        }

    context = {
        "skill_name": name,
        "skill_title": slug_to_title(name),
        "skill_description": description,
        "generated_date": datetime.date.today().isoformat(),
        "generator_version": GENERATOR_VERSION,
        "kind": kind,
        "self_skill_path": self_skill_path,
        "role_md_path": role_md_path,
        "role_relationship_block": role_relationship_block,
        "allowed_write_paths_json": json.dumps(allowed_write_paths, indent=2),
        "assets_json": json.dumps(assets_dict, indent=2),
        "workflow_intro_block": workflow_intro_block,
        "validation_block": validation_block,
        "related_assets_block": related_assets_block,
        # Markdown blocks for SKILL.md / role.md:
        "engineering_rules_block": engineering_rules_block,
        "context_report_block": build_context_report_block(context_docs),
        "graph_report_block": build_graph_report_block(graph, touches, affected_modules),
        "project_structure_block": build_project_structure_block(graph_manifest),
        # JSON-safe scalars/arrays for manifest.json:
        "context_found_json": json.dumps(context_docs["found"]),
        "context_missing_json": json.dumps(context_docs["missing"]),
        "graph_used_json": "true" if graph and "error" not in graph else "false",
        "graph_node_count_json": str(graph["node_count"]) if graph and "node_count" in graph else "null",
        "graph_edge_count_json": str(graph["edge_count"]) if graph and "edge_count" in graph else "null",
        "touches_json": json.dumps(touches),
        "affected_modules_json": json.dumps(affected_modules),
        "graph_manifest_used_json": "true" if graph_manifest and "error" not in graph_manifest else "false",
        "graph_manifest_file_count_json": (
            str(graph_manifest["file_count"]) if graph_manifest and "file_count" in graph_manifest else "null"
        ),
    }

    created, skipped, errors = [], [], []

    for section in sections:
        if section not in asset_map:
            errors.append(
                f"Section '{section}' is not valid for --kind {kind} "
                f"(valid: {', '.join(asset_map.keys())}) — skipping."
            )
            continue

        spec = asset_map[section]
        template_path = templates_dir / spec["template"]
        dest_rel = spec["dest"].format(name=name)
        dest_path = target / dest_rel

        # Safety: refuse to write anywhere outside target/.claude/
        try:
            dest_path.resolve().relative_to((target / ".claude").resolve())
        except ValueError:
            errors.append(f"Refusing to write outside .claude/: {dest_path}")
            continue

        if not template_path.is_file():
            errors.append(f"Missing template for '{section}': {template_path}")
            continue

        if dest_path.exists() and not force:
            skipped.append(str(dest_rel))
            continue

        template_text = template_path.read_text(encoding="utf-8")
        rendered = render(template_text, context)

        if dry_run:
            created.append(f"{dest_rel} (dry-run, not written)")
            continue

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(rendered, encoding="utf-8")
        created.append(str(dest_rel))

    # Validate manifest.json is well-formed JSON after rendering, if generated
    if "manifest" in sections and not dry_run:
        manifest_check_path = target / asset_map["manifest"]["dest"].format(name=name)
        if manifest_check_path.exists():
            try:
                json.loads(manifest_check_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"Generated manifest.json is invalid JSON: {e}")

    print(f"\nSkill Generator v{GENERATOR_VERSION} — {kind} bundle for '{name}'")
    print(f"Target project: {target}")
    print(
        f"Context docs found: {context_docs['found'] or '(none)'} | "
        f"missing: {context_docs['missing'] or '(none)'}"
    )
    print(
        f"Architecture graph: {'loaded' if graph and 'error' not in graph else 'not available'}"
        + (f" ({graph['node_count']} nodes, {graph['edge_count']} edges)" if graph and 'error' not in graph else "")
    )
    print(
        f"Project structure manifest: "
        f"{'loaded (' + str(graph_manifest['file_count']) + ' files)' if graph_manifest and 'error' not in graph_manifest else 'not available'}\n"
    )

    for path in created:
        print(f"  CREATED         {path}")
    for path in skipped:
        print(f"  SKIPPED (exists) {path}  (use --force to overwrite)")
    for err in errors:
        print(f"  ERROR           {err}")

    print(
        f"\n{len(created)} created, {len(skipped)} skipped, {len(errors)} errors."
    )

    if errors:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Claude Code asset bundle. --kind skill "
        "(default) produces SKILL.md, manifest.json, role.md, prompt "
        "templates, workflow files, examples, and a validation checklist. "
        "--kind agent produces exactly SKILL.md, manifest.json, and "
        "role.md under .claude/agents/<name>/."
    )
    parser.add_argument("--name", required=True, help="Skill/agent name (lowercase-hyphenated).")
    parser.add_argument("--description", required=True, help="One/two sentence description.")
    parser.add_argument(
        "--target",
        default=".",
        help="Project root containing (or to contain) a .claude/ directory. "
        "Also where CLAUDE.md / docs/AI_CONSTITUTION.md / docs/AI_FACTORY.md "
        "/ graphify-out/ are read from automatically. Default: current directory.",
    )
    parser.add_argument(
        "--kind",
        choices=["skill", "agent"],
        default="skill",
        help="Bundle kind. 'skill' (default): full 7-asset bundle. "
        "'agent': SKILL.md + manifest.json + role.md only, under .claude/agents/<name>/.",
    )
    parser.add_argument(
        "--sections",
        default="all",
        help="Comma-separated subset of the sections valid for the chosen --kind. "
        f"Skill sections: {','.join(ALL_SKILL_SECTIONS)}. "
        f"Agent sections: {','.join(ALL_AGENT_SECTIONS)}. Default: all.",
    )
    parser.add_argument(
        "--touches",
        default="",
        help="Comma-separated list of file paths / symbol substrings this "
        "skill/agent will touch, used to detect affected modules via "
        "graphify-out/graph.json if present. Optional.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting existing destination files. Off by default.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without writing any files.",
    )

    args = parser.parse_args()

    try:
        validate_name(args.name)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    all_sections = ALL_AGENT_SECTIONS if args.kind == "agent" else ALL_SKILL_SECTIONS
    sections = (
        all_sections
        if args.sections.strip().lower() == "all"
        else [s.strip() for s in args.sections.split(",") if s.strip()]
    )

    touches = [t.strip() for t in args.touches.split(",") if t.strip()]

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"ERROR: target path does not exist: {target}", file=sys.stderr)
        return 1

    return generate(
        name=args.name,
        description=args.description,
        target=target,
        kind=args.kind,
        sections=sections,
        touches=touches,
        force=args.force,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
