"""Compare uncontrolled mainline-to-ramp demand ratios for highway_merge_v3."""

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
from experiments.highway_merge_v3.step03_demand_ratio.config import (
    DEFAULT_CLEARANCE_TIME_S,
    DEFAULT_DEMAND_RATIOS,
    DEFAULT_DURATION_S,
    DEFAULT_SEEDS,
    DEFAULT_TOTAL_RATES,
)
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.highway_merge import run_highway_v3_single_case
from traffic_merge_sim.minimal_merge import RESULT_FIELDS

RAW_FIELDS = ["total_demand_veh_h", "demand_ratio", *RESULT_FIELDS, "capacity_state"]
SUMMARY_FIELDS = [
    "total_demand_veh_h", "demand_ratio", "main_veh_h", "ramp_veh_h", "runs",
    "recovered_runs", "breakdown_runs", "classification", "mean_peak_queue_vehicles",
    "max_peak_queue_vehicles", "mean_avg_wait_time_s", "mean_unfinished_vehicles",
    "mean_throughput_veh_h", "collision_runs", "teleport_runs",
]
STATE_PRIORITY = {"recovered": 0, "breakdown": 1}


def parse_csv(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def parse_ints(raw: str) -> list[int]:
    return [int(value) for value in parse_csv(raw)]


def classify_capacity_state(row: dict[str, object]) -> str:
    """Use the Step 2 recovery criterion, independent of temporary stops."""
    return "breakdown" if int(row["unfinished_vehicles"]) > 0 else "recovered"


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    conditions = sorted({(int(row["total_demand_veh_h"]), str(row["demand_ratio"])) for row in rows})
    for total_rate, ratio in conditions:
        selected = [
            row for row in rows
            if int(row["total_demand_veh_h"]) == total_rate and str(row["demand_ratio"]) == ratio
        ]
        counts = Counter(str(row["capacity_state"]) for row in selected)
        classification = max(counts, key=lambda state: (counts[state], STATE_PRIORITY[state]))
        summaries.append({
            "total_demand_veh_h": total_rate,
            "demand_ratio": ratio,
            "main_veh_h": selected[0]["main_veh_h"],
            "ramp_veh_h": selected[0]["side_veh_h"],
            "runs": len(selected),
            "recovered_runs": counts["recovered"],
            "breakdown_runs": counts["breakdown"],
            "classification": classification,
            "mean_peak_queue_vehicles": mean(float(row["peak_queue_vehicles"]) for row in selected),
            "max_peak_queue_vehicles": max(int(row["peak_queue_vehicles"]) for row in selected),
            "mean_avg_wait_time_s": mean(float(row["avg_wait_time_s"]) for row in selected),
            "mean_unfinished_vehicles": mean(float(row["unfinished_vehicles"]) for row in selected),
            "mean_throughput_veh_h": mean(float(row["throughput"]) * 3600 for row in selected),
            "collision_runs": sum(int(row["collisions"]) > 0 for row in selected),
            "teleport_runs": sum(int(row["teleports"]) > 0 for row in selected),
        })
    return summaries


def run(
    total_rates: list[int], demand_ratios: list[str], seeds: list[int], *,
    duration_s: float, clearance_time_s: float, output_dir: Path | None = None,
) -> Path:
    results_dir = output_dir or Path(__file__).resolve().parent / "results"
    rows: list[dict[str, object]] = []
    for total_rate in total_rates:
        for ratio in demand_ratios:
            main_rate, ramp_rate = allocate_demand(total_rate, ratio)
            for seed in seeds:
                row = run_highway_v3_single_case(
                    main_rate, ramp_rate, duration=duration_s, seed=seed,
                    clearance_time=clearance_time_s,
                )
                row.update(total_demand_veh_h=total_rate, demand_ratio=ratio)
                row["capacity_state"] = classify_capacity_state(row)
                rows.append(row)

    raw_path = write_rows(results_dir / "demand_ratio_raw.csv", rows, RAW_FIELDS)
    write_rows(results_dir / "demand_ratio_summary.csv", summarize(rows), SUMMARY_FIELDS)
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "highway_merge_v3_step03_uncontrolled_demand_ratio",
        "network": "highway_merge_v3",
        "script": "experiments/highway_merge_v3/step03_demand_ratio/run.py",
        "raw_csv": "demand_ratio_raw.csv",
        "summary_csv": "demand_ratio_summary.csv",
        "total_rates_veh_h": total_rates,
        "demand_ratios": demand_ratios,
        "demand_ratio_definition": "mainline demand : ramp demand",
        "seeds": seeds,
        "demand_duration_s": duration_s,
        "clearance_time_s": clearance_time_s,
        "classification": {
            "recovered": "all loaded vehicles arrive by the end of the clearance period",
            "breakdown": "one or more loaded vehicles remain unfinished after clearance",
            "aggregation": "majority over seeds; ties use breakdown",
        },
    })
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare uncontrolled demand ratios for highway_merge_v3.")
    parser.add_argument("--total-rates", default=",".join(map(str, DEFAULT_TOTAL_RATES)))
    parser.add_argument("--demand-ratios", default=",".join(DEFAULT_DEMAND_RATIOS))
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME_S)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output = run(
        parse_ints(args.total_rates), parse_csv(args.demand_ratios), parse_ints(args.seeds),
        duration_s=args.duration, clearance_time_s=args.clearance_time, output_dir=args.output_dir,
    )
    print(f"Highway merge v3 Step 3 results saved to: {output}")
