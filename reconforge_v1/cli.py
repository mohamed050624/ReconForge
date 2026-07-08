"""ReconForge V1 CLI adapter.

This module is the stable CLI layer for the program-level workflow.
The current engine still lives in reconforge_one.py and will be split into
smaller modules incrementally.
"""

from __future__ import annotations

import sys

from reconforge_one import main as run_program_recon


def main() -> int:
    """Run the ReconForge V1 program-level CLI."""
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        sys.argv.pop(1)

    return run_program_recon()
