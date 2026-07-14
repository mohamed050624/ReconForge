# Skill Generator (V2)

A reusable Claude Code skill that scaffolds the full asset bundle a new
skill or agent needs — grounded in the target project's real architecture
and constitution wherever those exist, and never inventing project-specific
behavior on its own. See `CHANGELOG.md` for the full V1 → V2 upgrade
history.

## What's in this package

```
skill-generator/
├── SKILL.md                     # entry point — read this first
├── README.md                    # this file
├── CHANGELOG.md                 # V1 -> V2 upgrade history
├── scripts/
│   └── generate_asset_bundle.py # the generator (stdlib-only, Python 3.9+)
├── templates/                   # the 8 templates the script renders
│   ├── skill_md.template
│   ├── manifest_json.template
│   ├── role_md.template
│   ├── prompt_template.md.template
│   ├── workflow_md.template
│   ├── example_md.template
│   ├── validation_checklist.md.template
│   └── engineering_rules_block.md.template   # new in V2
└── references/
    ├── directory_structure.md   # the .claude/ layout this generator assumes
    └── validation_criteria.md   # rationale behind each checklist item
```

## Install into a project

Copy this whole `skill-generator/` folder into the target project's
`.claude/skills/` directory (i.e. it becomes a skill Claude Code can
discover), for example:

```
<project>/.claude/skills/skill-generator/
```

## Quick start — skill bundle (default)

```bash
python3 scripts/generate_asset_bundle.py \
  --name my-new-skill \
  --description "What it does and when to trigger it." \
  --target /path/to/project \
  --sections all
```

Before writing anything, the generator automatically reads (from
`--target`) `CLAUDE.md`, `docs/AI_CONSTITUTION.md`, `docs/AI_FACTORY.md`,
and — if present — `graphify-out/graph.json` and
`graphify-out/manifest.json`. Missing files are reported, never invented.

This creates, inside `<project>/.claude/`:

- `skills/my-new-skill/SKILL.md` — now includes Architecture/Documentation
  /Testing/Dependency rules and a "Project Context" section automatically
- `manifests/my-new-skill/manifest.json` — now includes machine-readable
  context/graph findings
- `roles/my-new-skill/role.md`
- `prompts/my-new-skill/core_task.md`
- `workflows/my-new-skill/workflow.md`
- `skills/my-new-skill/examples/example_1.md`
- `skills/my-new-skill/VALIDATION_CHECKLIST.md`

## Quick start — agent bundle (new in V2)

```bash
python3 scripts/generate_asset_bundle.py \
  --name my-new-agent \
  --description "What it does and when to trigger it." \
  --target /path/to/project \
  --kind agent
```

This creates exactly:

- `agents/my-new-agent/SKILL.md`
- `agents/my-new-agent/manifest.json`
- `agents/my-new-agent/role.md`

## Dependency-impact detection (new in V2)

If the target project has `graphify-out/graph.json`, pass `--touches` to
compute which modules are directly connected to the ones this skill/agent
will interact with:

```bash
python3 scripts/generate_asset_bundle.py \
  --name my-new-skill --description "..." --target /path/to/project \
  --touches "reconforge_v1/context.py,reconforge_v1/models.py"
```

Run with `--dry-run` first to preview, and add `--force` only if you
intentionally want to overwrite an existing bundle — by default nothing is
ever overwritten.

## What this does NOT do

It does not write the domain-specific logic of your skill or agent. Every
generated file contains `<!-- TODO -->` placeholders for you (or a
follow-up request) to fill in with the actual behavior. It does not
fabricate the contents of a missing `docs/AI_CONSTITUTION.md` or
`docs/AI_FACTORY.md` — it reports the gap instead. This tool's only job is
guaranteeing that every skill or agent in a project has the same
structure, documentation, and safety checklist — every time, grounded in
whatever real project context actually exists.
