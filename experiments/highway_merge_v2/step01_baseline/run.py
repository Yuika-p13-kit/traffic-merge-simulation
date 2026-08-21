"""Run Step 1 uncontrolled baseline cases for highway_merge_v2 only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.common import write_metadata, write_rows
from traffic_merge_sim.highway_merge import run_highway_single_case
from traffic_merge_sim.minimal_merge import RESULT_FIELDS

from config import (
    DEFAULT_CLEARANCE_TIME_S,
    DEFAULT_DURATION_S,
    DEFAULT_MAIN_RATES,
    DEFAULT_RAMP_RATES,
    DEFAULT_SEEDS,
)


def parse_ints(raw: str) -> list[int]:
    return [int(value.strip()) for value in raw.split(",") if value.strip()]


def run(main_rates: list[int], ramp_rates: list[int], seeds: list[int], *, duration_s: float, clearance_time_s: float) -> Path:
    rows = [
        run_highway_single_case(
            main_rate, ramp_rate, duration=duration_s, seed=seed, clearance_time=clearance_time_s,
        )
        for main_rate in main_rates
        for ramp_rate in ramp_rates
        for seed in seeds
    ]
    results_dir = Path(__file__).resolve().parent / "results"
    csv_path = write_rows(results_dir / "baseline_raw.csv", rows, RESULT_FIELDS)
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "highway_merge_v2_step01_uncontrolled_baseline",
        "network": "highway_merge_v2",
        "script": "experiments/highway_merge_v2/step01_baseline/run.py",
        "csv": "experiments/highway_merge_v2/step01_baseline/results/baseline_raw.csv",
        "main_rates_veh_h": main_rates,
        "ramp_rates_veh_h": ramp_rates,
        "seeds": seeds,
        "demand_duration_s": duration_s,
        "clearance_time_s": clearance_time_s,
    })
    return csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the highway_merge_v2 Step 1 uncontrolled baseline.")
    parser.add_argument("--main-rates", default=",".join(map(str, DEFAULT_MAIN_RATES)))
    parser.add_argument("--ramp-rates", default=",".join(map(str, DEFAULT_RAMP_RATES)))
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME_S)
    args = parser.parse_args()
    output = run(
        parse_ints(args.main_rates), parse_ints(args.ramp_rates), parse_ints(args.seeds),
        duration_s=args.duration, clearance_time_s=args.clearance_time,
    )
    print(f"Highway Step 1 baseline saved to: {output}")
