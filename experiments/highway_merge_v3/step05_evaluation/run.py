"""Evaluate v3's fixed Step-4 candidate with complete TTS and paired CIs."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
STEP_DIR = Path(__file__).resolve().parent
STEP04_DIR = ROOT / "experiments/highway_merge_v3/step04_cooperative_merge"
for path in (ROOT, ROOT / "src", STEP_DIR, STEP04_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from analysis import paired_summary
from controller import CooperativeSettings, LimitedCooperativeController, VehicleState
from config import DEFAULT_CLEARANCE_TIME_S, DEFAULT_DEMAND_RATIOS, DEFAULT_DURATION_S, DEFAULT_SEEDS, DEFAULT_STRATEGIES, DEFAULT_TOTAL_RATES
from experiments.common import write_metadata, write_rows
from metrics import CompleteTTSMetrics
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.metrics import classify_state, summarize_step_series, summarize_tripinfo
from traffic_merge_sim.network_config import HIGHWAY_MERGE_V3
from traffic_merge_sim.paths import GENERATED_OUTPUT_DIR
from traffic_merge_sim.route_builder import build_case_route_file
from traffic_merge_sim.sumo_runner import locate_sumo_binary
from visualize import generate

# Exact Step-4 improvement-02 configuration; do not import the mutable latest Step-4 config.
SETTINGS = CooperativeSettings(606.0, 0.0, 80.0, 260.0, 3.0, 10.0, float("inf"), 23.5, 7.0, 8.0)
MAIN_CONTROL_LANE_ID = "main_merge_1"

RAW_FIELDS = ["strategy", "total_demand_veh_h", "demand_ratio", "seed", "main_veh_h", "ramp_veh_h", "network_time_spent_s", "insertion_wait_time_s", "total_time_spent_s", "main_total_time_spent_s", "ramp_total_time_spent_s", "main_insertion_wait_time_s", "ramp_insertion_wait_time_s", "unfinished_vehicles", "throughput", "peak_queue_vehicles", "collisions", "teleports", "interventions"]
SUMMARY_FIELDS = ["strategy", "runs", "mean_total_time_spent_s", "mean_network_time_spent_s", "mean_insertion_wait_time_s", "mean_main_total_time_spent_s", "mean_ramp_total_time_spent_s", "mean_unfinished_vehicles", "mean_throughput_veh_h", "breakdown_runs", "collision_runs", "teleport_runs", "mean_interventions"]
PAIRED_FIELDS = ["metric", "paired_seeds", "mean_paired_delta", "ci_95_low", "ci_95_high", "lower_is_better", "interpretation"]


def lane_states(traci: object, lane_id: str, waiting: bool) -> list[VehicleState]:
    length = float(traci.lane.getLength(lane_id))
    return [VehicleState(vehicle_id=vehicle_id, distance_to_merge_end_m=max(0, length - float(traci.vehicle.getLanePosition(vehicle_id))), speed_m_s=float(traci.vehicle.getSpeed(vehicle_id)), waiting_time_s=float(traci.vehicle.getWaitingTime(vehicle_id)) if waiting else 0.0) for vehicle_id in traci.lane.getLastStepVehicleIDs(lane_id)]


def select_improvement_02(controller: LimitedCooperativeController, now: float, ramps: list[VehicleState], mains: list[VehicleState]) -> str | None:
    """Reproduce the pre-ETA-pairing Step-4 improvement-02 selector exactly."""
    if controller.active_main_vehicle or now < controller.cooldown_until_s:
        return controller.active_main_vehicle
    ramps = [vehicle for vehicle in ramps if vehicle.distance_to_merge_end_m <= SETTINGS.ramp_activation_distance_m and vehicle.waiting_time_s >= SETTINGS.ramp_wait_threshold_s]
    candidates = [vehicle for vehicle in mains if SETTINGS.main_min_distance_m <= vehicle.distance_to_merge_end_m <= SETTINGS.main_control_distance_m and SETTINGS.min_conflict_eta_s <= vehicle.distance_to_merge_end_m / max(vehicle.speed_m_s, .1) <= SETTINGS.max_conflict_eta_s]
    if not ramps or not candidates:
        return None
    selected = min(candidates, key=lambda vehicle: vehicle.distance_to_merge_end_m / max(vehicle.speed_m_s, .1))
    controller.active_main_vehicle = selected.vehicle_id
    controller.target_ramp_vehicle = min(ramps, key=lambda vehicle: vehicle.distance_to_merge_end_m).vehicle_id
    controller.intervention_started_s = now; controller.interventions += 1
    return selected.vehicle_id


def run_case(strategy: str, main_rate: int, ramp_rate: int, duration: float, clearance: float, seed: int, fcd_output_dir: Path | None = None) -> dict[str, object]:
    import traci
    output_dir = GENERATED_OUTPUT_DIR / HIGHWAY_MERGE_V3.name
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"v3_step05_{strategy}_main_{main_rate}_ramp_{ramp_rate}_seed_{seed}"
    route, tripinfo, summary = (output_dir / f"{prefix}{suffix}" for suffix in (".rou.xml", ".tripinfo.xml", ".summary.xml"))
    fcd_path = fcd_output_dir / f"{strategy}_main_{main_rate}_ramp_{ramp_rate}_seed_{seed}.fcd.xml" if fcd_output_dir else None
    for path in (route, tripinfo, summary, fcd_path):
        if path is not None: path.unlink(missing_ok=True)
    build_case_route_file(route, main_rate, ramp_rate, duration, network=HIGHWAY_MERGE_V3)
    command = [locate_sumo_binary(), "-n", str(HIGHWAY_MERGE_V3.network_path), "-r", str(route), "--no-step-log", "--quit-on-end", "--tripinfo-output", str(tripinfo), "--summary-output", str(summary), "--xml-validation", "never", "--time-to-teleport", "-1", "--end", str(duration + clearance), "--seed", str(seed)]
    if fcd_path is not None:
        fcd_path.parent.mkdir(parents=True, exist_ok=True)
        command.extend(["--fcd-output", str(fcd_path)])
    recorder, controller, yielded = CompleteTTSMetrics(), (LimitedCooperativeController(SETTINGS) if strategy == "cooperative_limited" else None), set()
    traci.start(command)
    try:
        while traci.simulation.getTime() < duration + clearance:
            traci.simulationStep(); now = float(traci.simulation.getTime()); ids = set(traci.vehicle.getIDList())
            recorder.observe({vehicle: float(traci.vehicle.getSpeed(vehicle)) for vehicle in ids}, set(traci.simulation.getPendingVehicles()), set(traci.simulation.getLoadedIDList()), set(traci.simulation.getDepartedIDList()), set(traci.simulation.getArrivedIDList()), within_demand=now <= duration)
            if controller is not None:
                released = controller.observe(now, bool(controller.target_ramp_vehicle and controller.target_ramp_vehicle not in ids), bool(controller.active_main_vehicle in ids))
                if released and released in ids: traci.vehicle.setSpeed(released, -1)
                selected = select_improvement_02(controller, now, lane_states(traci, "main_merge_0", True), lane_states(traci, MAIN_CONTROL_LANE_ID, False))
                if selected and selected in ids: traci.vehicle.setSpeed(selected, SETTINGS.cooperative_speed_m_s); yielded.add(selected)
    finally:
        if controller is not None and controller.active_main_vehicle in set(traci.vehicle.getIDList()): traci.vehicle.setSpeed(controller.active_main_vehicle, -1)
        traci.close()
    result = recorder.result(); steps = summarize_step_series(summary, duration); result.update(summarize_tripinfo(tripinfo, int(result["accounted_loaded_veh"])), **steps)
    result.update(strategy=strategy, main_veh_h=main_rate, ramp_veh_h=ramp_rate, seed=seed, unfinished_vehicles=max(0, int(steps["loaded_vehicles"]) - int(result["arrived_veh"])), throughput=int(result["arrived_veh"]) / duration, interventions=controller.interventions if controller else 0)
    return result


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output=[]
    for strategy in ("uncontrolled", "cooperative_limited"):
        selected=[r for r in rows if r["strategy"] == strategy]
        output.append({"strategy":strategy,"runs":len(selected),"mean_total_time_spent_s":mean(float(r["total_time_spent_s"]) for r in selected),"mean_network_time_spent_s":mean(float(r["network_time_spent_s"]) for r in selected),"mean_insertion_wait_time_s":mean(float(r["insertion_wait_time_s"]) for r in selected),"mean_main_total_time_spent_s":mean(float(r["main_total_time_spent_s"]) for r in selected),"mean_ramp_total_time_spent_s":mean(float(r["ramp_total_time_spent_s"]) for r in selected),"mean_unfinished_vehicles":mean(float(r["unfinished_vehicles"]) for r in selected),"mean_throughput_veh_h":mean(float(r["throughput"]) for r in selected)*3600,"breakdown_runs":sum(int(r["unfinished_vehicles"])>0 for r in selected),"collision_runs":sum(int(r["collisions"])>0 for r in selected),"teleport_runs":sum(int(r["teleports"])>0 for r in selected),"mean_interventions":mean(float(r["interventions"]) for r in selected)})
    return output


def run(seeds: list[int] = DEFAULT_SEEDS, duration: float = DEFAULT_DURATION_S, clearance: float = DEFAULT_CLEARANCE_TIME_S, output_dir: Path | None = None, fcd_output_dir: Path | None = None) -> Path:
    main_rate, ramp_rate = allocate_demand(DEFAULT_TOTAL_RATES[0], DEFAULT_DEMAND_RATIOS[0]); rows=[]
    for strategy in DEFAULT_STRATEGIES:
        for seed in seeds:
            row = run_case(strategy, main_rate, ramp_rate, duration, clearance, seed, fcd_output_dir)
            row.update(total_demand_veh_h=DEFAULT_TOTAL_RATES[0], demand_ratio=DEFAULT_DEMAND_RATIOS[0]); rows.append(row)
    result_dir=output_dir or STEP_DIR / "results"
    raw=write_rows(result_dir / "evaluation_raw.csv", [{field: row.get(field, 0) for field in RAW_FIELDS} for row in rows], RAW_FIELDS)
    write_rows(result_dir / "evaluation_summary.csv", summarize(rows), SUMMARY_FIELDS)
    write_rows(result_dir / "paired_confidence_summary.csv", paired_summary(rows), PAIRED_FIELDS)
    generate(result_dir / "evaluation_summary.csv", result_dir / "figures" / "complete_tts.svg")
    write_metadata(result_dir / "metadata.json", {"experiment_id":"highway_merge_v3_step05_evaluation","source_candidate":"step04 improvement_02","network":HIGHWAY_MERGE_V3.name,"seeds":seeds,"demand_duration_s":duration,"clearance_time_s":clearance,"tts_definition":"network occupancy integral + pending insertion vehicle integral", "fcd_output_dir": str(fcd_output_dir) if fcd_output_dir else None})
    return raw


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS))); parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S); parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME_S); parser.add_argument("--output-dir", type=Path); parser.add_argument("--fcd-output-dir", type=Path, default=GENERATED_OUTPUT_DIR / "trajectories" / "v3-step05"); args=parser.parse_args()
    print(run([int(x) for x in args.seeds.split(",")], args.duration, args.clearance_time, args.output_dir, args.fcd_output_dir))
