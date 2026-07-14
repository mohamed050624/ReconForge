# Changelog — Skill Generator

## V2.0.0 (2026-07-14)

Upgrade only — no redesign. Every V1 capability, file, and guarantee is
still present and behaves the same way unless explicitly noted below. All
changes are additive except the `--sections` default, which is now
kind-aware (see item 5).

### 1. Automatic context loading before any asset is generated

**What changed:** Every run of `generate_asset_bundle.py` now reads, from
the target project root, before writing anything:

- `CLAUDE.md`
- `docs/AI_CONSTITUTION.md`
- `docs/AI_FACTORY.md`

**Why:** Generated skills were previously blind to whatever engineering
rules a project already had. A skill/agent that doesn't know the project's
constitution can't meaningfully preserve it.

**Behavior on missing files:** A missing file is recorded as `missing`, not
silently skipped and never fabricated. Findings surface in two places:
- Generated `SKILL.md` → "Project Context" section, human-readable.
- Generated `manifest.json` → `context_sources.found` / `.missing`,
  machine-readable.

**New functions:** `load_context_docs()`, `build_context_report_block()`.

---

### 2. Architecture-graph-aware generation via `graphify-out/graph.json`

**What changed:** If `graphify-out/graph.json` exists in the target
project, the generator now loads it, reports node/edge counts, and — given
the new `--touches` flag — walks the graph's adjacency to detect
directly-connected ("affected") modules for the skill/agent being
generated.

**Why:** A newly generated skill that will touch specific files/modules
should ship with a real, computed list of what else that touches, not a
`<!-- TODO -->` placeholder, whenever that information is available.

**New CLI flag:** `--touches file1,file2,...` (optional; comma-separated
file paths or symbol/label substrings).

**Behavior with no graph or no `--touches`:** Reported explicitly as
"not available" / "no `--touches` supplied" — never silently defaulted to
an empty finding presented as a clean bill of health.

**New functions:** `load_architecture_graph()`, `compute_affected_modules()`,
`build_graph_report_block()`.

---

### 3. Project-structure awareness via `graphify-out/manifest.json`

**What changed:** If `graphify-out/manifest.json` exists, the generator
loads it and reports a tracked-file-count snapshot of the project's
structure, in both the generated `SKILL.md` and `manifest.json`.

**Why:** Requirement 3 of the V2 spec — use the graphify manifest to
understand project structure when it's available, without requiring it.

**New functions:** `load_graph_manifest()`, `build_project_structure_block()`.

---

### 4. Every generated Skill now automatically includes four rule categories

**What changed:** Every generated `SKILL.md` now has a mandatory
"Engineering Rules (auto-injected)" section covering:

- Architecture rules
- Documentation rules
- Testing rules
- Dependency rules

**Why:** These four categories were previously left entirely to whoever
filled in the `<!-- TODO -->` placeholders — meaning a generated skill
could ship with zero architectural discipline baked in. V2 makes them a
structural guarantee, not a suggestion.

**New template:** `templates/engineering_rules_block.md.template` — fixed,
generic boilerplate (not per-project rendered) inserted verbatim via the
`{{engineering_rules_block}}` placeholder. `manifest.json` also gained an
`engineering_rules_injected` object confirming all four are present.

**Templates touched:** `skill_md.template` (new sections), `role_md.template`
(new "Context-loading responsibility" section), `manifest_json.template`
(new `context_sources`, `architecture_graph`, `project_structure_source`,
`engineering_rules_injected` fields).

---

### 5. New `--kind agent` bundle shape

**What changed:** The generator now supports `--kind skill` (default,
unchanged 7-asset bundle) and `--kind agent` (new: exactly `SKILL.md`,
`manifest.json`, `role.md`, written to `.claude/agents/<name>/` instead of
being split across `.claude/{skills,manifests,roles}/<name>/`).

**Why:** Requirement 5 of the V2 spec — every generated Agent must include
SKILL.md, manifest.json, and role.md. Agents are a distinct asset shape
from skills (no prompts/workflows/examples/checklist), so they get their
own destination map (`AGENT_ASSET_MAP`) rather than overloading the
existing one.

**Behavior change (narrow):** `--sections all` now resolves against
whichever section set is valid for the chosen `--kind`
(`ALL_SKILL_SECTIONS` vs. `ALL_AGENT_SECTIONS`) instead of a single global
list. Explicit `--sections` values invalid for the chosen `--kind` are
reported as errors per-section, exactly like an unknown section name was
handled in V1 — this is a generalization of existing behavior, not new
behavior.

**New template**: none — `--kind agent` reuses `skill_md.template`,
`manifest_json.template`, and `role_md.template` verbatim, just at
different destination paths. This keeps the two kinds consistent by
construction rather than by convention.

---

### 6. No-overwrite guarantee — unchanged, re-verified

**What changed:** Nothing. `--force` is still required to overwrite an
existing destination file; every run still prints a per-file
`CREATED` / `SKIPPED (exists)` / `ERROR` report. Re-verified against both
`--kind skill` and the new `--kind agent` path.

---

### 7. This CHANGELOG

New in V2: this file. Every future upgrade should append a new dated
section here rather than editing history.

---

## Non-changes (explicitly preserved from V1)

- Directory structure for `--kind skill` bundles: unchanged.
- No-overwrite-without-`--force` guarantee: unchanged.
- Refusal to write outside `target/.claude/`: unchanged.
- `--dry-run` behavior: unchanged.
- Self-contained, documented, Claude-Code-compatible output: unchanged
  requirement, now with more to be documented (see item 4).
- Stdlib-only, no external dependencies: unchanged.

## Upgrade notes for existing V1-generated bundles

Bundles generated by V1 are still valid and are not touched by upgrading
the generator itself — this upgrade changes what *new* generations look
like, not files already on disk. To bring an existing V1-generated skill
up to V2's standard (engineering rules section, project context section),
regenerate its `skill` section with `--force` after reviewing what you'll
overwrite, or hand-add the new sections from
`templates/skill_md.template`.
