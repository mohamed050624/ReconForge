# ReconForge AI Factory

## Purpose

The AI Factory is the central system responsible for generating, validating, maintaining and evolving every AI asset used by ReconForge.

The AI Factory never modifies production code directly.

Its responsibility is generating high-quality AI development assets.

---

## Supported Assets

- Skills
- Roles
- Manifest Files
- Prompt Templates
- Workflow Templates
- Documentation
- Validation Checklists

---

## Core Principles

- Modular
- Versioned
- Self-documented
- Reusable
- Project-aware
- Graph-aware

---

## Inputs

- graphify-out/graph.json
- graphify-out/manifest.json
- CLAUDE.md
- Repository Structure
- Existing Assets

---

## Outputs

.claude/

skills/

roles/

prompts/

workflows/

manifests/

docs/

tests/

---

## Internal Components

AI Factory consists of:

1. Skill Creator
2. Role Creator
3. Manifest Builder
4. Prompt Builder
5. Workflow Builder
6. Documentation Builder
7. Validation Engine

---

## Future Components

- Agent Generator
- MCP Generator
- Plugin Generator
- Test Generator
- UI Generator

---

## Rule

Every generated asset must be reproducible.

Nothing is handwritten if it can be generated.

Every asset is version controlled.

Every asset is documented.

Every asset follows project architecture.