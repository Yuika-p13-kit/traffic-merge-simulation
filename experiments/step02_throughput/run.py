from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from experiments.common import write_metadata, write_rows
from experiments.step02_throughput.config import (
    DEFAULT_CLEARANCE_TIME,
    DEFAULT_DURATION,
    DEFAULT_MAIN_RATES,
    DEFAULT_SEEDS,
    DEFAULT_SIDE_RATES,
)
from traffic_merge_sim.minimal_merge import RESULT_FIELDS
from traffic_merge_sim.sumo_runner import run_single_case

SUMMARY_FIELDS = [
    "main_veh_h", "side_veh_h", "runs", "free_flow_runs", "queue_runs", "breakdown_runs",
    "classification", "mean_peak_queue_vehicles", "max_peak_queue_vehicles",
    "mean_avg_wait_time_s", "mean_unfinished_vehicles", "mean_throughput_veh_s",
]
STATE_PRIORITY = {"free_flow": 0, "queue": 1, "breakdown": 2}


def parse_ints(raw: str) -> list[int]:
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    conditions = sorted({(int(row["main_veh_h"]), int(row["side_veh_h"])) for row in rows})
    for main_rate, side_rate in conditions:
        selected = [row for row in rows if row["main_veh_h"] == main_rate and row["side_veh_h"] == side_rate]
        counts = Counter(str(row["state"]) for row in selected)
        classification = max(counts, key=lambda state: (counts[state], STATE_PRIORITY[state]))
        summaries.append({
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
            "mean_unfinished_vehicles": mean(float(row["unfinished_vehicles"]) for row in selected),
            "mean_throughput_veh_s": mean(float(row["throughput"]) for row in selected),
        })
    return summaries


def run(
    main_rates: list[int], side_rates: list[int], duration: float,
    clearance_time: float, seeds: list[int], output_dir: Path | None = None,
) -> Path:
    results_dir = output_dir or Path(__file__).resolve().parent / "results"
    rows = [
        run_single_case(
            main_veh_h=main_rate,
            side_veh_h=side_rate,
            duration=duration,
            clearance_time=clearance_time,
            seed=seed,
        )
        for main_rate in main_rates
        for side_rate in side_rates
        for seed in seeds
    ]
    raw_path = write_rows(results_dir / "throughput_raw.csv", rows, RESULT_FIELDS)
    write_rows(results_dir / "throughput_summary.csv", summarize(rows), SUMMARY_FIELDS)
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "step02_throughput_boundary",
        "script": "experiments/step02_throughput/run.py",
        "raw_csv": "throughput_raw.csv",
        "summary_csv": "throughput_summary.csv",
        "seeds": seeds,
        "demand_duration_s": duration,
        "clearance_time_s": clearance_time,
        "main_rates": main_rates,
        "side_rates": side_rates,
        "classification": {
            "free_flow": "no SUMO halting/waiting vehicles during demand and none unfinished after clearance",
            "queue": "halting/waiting vehicles observed during demand, all cleared afterward",
            "breakdown": "one or more vehicles unfinished after clearance",
            "aggregation": "majority over seeds; ties use the more severe state",
        },
    })
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure the queue/breakdown boundary with a clearance period.")
    parser.add_argument("--main-rates", default=",".join(map(str, DEFAULT_MAIN_RATES)))
    parser.add_argument("--side-rates", default=",".join(map(str, DEFAULT_SIDE_RATES)))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME)
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    run(
        parse_ints(args.main_rates), parse_ints(args.side_rates), args.duration,
        args.clearance_time, parse_ints(args.seeds), args.output_dir,
    )
