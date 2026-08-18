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

from config import (
    COOLDOWN_S, COOPERATIVE_SPEED_M_S, DEFAULT_CLEARANCE_TIME, DEFAULT_DEMAND_RATIOS,
    DEFAULT_DURATION, DEFAULT_SEEDS, DEFAULT_STRATEGIES, DEFAULT_TOTAL_RATES,
    MAIN_CONTROL_DISTANCE_M, MAIN_MIN_DISTANCE_M, MAX_CONFLICT_ETA_S,
    MAX_INTERVENTION_S, MIN_CONFLICT_ETA_S, SIDE_ACTIVATION_DISTANCE_M,
    SIDE_WAIT_THRESHOLD_S,
)
from controller import LimitedCooperativeController, LimitedSettings, VehicleState
from experiments.common import write_metadata, write_rows
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.metrics import classify_state, estimate_generated_vehicles, summarize_step_series, summarize_tripinfo
from traffic_merge_sim.minimal_merge import RESULT_FIELDS
from traffic_merge_sim.paths import GENERATED_OUTPUT_DIR, NETWORK_PATH
from traffic_merge_sim.route_builder import build_case_route_file
from traffic_merge_sim.sumo_runner import locate_sumo_binary, run_single_case

SETTINGS = LimitedSettings(
    side_activation_distance_m=SIDE_ACTIVATION_DISTANCE_M,
    side_wait_threshold_s=SIDE_WAIT_THRESHOLD_S,
    main_control_distance_m=MAIN_CONTROL_DISTANCE_M,
    main_min_distance_m=MAIN_MIN_DISTANCE_M,
    min_conflict_eta_s=MIN_CONFLICT_ETA_S,
    max_conflict_eta_s=MAX_CONFLICT_ETA_S,
    cooperative_speed_m_s=COOPERATIVE_SPEED_M_S,
    max_intervention_s=MAX_INTERVENTION_S,
    cooldown_s=COOLDOWN_S,
)
CONTROL_FIELDS = ["interventions", "successful_releases", "timed_out_interventions", "yielded_main_vehicles"]
RAW_FIELDS = ["strategy", "demand_ratio", "total_demand_veh_h", *CONTROL_FIELDS, *RESULT_FIELDS]
SUMMARY_FIELDS = [
    "strategy", "demand_ratio", "total_demand_veh_h", "main_veh_h", "side_veh_h", "runs",
    "queue_runs", "breakdown_runs", "classification", "mean_peak_queue_vehicles",
    "mean_avg_wait_time_s", "mean_unfinished_vehicles", "mean_throughput_veh_h",
    "mean_interventions", "mean_successful_releases", "mean_timed_out_interventions",
    "mean_yielded_main_vehicles",
]
STATE_PRIORITY = {"free_flow": 0, "queue": 1, "breakdown": 2}


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_ints(raw: str) -> list[int]:
    return [int(item) for item in parse_csv(raw)]


def lane_states(traci: object, lane_id: str, include_waiting: bool) -> list[VehicleState]:
    length = float(traci.lane.getLength(lane_id))
    return [
        VehicleState(
            vehicle_id=vehicle_id,
            distance_to_merge_m=max(0.0, length - float(traci.vehicle.getLanePosition(vehicle_id))),
            speed_m_s=float(traci.vehicle.getSpeed(vehicle_id)),
            waiting_time_s=float(traci.vehicle.getWaitingTime(vehicle_id)) if include_waiting else 0.0,
        )
        for vehicle_id in traci.lane.getLastStepVehicleIDs(lane_id)
    ]


def finish_metrics(
    tripinfo_path: Path, summary_path: Path, main_rate: int, side_rate: int,
    duration: float, clearance_time: float, seed: int,
) -> dict[str, object]:
    expected = estimate_generated_vehicles(main_rate, side_rate, duration)
    metrics: dict[str, object] = summarize_tripinfo(tripinfo_path, expected)
    step_metrics = summarize_step_series(summary_path, duration)
    metrics.update(step_metrics)
    metrics["expected_generated_veh"] = expected
    metrics["generated_veh"] = step_metrics["loaded_vehicles"]
    metrics["unfinished_vehicles"] = max(0, step_metrics["loaded_vehicles"] - int(metrics["arrived_veh"]))
    metrics.update(
        main_veh_h=main_rate, side_veh_h=side_rate, seed=seed, duration_s=float(duration),
        clearance_time_s=float(clearance_time), simulation_end_s=float(duration + clearance_time),
    )
    metrics["throughput"] = int(metrics["arrived_veh"]) / duration if duration else 0.0
    metrics["queue_length"] = step_metrics["final_running_vehicles"] + step_metrics["final_waiting_vehicles"]
    metrics["state"] = classify_state(int(metrics["unfinished_vehicles"]), step_metrics["peak_queue_vehicles"])
    return metrics


def run_limited_case(
    main_rate: int, side_rate: int, duration: float, clearance_time: float, seed: int,
) -> dict[str, object]:
    import traci

    simulation_end = duration + clearance_time
    GENERATED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    case_name = f"cooperative_limited_main_{main_rate}_side_{side_rate}_seed_{seed}"
    route_path = GENERATED_OUTPUT_DIR / f"{case_name}.rou.xml"
    tripinfo_path = GENERATED_OUTPUT_DIR / f"{case_name}.tripinfo.xml"
    summary_path = GENERATED_OUTPUT_DIR / f"{case_name}.summary.xml"
    for path in (route_path, tripinfo_path, summary_path):
        path.unlink(missing_ok=True)
    build_case_route_file(route_path, main_rate, side_rate, duration)
    command = [
        locate_sumo_binary(), "-n", str(NETWORK_PATH), "-r", str(route_path), "--no-step-log",
        "--quit-on-end", "--tripinfo-output", str(tripinfo_path), "--summary-output",
        str(summary_path), "--xml-validation", "never", "--time-to-teleport", "-1",
        "--end", str(simulation_end), "--seed", str(seed),
    ]

    controller = LimitedCooperativeController(SETTINGS)
    yielded: set[str] = set()
    previous_out: set[str] = set()
    traci.start(command)
    try:
        while traci.simulation.getTime() < simulation_end:
            traci.simulationStep()
            now_s = float(traci.simulation.getTime())
            ids = set(traci.vehicle.getIDList())
            current_out = set(traci.edge.getLastStepVehicleIDs("out"))
            merged_side_vehicles = {
                vehicle_id for vehicle_id in current_out - previous_out
                if vehicle_id.startswith("side_flow")
            }
            released = controller.observe(
                now_s, merged_side_vehicles, bool(controller.active_main_vehicle in ids),
            )
            if released and released in ids:
                traci.vehicle.setSpeed(released, -1)

            selected = controller.select_candidate(
                now_s,
                lane_states(traci, "side_in_0", include_waiting=True),
                lane_states(traci, "main_in_0", include_waiting=False),
            )
            if selected and selected in ids:
                traci.vehicle.setSpeed(selected, SETTINGS.cooperative_speed_m_s)
                yielded.add(selected)
            previous_out = current_out
    finally:
        active = controller.active_main_vehicle
        if active and active in traci.vehicle.getIDList():
            traci.vehicle.setSpeed(active, -1)
        traci.close()

    metrics = finish_metrics(tripinfo_path, summary_path, main_rate, side_rate, duration, clearance_time, seed)
    metrics.update(
        strategy="cooperative_limited", interventions=controller.interventions,
        successful_releases=controller.successful_releases,
        timed_out_interventions=controller.timed_out_interventions,
        yielded_main_vehicles=len(yielded),
    )
    return metrics


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    keys = sorted({(str(r["strategy"]), int(r["total_demand_veh_h"]), str(r["demand_ratio"])) for r in rows})
    for strategy, total_rate, ratio in keys:
        selected = [r for r in rows if r["strategy"] == strategy and r["total_demand_veh_h"] == total_rate and r["demand_ratio"] == ratio]
        counts = Counter(str(row["state"]) for row in selected)
        classification = max(counts, key=lambda state: (counts[state], STATE_PRIORITY[state]))
        output.append({
            "strategy": strategy, "demand_ratio": ratio, "total_demand_veh_h": total_rate,
            "main_veh_h": selected[0]["main_veh_h"], "side_veh_h": selected[0]["side_veh_h"],
            "runs": len(selected), "queue_runs": counts["queue"], "breakdown_runs": counts["breakdown"],
            "classification": classification,
            "mean_peak_queue_vehicles": mean(float(r["peak_queue_vehicles"]) for r in selected),
            "mean_avg_wait_time_s": mean(float(r["avg_wait_time_s"]) for r in selected),
            "mean_unfinished_vehicles": mean(float(r["unfinished_vehicles"]) for r in selected),
            "mean_throughput_veh_h": mean(float(r["throughput"]) for r in selected) * 3600.0,
            "mean_interventions": mean(float(r["interventions"]) for r in selected),
            "mean_successful_releases": mean(float(r["successful_releases"]) for r in selected),
            "mean_timed_out_interventions": mean(float(r["timed_out_interventions"]) for r in selected),
            "mean_yielded_main_vehicles": mean(float(r["yielded_main_vehicles"]) for r in selected),
        })
    return output


def run(
    total_rates: list[int], ratios: list[str], strategies: list[str], duration: float,
    clearance_time: float, seeds: list[int], output_dir: Path | None = None,
) -> Path:
    unknown = set(strategies) - {"uncontrolled", "cooperative_limited"}
    if unknown:
        raise ValueError(f"Unknown strategies: {sorted(unknown)}")
    rows: list[dict[str, object]] = []
    for total_rate in total_rates:
        for ratio in ratios:
            main_rate, side_rate = allocate_demand(total_rate, ratio)
            for strategy in strategies:
                for seed in seeds:
                    if strategy == "uncontrolled":
                        row: dict[str, object] = run_single_case(
                            main_veh_h=main_rate, side_veh_h=side_rate, duration=duration,
                            clearance_time=clearance_time, seed=seed,
                        )
                        row.update(strategy=strategy, **{field: 0 for field in CONTROL_FIELDS})
                    else:
                        row = run_limited_case(main_rate, side_rate, duration, clearance_time, seed)
                    row.update(demand_ratio=ratio, total_demand_veh_h=total_rate)
                    rows.append(row)
    results_dir = output_dir or STEP_DIR / "results"
    raw_path = write_rows(results_dir / "cooperative_limited_raw.csv", rows, RAW_FIELDS)
    write_rows(results_dir / "cooperative_limited_summary.csv", summarize(rows), SUMMARY_FIELDS)
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "step04_02_cooperative_merge", "script": "experiments/step04-02_cooperative_merge/run.py",
        "raw_csv": raw_path.name, "summary_csv": "cooperative_limited_summary.csv",
        "strategies": strategies, "total_rates": total_rates, "demand_ratios": ratios,
        "seeds": seeds, "demand_duration_s": duration, "clearance_time_s": clearance_time,
        "cooperative_settings": SETTINGS.__dict__,
    })
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare uncontrolled and limited cooperative merging.")
    parser.add_argument("--total-rates", default=",".join(map(str, DEFAULT_TOTAL_RATES)))
    parser.add_argument("--demand-ratios", default=",".join(DEFAULT_DEMAND_RATIOS))
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME)
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(parse_ints(args.total_rates), parse_csv(args.demand_ratios), parse_csv(args.strategies), args.duration, args.clearance_time, parse_ints(args.seeds), args.output_dir)
