from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.common import write_metadata, write_rows
from experiments.step03_fixed_control.config import (
    DEFAULT_CLEARANCE_TIME,
    DEFAULT_DURATION,
    DEFAULT_MAIN_RATES,
    DEFAULT_SEEDS,
    DEFAULT_SIDE_RATES,
    DEFAULT_STRATEGIES,
)
from traffic_merge_sim.minimal_merge import RESULT_FIELDS
from traffic_merge_sim.sumo_runner import run_fixed_control_case, run_single_case

RAW_FIELDS = ["strategy", *RESULT_FIELDS]
SUMMARY_FIELDS = [
    "strategy", "main_veh_h", "side_veh_h", "runs", "free_flow_runs", "queue_runs",
    "breakdown_runs", "classification", "mean_peak_queue_vehicles",
    "max_peak_queue_vehicles", "mean_avg_wait_time_s", "mean_total_travel_time_s",
    "mean_unfinished_vehicles", "mean_throughput_veh_s",
]
STATE_PRIORITY = {"free_flow": 0, "queue": 1, "breakdown": 2}


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_ints(raw: str) -> list[int]:
    return [int(item) for item in parse_csv(raw)]


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    conditions = sorted({
        (str(row["strategy"]), int(row["main_veh_h"]), int(row["side_veh_h"]))
        for row in rows
    })
    for strategy, main_rate, side_rate in conditions:
        selected = [row for row in rows if (
            row["strategy"] == strategy
            and row["main_veh_h"] == main_rate
            and row["side_veh_h"] == side_rate
        )]
        counts = Counter(str(row["state"]) for row in selected)
        classification = max(counts, key=lambda state: (counts[state], STATE_PRIORITY[state]))
        summaries.append({
            "strategy": strategy,
            "main_veh_h": main_rate,
            "side_veh_h": side_rate,
            "runs": len(selected),
            "free_flow_runs": counts["free_flow"],
            "queue_runs": counts["queue"],
            "breakdown_runs": counts["breakdown"],
            "classification": classification,
            "mean_peak_queue_vehicles": mean(float(row["peak_queue_vehicles"]) for row in selected),
            "max_peak_queue_vehicles": max(int(row["peak_queue_vehicles"]) for row in selected),
            "mean_avg_wait_time_s": mean(float(row["avg_wait_time_s"]) for row in selected),
            "mean_total_travel_time_s": mean(float(row["total_travel_time_s"]) for row in selected),
            "mean_unfinished_vehicles": mean(float(row["unfinished_vehicles"]) for row in selected),
            "mean_throughput_veh_s": mean(float(row["throughput"]) for row in selected),
        })
    return summaries


def run(
    main_rates: list[int], side_rates: list[int], strategies: list[str], duration: float,
    clearance_time: float, seeds: list[int], output_dir: Path | None = None,
) -> Path:
    results_dir = output_dir or Path(__file__).resolve().parent / "results"
    rows: list[dict[str, object]] = []
    for strategy in strategies:
        for main_rate in main_rates:
            for side_rate in side_rates:
                for seed in seeds:
                    if strategy == "uncontrolled":
                        row = run_single_case(
                            main_veh_h=main_rate, side_veh_h=side_rate, duration=duration,
                            clearance_time=clearance_time, seed=seed,
                        )
                        row["strategy"] = strategy
                    else:
                        row = run_fixed_control_case(
                            main_rate, side_rate, strategy, duration, clearance_time, seed,
                        )
                    rows.append(row)

    raw_path = write_rows(results_dir / "fixed_control_raw.csv", rows, RAW_FIELDS)
    write_rows(results_dir / "fixed_control_summary.csv", summarize(rows), SUMMARY_FIELDS)
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "step03_fixed_control",
        "script": "experiments/step03_fixed_control/run.py",
        "raw_csv": "fixed_control_raw.csv",
        "summary_csv": "fixed_control_summary.csv",
        "strategies": strategies,
        "strategy_definition": "main vehicles passed : side vehicles passed; demand ratio is independent",
        "seeds": seeds,
        "demand_duration_s": duration,
        "clearance_time_s": clearance_time,
        "main_rates": main_rates,
        "side_rates": side_rates,
    })
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare uncontrolled and fixed vehicle-count merge strategies.")
    parser.add_argument("--main-rates", default=",".join(map(str, DEFAULT_MAIN_RATES)))
    parser.add_argument("--side-rates", default=",".join(map(str, DEFAULT_SIDE_RATES)))
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME)
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    run(
        parse_ints(args.main_rates), parse_ints(args.side_rates), parse_csv(args.strategies),
        args.duration, args.clearance_time, parse_ints(args.seeds), args.output_dir,
    )
