# ReconForge

ReconForge is a modular Python framework for authorized Bug Bounty and penetration testing reconnaissance.

It automates reconnaissance workflows, organizes outputs, generates Markdown reports, and creates AI-ready context to help a human security researcher prioritize manual testing.

ReconForge V1 does not automate exploitation, destructive testing, credential attacks, persistence, evasion, malware, or unauthorized activity.

## V1 Features

- Workspace Manager
- Config Loader
- Logger
- Tool Runner
- Subfinder
- Assetfinder
- HTTPX
- WhatWeb
- Katana
- GAU
- Waybackurls
- Markdown Report Generator
- AI Context Generator

## Project Structure

ReconForge/
- core/
- modules/
- ai_context.py
- report.py
- reconforge.py
- config.yaml
- requirements.txt
- README.md

## Setup

Create a Python virtual environment:

python3 -m venv .venv
source .venv/bin/activate

Install dependencies:

pip install --upgrade pip
pip install -r requirements.txt

## Basic Usage

Initialize a workspace:

python3 reconforge.py --target example.com --dry-run --verbose

Run selected tools:

python3 reconforge.py --target example.com --tools subfinder,assetfinder,httpx --verbose

Run all V1 tools:

python3 reconforge.py --target example.com --tools all --verbose

Run without executing external tools:

python3 reconforge.py --target example.com --tools all --dry-run --verbose

## Outputs

ReconForge creates a workspace for each target:

workspaces/<target>/
- logs/
- raw/
- processed/
- reports/

Generated reports:

workspaces/<target>/reports/final_report.md
workspaces/<target>/reports/ai_context.json

## Safety

Only use ReconForge against assets where you have explicit authorization.

ReconForge V1 focuses on reconnaissance, reporting, and AI-ready context generation. It does not perform exploitation.
