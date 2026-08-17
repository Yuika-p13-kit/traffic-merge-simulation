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
from experiments.step03_demand_ratio.config import (
    DEFAULT_CLEARANCE_TIME,
    DEFAULT_DEMAND_RATIOS,
    DEFAULT_DURATION,
    DEFAULT_SEEDS,
    DEFAULT_TOTAL_RATES,
)
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.minimal_merge import RESULT_FIELDS
from traffic_merge_sim.sumo_runner import run_single_case

RAW_FIELDS = ["demand_ratio", "total_demand_veh_h", *RESULT_FIELDS]
SUMMARY_FIELDS = [
    "demand_ratio", "total_demand_veh_h", "main_veh_h", "side_veh_h", "runs",
    "free_flow_runs", "queue_runs", "breakdown_runs", "classification",
    "mean_peak_queue_vehicles", "max_peak_queue_vehicles", "mean_avg_wait_time_s",
    "mean_total_travel_time_s", "mean_unfinished_vehicles", "mean_throughput_veh_s",
]
STATE_PRIORITY = {"free_flow": 0, "queue": 1, "breakdown": 2}


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_ints(raw: str) -> list[int]:
    return [int(item) for item in parse_csv(raw)]


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    conditions = sorted({
        (int(row["total_demand_veh_h"]), str(row["demand_ratio"])) for row in rows
    })
    for total_rate, ratio in conditions:
        selected = [row for row in rows if (
            row["total_demand_veh_h"] == total_rate and row["demand_ratio"] == ratio
        )]
        counts = Counter(str(row["state"]) for row in selected)
        classification = max(counts, key=lambda state: (counts[state], STATE_PRIORITY[state]))
        summaries.append({
            "demand_ratio": ratio,
            "total_demand_veh_h": total_rate,
            "main_veh_h": selected[0]["main_veh_h"],
            "side_veh_h": selected[0]["side_veh_h"],
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
    total_rates: list[int], demand_ratios: list[str], duration: float,
    clearance_time: float, seeds: list[int], output_dir: Path | None = None,
) -> Path:
    results_dir = output_dir or Path(__file__).resolve().parent / "results"
    rows: list[dict[str, object]] = []
    for total_rate in total_rates:
        for ratio in demand_ratios:
            main_rate, side_rate = allocate_demand(total_rate, ratio)
            for seed in seeds:
                row = run_single_case(
                    main_veh_h=main_rate, side_veh_h=side_rate, duration=duration,
                    clearance_time=clearance_time, seed=seed,
                )
                row.update(demand_ratio=ratio, total_demand_veh_h=total_rate)
                rows.append(row)

    raw_path = write_rows(results_dir / "demand_ratio_raw.csv", rows, RAW_FIELDS)
    write_rows(results_dir / "demand_ratio_summary.csv", summarize(rows), SUMMARY_FIELDS)
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "step03_uncontrolled_demand_ratio",
        "script": "experiments/step03_demand_ratio/run.py",
        "raw_csv": "demand_ratio_raw.csv",
        "summary_csv": "demand_ratio_summary.csv",
        "control": "uncontrolled priority merge; no traffic signal",
        "demand_ratio_definition": "main demand : side demand",
        "total_rates": total_rates,
        "demand_ratios": demand_ratios,
        "seeds": seeds,
        "demand_duration_s": duration,
        "clearance_time_s": clearance_time,
    })
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare demand ratios on the uncontrolled priority merge.")
    parser.add_argument("--total-rates", default=",".join(map(str, DEFAULT_TOTAL_RATES)))
    parser.add_argument("--demand-ratios", default=",".join(DEFAULT_DEMAND_RATIOS))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME)
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    run(
        parse_ints(args.total_rates), parse_csv(args.demand_ratios), args.duration,
        args.clearance_time, parse_ints(args.seeds), args.output_dir,
    )
