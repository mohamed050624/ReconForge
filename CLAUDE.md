# ReconForge Development Rules

## Mission

ReconForge is a modular AI-assisted reconnaissance framework for professional bug bounty and penetration testing.

## Principles

- Never break existing architecture.
- Preserve backward compatibility whenever possible.
- Prefer modular design over monolithic code.
- One responsibility per module.
- Every feature must include documentation.
- Every feature must include tests.
- Explain architectural decisions before implementing major changes.

## Coding Standards

- Python 3.13+
- Type hints everywhere.
- Google-style docstrings.
- Ruff compliant.
- Black formatted.
- Small focused functions.
- Avoid duplicated logic.

## Architecture

Respect the existing package hierarchy.

Never move files unless explicitly requested.

Never rename public APIs without updating references.

## AI Workflow

Before coding:

1. Analyze project.
2. Explain plan.
3. Identify affected modules.
4. Detect risks.
5. Then implement.

## Git

Never modify unrelated files.

Keep commits focused.

## Documentation

Update README if behavior changes.

Update docs when architecture changes.