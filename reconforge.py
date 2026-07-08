"""ReconForge V1 program-level CLI entrypoint.

Primary usage:
    python3 reconforge.py run --program hackerone-example --scope-csv scope.csv

Compatibility usage:
    python3 reconforge.py --program hackerone-example --scope-csv scope.csv
"""

from __future__ import annotations

import sys

from reconforge_one import main as run_reconforge_one


def main() -> int:
    """Run the ReconForge V1 CLI."""
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        sys.argv.pop(1)

    return run_reconforge_one()


if __name__ == "__main__":
    raise SystemExit(main())
