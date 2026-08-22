"""Run uncontrolled demand-calibration cases for highway_merge_v3 only."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.common import write_metadata, write_rows
from experiments.highway_merge_v3.step01_baseline.config import (
    DEFAULT_CLEARANCE_TIME_S,
    DEFAULT_DURATION_S,
    DEFAULT_MAIN_RATES,
    DEFAULT_RAMP_RATES,
    DEFAULT_SEEDS,
)
from traffic_merge_sim.highway_merge import run_highway_v3_single_case
from traffic_merge_sim.minimal_merge import RESULT_FIELDS

SUMMARY_FIELDS = [
    "main_veh_h", "ramp_veh_h", "runs", "recovered_runs", "unfinished_runs",
    "collision_runs", "teleport_runs", "mean_peak_queue_vehicles",
    "mean_avg_wait_time_s", "mean_unfinished_vehicles", "mean_throughput_veh_s",
]


def parse_ints(raw: str) -> list[int]:
    return [int(value.strip()) for value in raw.split(",") if value.strip()]


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    conditions = sorted({(int(row["main_veh_h"]), int(row["side_veh_h"])) for row in rows})
    for main_rate, ramp_rate in conditions:
        selected = [
            row for row in rows
            if int(row["main_veh_h"]) == main_rate and int(row["side_veh_h"]) == ramp_rate
        ]
        summaries.append({
            "main_veh_h": main_rate,
            "ramp_veh_h": ramp_rate,
            "runs": len(selected),
            "recovered_runs": sum(int(row["unfinished_vehicles"]) == 0 for row in selected),
            "unfinished_runs": sum(int(row["unfinished_vehicles"]) > 0 for row in selected),
            "collision_runs": sum(int(row["collisions"]) > 0 for row in selected),
            "teleport_runs": sum(int(row["teleports"]) > 0 for row in selected),
            "mean_peak_queue_vehicles": mean(float(row["peak_queue_vehicles"]) for row in selected),
            "mean_avg_wait_time_s": mean(float(row["avg_wait_time_s"]) for row in selected),
            "mean_unfinished_vehicles": mean(float(row["unfinished_vehicles"]) for row in selected),
            "mean_throughput_veh_s": mean(float(row["throughput"]) for row in selected),
        })
    return summaries


def run(
    main_rates: list[int], ramp_rates: list[int], seeds: list[int], *,
    duration_s: float, clearance_time_s: float, output_dir: Path | None = None,
) -> Path:
    results_dir = output_dir or Path(__file__).resolve().parent / "results"
    rows = [
        run_highway_v3_single_case(
            main_rate, ramp_rate, duration=duration_s, seed=seed,
            clearance_time=clearance_time_s,
        )
        for main_rate in main_rates
        for ramp_rate in ramp_rates
        for seed in seeds
    ]
    raw_path = write_rows(results_dir / "baseline_raw.csv", rows, RESULT_FIELDS)
    write_rows(results_dir / "baseline_summary.csv", summarize(rows), SUMMARY_FIELDS)
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "highway_merge_v3_step01_uncontrolled_baseline",
        "network": "highway_merge_v3",
        "script": "experiments/highway_merge_v3/step01_baseline/run.py",
        "raw_csv": "baseline_raw.csv",
        "summary_csv": "baseline_summary.csv",
        "main_rates_veh_h": main_rates,
        "ramp_rates_veh_h": ramp_rates,
        "seeds": seeds,
        "demand_duration_s": duration_s,
        "clearance_time_s": clearance_time_s,
        "acceptance": {
            "recovery": "all loaded vehicles arrive by the end of clearance",
            "simulation_integrity": "no collisions and no teleports",
        },
    })
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the highway_merge_v3 Step 1 uncontrolled baseline.")
    parser.add_argument("--main-rates", default=",".join(map(str, DEFAULT_MAIN_RATES)))
    parser.add_argument("--ramp-rates", default=",".join(map(str, DEFAULT_RAMP_RATES)))
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME_S)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output = run(
        parse_ints(args.main_rates), parse_ints(args.ramp_rates), parse_ints(args.seeds),
        duration_s=args.duration, clearance_time_s=args.clearance_time,
        output_dir=args.output_dir,
    )
    print(f"Highway merge v3 Step 1 results saved to: {output}")
