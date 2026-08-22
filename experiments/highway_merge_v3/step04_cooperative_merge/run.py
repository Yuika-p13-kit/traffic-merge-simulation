"""Compare bounded cooperative merge control with v3's uncontrolled baseline."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
STEP_DIR = Path(__file__).resolve().parent
for path in (ROOT, ROOT / "src", STEP_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config import (
    COOLDOWN_S, COOPERATIVE_SPEED_M_S, DEFAULT_CLEARANCE_TIME_S, DEFAULT_DEMAND_RATIOS,
    DEFAULT_DURATION_S, DEFAULT_SEEDS, DEFAULT_STRATEGIES, DEFAULT_TOTAL_RATES,
    MAIN_CONTROL_DISTANCE_M, MAIN_CONTROL_LANE_ID, MAIN_MIN_DISTANCE_M, MAX_CONFLICT_ETA_S, MAX_INTERVENTION_S, MAX_PAIR_ETA_GAP_S,
    MIN_CONFLICT_ETA_S, RAMP_ACTIVATION_DISTANCE_M, RAMP_WAIT_THRESHOLD_S,
)
from controller import CooperativeSettings, LimitedCooperativeController, VehicleState
from experiments.common import write_metadata, write_rows
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.highway_merge import run_highway_v3_single_case
from traffic_merge_sim.metrics import estimate_generated_vehicles, summarize_step_series, summarize_tripinfo
from traffic_merge_sim.minimal_merge import RESULT_FIELDS
from traffic_merge_sim.network_config import HIGHWAY_MERGE_V3
from traffic_merge_sim.paths import GENERATED_OUTPUT_DIR
from traffic_merge_sim.route_builder import build_case_route_file
from traffic_merge_sim.sumo_runner import locate_sumo_binary

SETTINGS = CooperativeSettings(
    RAMP_ACTIVATION_DISTANCE_M, RAMP_WAIT_THRESHOLD_S, MAIN_MIN_DISTANCE_M,
    MAIN_CONTROL_DISTANCE_M, MIN_CONFLICT_ETA_S, MAX_CONFLICT_ETA_S, MAX_PAIR_ETA_GAP_S,
    COOPERATIVE_SPEED_M_S, MAX_INTERVENTION_S, COOLDOWN_S,
)
CONTROL_FIELDS = ["interventions", "successful_releases", "timed_out_interventions", "yielded_main_vehicles"]
RAW_FIELDS = ["strategy", "total_demand_veh_h", "demand_ratio", *CONTROL_FIELDS, *RESULT_FIELDS]
SUMMARY_FIELDS = [
    "strategy", "total_demand_veh_h", "demand_ratio", "main_veh_h", "ramp_veh_h", "runs",
    "recovered_runs", "breakdown_runs", "mean_unfinished_vehicles", "mean_throughput_veh_h",
    "mean_peak_queue_vehicles", "mean_avg_wait_time_s", "collision_runs", "teleport_runs",
    "mean_interventions", "mean_successful_releases", "mean_timed_out_interventions",
]


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_ints(raw: str) -> list[int]:
    return [int(item) for item in parse_csv(raw)]


def lane_states(traci: object, lane_id: str, include_waiting: bool) -> list[VehicleState]:
    length = float(traci.lane.getLength(lane_id))
    return [
        VehicleState(
            vehicle_id=vehicle_id,
            distance_to_merge_end_m=max(0.0, length - float(traci.vehicle.getLanePosition(vehicle_id))),
            speed_m_s=float(traci.vehicle.getSpeed(vehicle_id)),
            waiting_time_s=float(traci.vehicle.getWaitingTime(vehicle_id)) if include_waiting else 0.0,
        )
        for vehicle_id in traci.lane.getLastStepVehicleIDs(lane_id)
    ]


def finish_metrics(tripinfo_path: Path, summary_path: Path, main_rate: int, ramp_rate: int, duration: float, clearance: float, seed: int) -> dict[str, object]:
    metrics: dict[str, object] = summarize_tripinfo(tripinfo_path, estimate_generated_vehicles(main_rate, ramp_rate, duration))
    steps = summarize_step_series(summary_path, duration)
    metrics.update(steps)
    metrics["unfinished_vehicles"] = max(0, steps["loaded_vehicles"] - int(metrics["arrived_veh"]))
    metrics.update(main_veh_h=main_rate, side_veh_h=ramp_rate, seed=seed, duration_s=duration, clearance_time_s=clearance, simulation_end_s=duration + clearance)
    metrics["throughput"] = int(metrics["arrived_veh"]) / duration
    return metrics


def run_limited_case(main_rate: int, ramp_rate: int, duration: float, clearance: float, seed: int) -> dict[str, object]:
    import traci

    output_dir = GENERATED_OUTPUT_DIR / HIGHWAY_MERGE_V3.name
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"v3_cooperative_main_{main_rate}_ramp_{ramp_rate}_seed_{seed}"
    route_path, tripinfo_path, summary_path = (output_dir / f"{prefix}{suffix}" for suffix in (".rou.xml", ".tripinfo.xml", ".summary.xml"))
    for path in (route_path, tripinfo_path, summary_path):
        path.unlink(missing_ok=True)
    build_case_route_file(route_path, main_rate, ramp_rate, duration, network=HIGHWAY_MERGE_V3)
    command = [locate_sumo_binary(), "-n", str(HIGHWAY_MERGE_V3.network_path), "-r", str(route_path), "--no-step-log", "--quit-on-end", "--tripinfo-output", str(tripinfo_path), "--summary-output", str(summary_path), "--xml-validation", "never", "--time-to-teleport", "-1", "--end", str(duration + clearance), "--seed", str(seed)]
    controller = LimitedCooperativeController(SETTINGS)
    yielded: set[str] = set()
    traci.start(command)
    try:
        while traci.simulation.getTime() < duration + clearance:
            traci.simulationStep()
            now_s = float(traci.simulation.getTime())
            ids = set(traci.vehicle.getIDList())
            # Retain the advisory through the short downstream convergence;
            # improvement 3 showed that releasing at the lane change is too early.
            target_completed = bool(controller.target_ramp_vehicle and controller.target_ramp_vehicle not in ids)
            released = controller.observe(now_s, target_completed, bool(controller.active_main_vehicle in ids))
            if released and released in ids:
                traci.vehicle.setSpeed(released, -1)
            selected = controller.select_candidate(now_s, lane_states(traci, "main_merge_0", True), lane_states(traci, MAIN_CONTROL_LANE_ID, False))
            if selected and selected in ids:
                traci.vehicle.setSpeed(selected, SETTINGS.cooperative_speed_m_s)
                yielded.add(selected)
    finally:
        if controller.active_main_vehicle in set(traci.vehicle.getIDList()):
            traci.vehicle.setSpeed(controller.active_main_vehicle, -1)
        traci.close()
    metrics = finish_metrics(tripinfo_path, summary_path, main_rate, ramp_rate, duration, clearance, seed)
    metrics.update(strategy="cooperative_limited", interventions=controller.interventions, successful_releases=controller.successful_releases, timed_out_interventions=controller.timed_out_interventions, yielded_main_vehicles=len(yielded))
    return metrics


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for strategy in sorted({str(row["strategy"]) for row in rows}):
        selected = [row for row in rows if row["strategy"] == strategy]
        output.append({
            "strategy": strategy, "total_demand_veh_h": selected[0]["total_demand_veh_h"], "demand_ratio": selected[0]["demand_ratio"], "main_veh_h": selected[0]["main_veh_h"], "ramp_veh_h": selected[0]["side_veh_h"], "runs": len(selected),
            "recovered_runs": sum(int(row["unfinished_vehicles"]) == 0 for row in selected), "breakdown_runs": sum(int(row["unfinished_vehicles"]) > 0 for row in selected),
            "mean_unfinished_vehicles": mean(float(row["unfinished_vehicles"]) for row in selected), "mean_throughput_veh_h": mean(float(row["throughput"]) for row in selected) * 3600,
            "mean_peak_queue_vehicles": mean(float(row["peak_queue_vehicles"]) for row in selected), "mean_avg_wait_time_s": mean(float(row["avg_wait_time_s"]) for row in selected),
            "collision_runs": sum(int(row["collisions"]) > 0 for row in selected), "teleport_runs": sum(int(row["teleports"]) > 0 for row in selected),
            "mean_interventions": mean(float(row["interventions"]) for row in selected), "mean_successful_releases": mean(float(row["successful_releases"]) for row in selected), "mean_timed_out_interventions": mean(float(row["timed_out_interventions"]) for row in selected),
        })
    return output


def run(total_rates: list[int], ratios: list[str], strategies: list[str], seeds: list[int], *, duration_s: float, clearance_time_s: float, output_dir: Path | None = None) -> Path:
    if set(strategies) - {"uncontrolled", "cooperative_limited"}:
        raise ValueError("strategies must be uncontrolled and/or cooperative_limited")
    rows: list[dict[str, object]] = []
    for total_rate in total_rates:
        for ratio in ratios:
            main_rate, ramp_rate = allocate_demand(total_rate, ratio)
            for strategy in strategies:
                for seed in seeds:
                    row = run_highway_v3_single_case(main_rate, ramp_rate, duration=duration_s, clearance_time=clearance_time_s, seed=seed) if strategy == "uncontrolled" else run_limited_case(main_rate, ramp_rate, duration_s, clearance_time_s, seed)
                    row.update(strategy=strategy, total_demand_veh_h=total_rate, demand_ratio=ratio)
                    if strategy == "uncontrolled": row.update({field: 0 for field in CONTROL_FIELDS})
                    rows.append(row)
    result_dir = output_dir or STEP_DIR / "results"
    raw_path = write_rows(result_dir / "cooperative_raw.csv", rows, RAW_FIELDS)
    write_rows(result_dir / "cooperative_summary.csv", summarize(rows), SUMMARY_FIELDS)
    write_metadata(result_dir / "metadata.json", {"experiment_id": "highway_merge_v3_step04_cooperative", "network": HIGHWAY_MERGE_V3.name, "strategies": strategies, "total_rates_veh_h": total_rates, "demand_ratios": ratios, "seeds": seeds, "demand_duration_s": duration_s, "clearance_time_s": clearance_time_s, "cooperative_settings": SETTINGS.__dict__})
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--total-rates", default=",".join(map(str, DEFAULT_TOTAL_RATES)))
    parser.add_argument("--demand-ratios", default=",".join(DEFAULT_DEMAND_RATIOS))
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME_S)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(run(parse_ints(args.total_rates), parse_csv(args.demand_ratios), parse_csv(args.strategies), parse_ints(args.seeds), duration_s=args.duration, clearance_time_s=args.clearance_time, output_dir=args.output_dir))
