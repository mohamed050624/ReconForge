---
name: skill-generator
description: Generate a complete, production-ready asset bundle for a new Claude Code skill (SKILL.md, manifest.json, role.md, prompt templates, workflow files, examples, validation checklist) or agent (SKILL.md, manifest.json, role.md) inside any project's .claude/ directory. Automatically reads the target project's CLAUDE.md, docs/AI_CONSTITUTION.md, and docs/AI_FACTORY.md before generating anything, and — if present — loads graphify-out/graph.json (dependency/architecture graph) and graphify-out/manifest.json (project structure) to produce architecture-aware assets with real dependency findings. Every generated skill automatically includes Architecture, Documentation, Testing, and Dependency rule sections. Use this whenever the user wants to scaffold a new skill or agent, standardize how skills are documented across a project, or bootstrap AI-assisted tooling for a codebase. This skill produces the reusable SCAFFOLD only — it never invents project-specific behavior, and it never fabricates the contents of a missing context document; the caller supplies the skill's name, purpose, and domain details. Trigger this for phrases like "create a skill for...", "scaffold a Claude Code skill", "generate a skill.md and manifest", "create an agent", "set up AI tooling structure for this repo", or "I need a role/prompt/workflow file for this skill." Do not use this for editing an existing skill's business logic, and do not use this to write the actual domain-specific implementation of a skill — only its structural assets.
compatibility: Claude Code projects using a `.claude/` directory convention (skills/, workflows/, prompts/, roles/, manifests/, agents/). Python 3.9+ for the generator script. No external dependencies. Optionally reads CLAUDE.md, docs/AI_CONSTITUTION.md, docs/AI_FACTORY.md, and a graphify-style graphify-out/{graph.json,manifest.json} if the target project has them.
---

# Skill Generator (V2)

A reusable, project-agnostic generator that scaffolds the full set of assets a
Claude Code project expects for a new skill or agent. It is a **template
engine and directory-structure enforcer**, not a skill-content author. It
never decides *what* a project-specific skill should do — it only
guarantees that whatever skill or agent is created looks, documents, and
organizes itself the same way every time, and that it's grounded in
whatever real architectural context the target project actually has.

See `CHANGELOG.md` for the full V1 → V2 upgrade history.

## What this skill produces

For a single invocation with a skill name and description, this generator
creates the following self-contained assets:

### `--kind skill` (default) — full 7-asset bundle

| Asset | Purpose | Destination |
|---|---|---|
| `SKILL.md` | Entry point: frontmatter + instructions Claude reads when the skill triggers | `.claude/skills/<name>/SKILL.md` |
| `manifest.json` | Machine-readable metadata: version, compatibility, asset inventory, auto-loaded context | `.claude/manifests/<name>/manifest.json` |
| `role.md` | Persona/responsibility contract: what the skill is and is not allowed to do | `.claude/roles/<name>/role.md` |
| Prompt templates | Reusable prompt scaffolds for the skill's core tasks | `.claude/prompts/<name>/*.md` |
| Workflow files | Ordered, numbered step-by-step procedures | `.claude/workflows/<name>/*.md` |
| Examples | Worked input/output scenarios | `.claude/skills/<name>/examples/*.md` |
| Validation checklist | Structural + safety checklist for reviewing the generated skill | `.claude/skills/<name>/VALIDATION_CHECKLIST.md` |

### `--kind agent` (new in V2) — exactly 3 assets

| Asset | Purpose | Destination |
|---|---|---|
| `SKILL.md` | Entry point for the agent | `.claude/agents/<name>/SKILL.md` |
| `manifest.json` | Machine-readable metadata | `.claude/agents/<name>/manifest.json` |
| `role.md` | Authority scope, boundaries, escalation rules | `.claude/agents/<name>/role.md` |

This mirrors the `.claude/` convention (`skills/`, `workflows/`, `prompts/`,
`roles/`, `manifests/`, `agents/`) so generated assets slot directly into an
existing Claude Code project without reorganizing anything.

## Automatic context loading (new in V2)

Every run — regardless of `--kind` or `--sections` — automatically reads,
from the target project root, before generating any file:

1. `CLAUDE.md`
2. `docs/AI_CONSTITUTION.md`
3. `docs/AI_FACTORY.md`

And if present:

4. `graphify-out/graph.json` — parsed for node/edge counts, and (given
   `--touches`) used to detect directly-connected "affected modules."
5. `graphify-out/manifest.json` — used to report a tracked-file-count
   project-structure snapshot.

**None of this is optional and none of it is fabricated.** A missing file
is reported as `found`/`missing` in both the generated `SKILL.md` ("Project
Context" section) and `manifest.json` (`context_sources`,
`architecture_graph`, `project_structure_source` fields) — never silently
skipped and never treated as "no constraints exist."

## When to use this skill

- The user asks to scaffold, bootstrap, or generate a new skill for a project.
- The user wants consistent structure across many skills in one repo.
- The user is setting up `.claude/` tooling for the first time.
- The user wants to regenerate one asset type (e.g. "just give this skill a
  validation checklist") for an existing skill.

## When NOT to use this skill

- Writing the actual domain logic of a specific skill (e.g. "write me a skill
  that runs subfinder and parses the output") — that's project-specific
  authoring. This generator only lays the scaffolding; a human or a follow-up
  pass fills in the domain content inside the generated placeholders.
- Modifying an existing skill's behavior — use direct edits instead.
- One-off, non-reusable scripts that aren't meant to become a skill.

## Hard requirements this skill always enforces

1. **Consistent directory structure.** Every generated bundle uses the exact
   layout in the table above. Never invent alternate folder names.
2. **Self-containment.** Every generated file must be readable and useful on
   its own — no file may silently depend on undocumented external state.
3. **Documentation in every asset.** Every generated file includes a header
   explaining its purpose, how it's used, and how it relates to the other
   assets in the bundle.
4. **Claude Code compatibility.** `SKILL.md` always uses valid YAML
   frontmatter (`name`, `description`, optional `compatibility`) per the
   Claude Code skill format.
5. **Architecture preservation.** Never restructure, rename, or move any
   existing file or folder in the target project. Only add new files inside
   the standard `.claude/` subfolders.
6. **No silent overwrites.** If a destination file already exists, the
   generator skips it and reports the conflict instead of overwriting it,
   unless the caller explicitly passes `--force`.
7. **Engineering rules on every generated skill (new in V2).** Every
   generated `SKILL.md` automatically includes Architecture, Documentation,
   Testing, and Dependency rule sections — not optional, not left to the
   caller to remember to add.
8. **Automatic, non-fabricated context loading (new in V2).** Every run
   reads the project's constitution/rules documents and architecture graph
   if they exist, and reports honestly when they don't — see "Automatic
   context loading" above.

## How to use this skill

### Step 1 — Gather the required inputs

Before generating anything, resolve these four inputs (ask the user if any
are missing/ambiguous):

1. `name` — lowercase, hyphenated identifier (e.g. `subdomain-recon`).
2. `description` — one or two sentences: what it does + when to
   trigger it (this becomes the SKILL.md frontmatter description).
3. `target_root` — path to the project root that contains (or should
   contain) a `.claude/` directory. This is also where `CLAUDE.md`,
   `docs/AI_CONSTITUTION.md`, `docs/AI_FACTORY.md`, and `graphify-out/` are
   read from automatically. Default: current project root.
4. `kind` — `skill` (default, full 7-asset bundle) or `agent` (new in V2:
   SKILL.md + manifest.json + role.md only).
5. `sections` — which asset types to generate. Default: **all** valid
   sections for the chosen `kind`. The user may ask for a subset (e.g.
   "just regenerate the manifest").
6. `touches` (optional, new in V2) — file paths or symbol names the new
   skill/agent will interact with, used to compute affected modules from
   `graphify-out/graph.json` if it exists.

Do not fabricate domain-specific behavior for `description` — if the user
hasn't told you what the skill actually does, ask. This generator's job is
structure, not invention. Likewise, never fabricate what a missing
`docs/AI_CONSTITUTION.md` or `docs/AI_FACTORY.md` would have said — the
generator reports the gap instead.

### Step 2 — Run the generator script

```bash
python3 scripts/generate_asset_bundle.py \
  --name "<name>" \
  --description "<description>" \
  --target "<target_root>" \
  --kind skill \
  --sections all
```

For an agent bundle instead:

```bash
python3 scripts/generate_asset_bundle.py \
  --name "<name>" \
  --description "<description>" \
  --target "<target_root>" \
  --kind agent
```

To compute affected modules from the architecture graph:

```bash
python3 scripts/generate_asset_bundle.py \
  --name "<name>" --description "<description>" --target "<target_root>" \
  --touches "path/to/file.py,other/module.py"
```

Useful flags:
- `--kind skill|agent` — which bundle shape to generate (default `skill`)
- `--sections ...` — comma-separated subset instead of `all` (valid values
  depend on `--kind`; see the tables above)
- `--touches file1,file2,...` — seed files/symbols for dependency-impact
  detection via `graphify-out/graph.json`, if present
- `--force` — explicitly allow overwriting existing files (off by default)
- `--dry-run` — print what would be created without writing anything

The script never overwrites existing files unless `--force` is passed, and it
prints a clear `CREATED` / `SKIPPED (exists)` report line per file so nothing
happens silently.

### Step 3 — Review the output against the checklist

Open the generated `VALIDATION_CHECKLIST.md` and walk through it before
treating the bundle as done. See `references/validation_criteria.md` for the
full rationale behind each check.

### Step 4 — Fill in domain-specific content

The generated files contain clearly marked placeholders like
`<!-- TODO: describe the specific tool invocation sequence here -->`. This
generator's job ends once the scaffold exists; filling those placeholders
with real project-specific behavior is a separate, explicit next step — do
not do it automatically as part of scaffolding unless the user asks for both
in the same request.

## Reference files

- `templates/` — the raw templates the script fills in (skill.md, manifest.json,
  role.md, prompt, workflow, example, checklist, and — new in V2 —
  engineering_rules_block, the fixed Architecture/Documentation/Testing/
  Dependency rules injected into every generated skill). Read these if you
  need to understand or hand-edit the exact output format.
- `references/directory_structure.md` — full explanation of the `.claude/`
  layout convention this generator assumes.
- `references/validation_criteria.md` — the reasoning behind each validation
  checklist item, for when you need to explain *why* a check exists.
- `scripts/generate_asset_bundle.py` — the generator itself.
- `CHANGELOG.md` — every difference between V1 and V2, with rationale.
