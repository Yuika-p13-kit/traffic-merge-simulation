from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = Path(__file__).resolve().parent
for path in (ROOT, ROOT / "src", STEP_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.common import write_metadata, write_rows
from config import (
    COOPERATIVE_SPEED_M_S,
    DEFAULT_CLEARANCE_TIME,
    DEFAULT_DEMAND_RATIOS,
    DEFAULT_DURATION,
    DEFAULT_SEEDS,
    DEFAULT_STRATEGIES,
    DEFAULT_TOTAL_RATES,
    MAIN_CONTROL_DISTANCE_M,
    MAIN_MIN_DISTANCE_M,
    SIDE_ACTIVATION_DISTANCE_M,
    SIDE_WAIT_THRESHOLD_S,
)
from controller import (
    CooperativeSettings,
    VehiclePosition,
    select_yield_vehicle,
)
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.metrics import (
    classify_state,
    estimate_generated_vehicles,
    summarize_step_series,
    summarize_tripinfo,
)
from traffic_merge_sim.minimal_merge import RESULT_FIELDS
from traffic_merge_sim.paths import GENERATED_OUTPUT_DIR, NETWORK_PATH
from traffic_merge_sim.route_builder import build_case_route_file
from traffic_merge_sim.sumo_runner import locate_sumo_binary, run_single_case

RAW_FIELDS = [
    "strategy", "demand_ratio", "total_demand_veh_h", "cooperation_events",
    "yielded_main_vehicles", *RESULT_FIELDS,
]
SUMMARY_FIELDS = [
    "strategy", "demand_ratio", "total_demand_veh_h", "main_veh_h", "side_veh_h",
    "runs", "free_flow_runs", "queue_runs", "breakdown_runs", "classification",
    "mean_peak_queue_vehicles", "mean_avg_wait_time_s", "mean_total_travel_time_s",
    "mean_unfinished_vehicles", "mean_throughput_veh_h", "mean_cooperation_events",
    "mean_yielded_main_vehicles",
]
STATE_PRIORITY = {"free_flow": 0, "queue": 1, "breakdown": 2}
SETTINGS = CooperativeSettings(
    side_activation_distance_m=SIDE_ACTIVATION_DISTANCE_M,
    side_wait_threshold_s=SIDE_WAIT_THRESHOLD_S,
    main_control_distance_m=MAIN_CONTROL_DISTANCE_M,
    main_min_distance_m=MAIN_MIN_DISTANCE_M,
    cooperative_speed_m_s=COOPERATIVE_SPEED_M_S,
)


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_ints(raw: str) -> list[int]:
    return [int(item) for item in parse_csv(raw)]


def lane_vehicles(traci: object, lane_id: str, *, include_waiting: bool) -> list[VehiclePosition]:
    lane_length = float(traci.lane.getLength(lane_id))
    return [
        VehiclePosition(
            vehicle_id=vehicle_id,
            distance_to_merge_m=max(0.0, lane_length - float(traci.vehicle.getLanePosition(vehicle_id))),
            waiting_time_s=float(traci.vehicle.getWaitingTime(vehicle_id)) if include_waiting else 0.0,
        )
        for vehicle_id in traci.lane.getLastStepVehicleIDs(lane_id)
    ]


def run_cooperative_case(
    main_rate: int, side_rate: int, duration: float, clearance_time: float, seed: int,
) -> dict[str, object]:
    import traci

    simulation_end = duration + clearance_time
    GENERATED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    case_name = f"cooperative_main_{main_rate}_side_{side_rate}_seed_{seed}"
    route_path = GENERATED_OUTPUT_DIR / f"{case_name}.rou.xml"
    tripinfo_path = GENERATED_OUTPUT_DIR / f"{case_name}.tripinfo.xml"
    summary_path = GENERATED_OUTPUT_DIR / f"{case_name}.summary.xml"
    for path in (route_path, tripinfo_path, summary_path):
        path.unlink(missing_ok=True)
    build_case_route_file(route_path, main_rate, side_rate, duration)

    command = [
        locate_sumo_binary(), "-n", str(NETWORK_PATH), "-r", str(route_path),
        "--no-step-log", "--quit-on-end", "--tripinfo-output", str(tripinfo_path),
        "--summary-output", str(summary_path), "--xml-validation", "never",
        "--time-to-teleport", "-1", "--end", str(simulation_end), "--seed", str(seed),
    ]
    controlled_vehicle: str | None = None
    yielded_vehicles: set[str] = set()
    cooperation_events = 0
    traci.start(command)
    try:
        while traci.simulation.getTime() < simulation_end:
            traci.simulationStep()
            side_vehicles = lane_vehicles(traci, "side_in_0", include_waiting=True)
            main_vehicles = lane_vehicles(traci, "main_in_0", include_waiting=False)
            selected = select_yield_vehicle(side_vehicles, main_vehicles, SETTINGS)

            if controlled_vehicle and controlled_vehicle != selected:
                if controlled_vehicle in traci.vehicle.getIDList():
                    traci.vehicle.setSpeed(controlled_vehicle, -1)
                controlled_vehicle = None
            if selected:
                if selected != controlled_vehicle:
                    cooperation_events += 1
                    yielded_vehicles.add(selected)
                traci.vehicle.setSpeed(selected, SETTINGS.cooperative_speed_m_s)
                controlled_vehicle = selected
    finally:
        if controlled_vehicle and controlled_vehicle in traci.vehicle.getIDList():
            traci.vehicle.setSpeed(controlled_vehicle, -1)
        traci.close()

    expected = estimate_generated_vehicles(main_rate, side_rate, duration)
    metrics: dict[str, object] = summarize_tripinfo(tripinfo_path, expected)
    step_metrics = summarize_step_series(summary_path, duration)
    metrics.update(step_metrics)
    metrics["expected_generated_veh"] = expected
    metrics["generated_veh"] = step_metrics["loaded_vehicles"]
    metrics["unfinished_vehicles"] = max(0, step_metrics["loaded_vehicles"] - int(metrics["arrived_veh"]))
    metrics.update(
        main_veh_h=main_rate, side_veh_h=side_rate, seed=seed,
        duration_s=float(duration), clearance_time_s=float(clearance_time),
        simulation_end_s=float(simulation_end), strategy="cooperative",
        cooperation_events=cooperation_events, yielded_main_vehicles=len(yielded_vehicles),
    )
    metrics["throughput"] = int(metrics["arrived_veh"]) / duration if duration else 0.0
    metrics["queue_length"] = step_metrics["final_running_vehicles"] + step_metrics["final_waiting_vehicles"]
    metrics["state"] = classify_state(int(metrics["unfinished_vehicles"]), step_metrics["peak_queue_vehicles"])
    return metrics


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    conditions = sorted({
        (str(row["strategy"]), int(row["total_demand_veh_h"]), str(row["demand_ratio"]))
        for row in rows
    })
    for strategy, total_rate, ratio in conditions:
        selected = [row for row in rows if (
            row["strategy"] == strategy and row["total_demand_veh_h"] == total_rate
            and row["demand_ratio"] == ratio
        )]
        counts = Counter(str(row["state"]) for row in selected)
        classification = max(counts, key=lambda state: (counts[state], STATE_PRIORITY[state]))
        summaries.append({
            "strategy": strategy,
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
            "mean_avg_wait_time_s": mean(float(row["avg_wait_time_s"]) for row in selected),
            "mean_total_travel_time_s": mean(float(row["total_travel_time_s"]) for row in selected),
            "mean_unfinished_vehicles": mean(float(row["unfinished_vehicles"]) for row in selected),
            "mean_throughput_veh_h": mean(float(row["throughput"]) for row in selected) * 3600.0,
            "mean_cooperation_events": mean(float(row["cooperation_events"]) for row in selected),
            "mean_yielded_main_vehicles": mean(float(row["yielded_main_vehicles"]) for row in selected),
        })
    return summaries


def run(
    total_rates: list[int], demand_ratios: list[str], strategies: list[str], duration: float,
    clearance_time: float, seeds: list[int], output_dir: Path | None = None,
) -> Path:
    unknown = set(strategies) - {"uncontrolled", "cooperative"}
    if unknown:
        raise ValueError(f"Unknown strategies: {sorted(unknown)}")
    results_dir = output_dir or Path(__file__).resolve().parent / "results"
    rows: list[dict[str, object]] = []
    for total_rate in total_rates:
        for ratio in demand_ratios:
            main_rate, side_rate = allocate_demand(total_rate, ratio)
            for strategy in strategies:
                for seed in seeds:
                    if strategy == "uncontrolled":
                        row: dict[str, object] = run_single_case(
                            main_veh_h=main_rate, side_veh_h=side_rate, duration=duration,
                            clearance_time=clearance_time, seed=seed,
                        )
                        row.update(strategy=strategy, cooperation_events=0, yielded_main_vehicles=0)
                    else:
                        row = run_cooperative_case(main_rate, side_rate, duration, clearance_time, seed)
                    row.update(demand_ratio=ratio, total_demand_veh_h=total_rate)
                    rows.append(row)

    raw_path = write_rows(results_dir / "cooperative_raw.csv", rows, RAW_FIELDS)
    write_rows(results_dir / "cooperative_summary.csv", summarize(rows), SUMMARY_FIELDS)
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "step04_cooperative_merge",
        "script": "experiments/step04-01_cooperative_merge/run.py",
        "raw_csv": "cooperative_raw.csv",
        "summary_csv": "cooperative_summary.csv",
        "strategies": strategies,
        "total_rates": total_rates,
        "demand_ratios": demand_ratios,
        "seeds": seeds,
        "demand_duration_s": duration,
        "clearance_time_s": clearance_time,
        "cooperative_settings": SETTINGS.__dict__,
        "control_definition": "No signal. Slow one approaching mainline vehicle when a side vehicle waits near the merge.",
    })
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare uncontrolled and initial cooperative natural merging.")
    parser.add_argument("--total-rates", default=",".join(map(str, DEFAULT_TOTAL_RATES)))
    parser.add_argument("--demand-ratios", default=",".join(DEFAULT_DEMAND_RATIOS))
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME)
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    run(
        parse_ints(args.total_rates), parse_csv(args.demand_ratios), parse_csv(args.strategies),
        args.duration, args.clearance_time, parse_ints(args.seeds), args.output_dir,
    )
