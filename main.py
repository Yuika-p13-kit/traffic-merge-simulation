"""Convenience entrypoint for manually checking the current default uncontrolled scenario."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from traffic_merge_sim.minimal_merge import run_minimal_merge_experiment


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the current default uncontrolled merge scenario for quick validation. "
            "For publication-oriented baseline reproduction, use experiments/step01_baseline/run.py."
        )
    )
    parser.add_argument("--q-main", type=int, default=None, help="Mainline demand in veh/h.")
    parser.add_argument("--q-side", type=int, default=None, help="On-ramp demand in veh/h.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed passed to SUMO.")
    parser.add_argument("--duration", type=float, default=1800.0, help="Simulation duration in seconds.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_minimal_merge_experiment(q_main=args.q_main, q_side=args.q_side, seed=args.seed, duration=args.duration)
