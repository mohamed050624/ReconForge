# Validation Criteria — Rationale

Background for each section of the generated `VALIDATION_CHECKLIST.md`, for
use when explaining *why* a check matters (e.g. to a user who wants to skip
one).

## Structure

Consistent structure is the entire value proposition of this generator. If
one skill's assets live in different places than another's, tooling and
humans both lose the ability to predict where to look. This check exists to
catch drift immediately, not after five more skills have copied the mistake.

## Self-containment

A file that only makes sense in combination with tribal knowledge is a
liability the moment its author leaves the room. Every generated asset should
survive being opened cold, six months later, by someone who has never seen
the project.

## Documentation

Skills are read by both humans and Claude itself. Undocumented assets waste
the reader's time re-deriving intent that the author already knew when
writing it.

## Claude Code compatibility

`SKILL.md` frontmatter is not just documentation — it's the mechanism Claude
Code uses to decide whether to consult the skill at all. Invalid YAML or a
vague description silently disables the skill (it just never triggers),
which is a hard failure mode to notice.

## Architecture preservation

The generator is a guest in someone else's project. Moving, renaming, or
overwriting files it doesn't own is exactly the kind of "helpful" behavior
that breaks trust and unrelated functionality. This check exists so that
"the generator ran" is never a sentence followed by "...and now something
else is broken."

## Overwrite safety

Silent overwrites are the single most damaging failure mode for a
scaffolding tool: they destroy work with no warning and no recovery path.
Every run must report exactly what it touched, and it must never touch an
existing file without the caller saying so explicitly.

## Domain readiness

The first six sections validate the *scaffold*. This last section is a
reminder that a scaffold is not a finished skill — `status: "scaffolded"` in
manifest.json is a deliberate, visible marker that domain content still
needs to be written and tested before anyone should trust the skill's
described behavior.
