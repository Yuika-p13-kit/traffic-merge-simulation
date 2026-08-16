from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from experiments.common import write_metadata
from experiments.step01_baseline.config import DEFAULT_DURATION, DEFAULT_MAIN_RATES, DEFAULT_SEED, DEFAULT_SIDE_RATES
from traffic_merge_sim.minimal_merge import run_load_sweep


def parse_rates(raw: str) -> list[int]:
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def run(main_rates: list[int], side_rates: list[int], duration: float, seed: int) -> Path:
    results_dir = Path(__file__).resolve().parent / "results"
    csv_path = run_load_sweep(main_rates, side_rates, duration, seed=seed, csv_path=results_dir / "baseline.csv")
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "step01_uncontrolled_baseline",
        "script": "experiments/step01_baseline/run.py",
        "csv": "experiments/step01_baseline/results/baseline.csv",
        "seed": seed, "duration_s": duration,
        "main_rates": main_rates, "side_rates": side_rates,
    })
    return csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Step 1 uncontrolled baseline validation.")
    parser.add_argument("--main-rates", default=",".join(map(str, DEFAULT_MAIN_RATES)))
    parser.add_argument("--side-rates", default=",".join(map(str, DEFAULT_SIDE_RATES)))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    run(parse_rates(args.main_rates), parse_rates(args.side_rates), args.duration, args.seed)
