from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from traffic_merge_sim.minimal_merge import run_minimal_merge_experiment


if __name__ == "__main__":
    run_minimal_merge_experiment()
