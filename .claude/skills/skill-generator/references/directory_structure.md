# The `.claude/` Directory Convention

This generator assumes (and, if missing, creates) a project layout with five
top-level subfolders under `.claude/`:

```
<project_root>/
└── .claude/
    ├── skills/
    │   └── <skill_name>/
    │       ├── SKILL.md
    │       ├── VALIDATION_CHECKLIST.md
    │       └── examples/
    │           └── example_1.md
    ├── workflows/
    │   └── <skill_name>/
    │       └── workflow.md
    ├── prompts/
    │   └── <skill_name>/
    │       └── core_task.md
    ├── roles/
    │   └── <skill_name>/
    │       └── role.md
    └── manifests/
        └── <skill_name>/
            └── manifest.json
```

## Why this shape

- **One subfolder per asset type, one folder per skill inside it.** This
  keeps every skill's files grouped by *kind* (all manifests live together,
  all roles live together) while still letting you `ls .claude/skills/` and
  see every skill in the project at a glance.
- **`skills/<name>/` is the canonical entry point.** SKILL.md is what Claude
  Code actually reads to decide whether to trigger the skill; everything
  else is metadata, process, or supporting material that SKILL.md points to.
- **`examples/` and the validation checklist live inside the skill folder**,
  not in a separate top-level folder, because they're tightly coupled to
  one specific skill's behavior and are rarely reused across skills.
- **Prompts and workflows get their own top-level folders** because they're
  sometimes reused or referenced across multiple related skills (e.g. a
  shared "authorization check" workflow), even though this generator scopes
  each generated one to a single skill by default.

## Compatibility with existing projects

If a project already has some but not all of these five folders, the
generator only creates the ones that are missing — it never restructures
folders that already exist. If a project uses a different convention
entirely, do not force this structure onto it; ask the user how they'd like
to adapt the generator's output paths instead of overwriting their layout.
