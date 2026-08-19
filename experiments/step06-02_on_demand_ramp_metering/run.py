from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = Path(__file__).resolve().parent
STEP06_DIR = ROOT / "experiments" / "step06_ramp_metering"
for path in (ROOT, ROOT / "src", STEP_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config import (ACTIVATION_PERSISTENCE_S, ACTIVATION_SPEED_M_S, CONTROL_ENTRY_POSITION_M, DEFAULT_CLEARANCE_TIME,
                    DEFAULT_DEMAND_RATIOS, DEFAULT_DURATION, DEFAULT_SEEDS, DEFAULT_STRATEGIES,
                    DEFAULT_TOTAL_RATES, METER_STOP_POSITION_M, MIN_ACTIVE_TIME_S,
                    MIN_MAIN_VEHICLES, RECOVERY_PERSISTENCE_S, RECOVERY_SPEED_M_S,
                    RELEASE_INTERVAL_S)
from controller import OnDemandRampMeter, OnDemandSettings
from experiments.common import write_metadata, write_rows
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.metrics import classify_state, estimate_generated_vehicles, summarize_step_series, summarize_tripinfo
from traffic_merge_sim.minimal_merge import RESULT_FIELDS
from traffic_merge_sim.paths import GENERATED_OUTPUT_DIR, NETWORK_PATH
from traffic_merge_sim.route_builder import build_case_route_file
from traffic_merge_sim.sumo_runner import locate_sumo_binary


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(f"step06_02_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


step06_config = _load("step06_config", STEP06_DIR / "config.py")
step06_controller = _load("step06_controller", STEP06_DIR / "controller.py")
step06_analysis = _load("step06_analysis", STEP06_DIR / "analysis.py")
step06_visualize = _load("step06_visualize", STEP06_DIR / "visualize.py")
_aliases = {name: sys.modules.get(name) for name in ("config", "controller", "analysis", "visualize")}
sys.modules.update(config=step06_config, controller=step06_controller,
                   analysis=step06_analysis, visualize=step06_visualize)
try:
    step06_run = _load("step06_run", STEP06_DIR / "run.py")
finally:
    for name, module in _aliases.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module

CompleteTTSMetrics = step06_run.CompleteTTSMetrics
SETTINGS = OnDemandSettings(
    release_interval_s=RELEASE_INTERVAL_S,
    min_main_vehicles=MIN_MAIN_VEHICLES,
    activation_speed_m_s=ACTIVATION_SPEED_M_S,
    recovery_speed_m_s=RECOVERY_SPEED_M_S,
    activation_persistence_s=ACTIVATION_PERSISTENCE_S,
    recovery_persistence_s=RECOVERY_PERSISTENCE_S,
    min_active_time_s=MIN_ACTIVE_TIME_S,
)
DEMAND_FIELDS = ["meter_activations", "meter_active_time_s", "meter_active_share", "meter_releases"]
RAW_FIELDS = ["strategy", "demand_ratio", "total_demand_veh_h", *step06_run.step05_run.CONTROL_FIELDS,
              "meter_release_interval_s", *DEMAND_FIELDS,
              *step06_run.step05_run.EXTENDED_FIELDS, *RESULT_FIELDS]
PAIRED_FIELDS = step06_run.PAIRED_FIELDS
CI_FIELDS = step06_run.CI_FIELDS


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_ints(raw: str) -> list[int]:
    return [int(item) for item in parse_csv(raw)]


def run_on_demand_case(main_rate: int, side_rate: int, duration: float,
                       clearance_time: float, seed: int) -> dict[str, object]:
    import traci

    simulation_end = duration + clearance_time
    GENERATED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    case = f"step06_02_on_demand_main_{main_rate}_side_{side_rate}_seed_{seed}"
    route_path = GENERATED_OUTPUT_DIR / f"{case}.rou.xml"
    tripinfo_path = GENERATED_OUTPUT_DIR / f"{case}.tripinfo.xml"
    summary_path = GENERATED_OUTPUT_DIR / f"{case}.summary.xml"
    for path in (route_path, tripinfo_path, summary_path):
        path.unlink(missing_ok=True)
    build_case_route_file(route_path, main_rate, side_rate, duration)
    command = [locate_sumo_binary(), "-n", str(NETWORK_PATH), "-r", str(route_path), "--no-step-log",
               "--quit-on-end", "--tripinfo-output", str(tripinfo_path), "--summary-output", str(summary_path),
               "--xml-validation", "never", "--time-to-teleport", "-1", "--end", str(simulation_end), "--seed", str(seed)]
    recorder = CompleteTTSMetrics()
    meter = OnDemandRampMeter(SETTINGS)
    stopped: set[str] = set()
    traci.start(command)
    try:
        while traci.simulation.getTime() < simulation_end:
            traci.simulationStep()
            now_s = float(traci.simulation.getTime())
            ids = set(traci.vehicle.getIDList())
            recorder.observe({vehicle_id: float(traci.vehicle.getSpeed(vehicle_id)) for vehicle_id in ids},
                             set(traci.simulation.getPendingVehicles()), set(traci.simulation.getLoadedIDList()),
                             set(traci.simulation.getDepartedIDList()), set(traci.simulation.getArrivedIDList()),
                             within_demand=now_s <= duration)
            main_speeds = [float(traci.vehicle.getSpeed(vehicle_id))
                           for vehicle_id in traci.lane.getLastStepVehicleIDs("main_in_0")]
            side_positions = {
                vehicle_id: float(traci.vehicle.getLanePosition(vehicle_id))
                for vehicle_id in traci.edge.getLastStepVehicleIDs("side_in")
                if float(traci.vehicle.getLanePosition(vehicle_id)) < METER_STOP_POSITION_M + 0.2
            }
            ready = {vehicle_id for vehicle_id, position in side_positions.items()
                     if position >= METER_STOP_POSITION_M - 0.2}
            eligible = {vehicle_id for vehicle_id, position in side_positions.items()
                        if position <= CONTROL_ENTRY_POSITION_M}
            held, released = meter.update(now_s, main_speeds, side_positions, ready, eligible)
            for vehicle_id in held - stopped:
                traci.vehicle.setStop(vehicle_id, "side_in", pos=METER_STOP_POSITION_M, laneIndex=0)
                stopped.add(vehicle_id)
            for vehicle_id in released & stopped & ids:
                traci.vehicle.setStop(vehicle_id, "side_in", pos=METER_STOP_POSITION_M,
                                      laneIndex=0, duration=0)
                stopped.remove(vehicle_id)
    finally:
        traci.close()

    expected = estimate_generated_vehicles(main_rate, side_rate, duration)
    metrics: dict[str, object] = summarize_tripinfo(tripinfo_path, expected)
    step_metrics = summarize_step_series(summary_path, duration)
    metrics.update(step_metrics)
    metrics.update(recorder.result())
    metrics.update(expected_generated_veh=expected, generated_veh=step_metrics["loaded_vehicles"])
    metrics["unfinished_vehicles"] = max(0, step_metrics["loaded_vehicles"] - int(metrics["arrived_veh"]))
    metrics["loaded_reconciliation_error_veh"] = int(metrics["accounted_loaded_veh"]) - int(metrics["loaded_vehicles"])
    metrics.update(main_veh_h=main_rate, side_veh_h=side_rate, seed=seed, duration_s=float(duration),
                   clearance_time_s=float(clearance_time), simulation_end_s=float(simulation_end),
                   strategy="ramp_on_demand_4s")
    metrics["throughput"] = int(metrics["arrived_veh"]) / duration if duration else 0.0
    metrics["queue_length"] = step_metrics["final_running_vehicles"] + step_metrics["final_waiting_vehicles"]
    metrics["state"] = classify_state(int(metrics["unfinished_vehicles"]), step_metrics["peak_queue_vehicles"])
    metrics.update(interventions=0, successful_releases=0, timed_out_interventions=0,
                   yielded_main_vehicles=0, side_merges_after_intervention=0,
                   meter_release_interval_s=RELEASE_INTERVAL_S, meter_activations=meter.activations,
                   meter_active_time_s=meter.active_time_s,
                   meter_active_share=meter.active_time_s / simulation_end if simulation_end else 0.0,
                   meter_releases=meter.releases)
    return metrics


def _meter_defaults(row: dict[str, object]) -> None:
    row.setdefault("meter_release_interval_s", 0.0)
    row.setdefault("meter_activations", 0)
    row.setdefault("meter_active_time_s", 0.0)
    row.setdefault("meter_active_share", 0.0)
    row.setdefault("meter_releases", 0)


def run(total_rates: list[int], ratios: list[str], strategies: list[str], duration: float,
        clearance_time: float, seeds: list[int], output_dir: Path | None = None) -> Path:
    allowed = {"uncontrolled", "cooperative_limited", "ramp_fixed_4s", "ramp_on_demand_4s"}
    unknown = set(strategies) - allowed
    if unknown:
        raise ValueError(f"Unknown strategies: {sorted(unknown)}")
    if "uncontrolled" not in strategies:
        raise ValueError("uncontrolled is required as the paired baseline")
    rows: list[dict[str, object]] = []
    for total in total_rates:
        for ratio in ratios:
            main_rate, side_rate = allocate_demand(total, ratio)
            for strategy in strategies:
                for seed in seeds:
                    if strategy == "ramp_on_demand_4s":
                        row = run_on_demand_case(main_rate, side_rate, duration, clearance_time, seed)
                    elif strategy == "ramp_fixed_4s":
                        row = step06_run.run_metered_case(strategy, main_rate, side_rate, duration, clearance_time, seed)
                    else:
                        row = step06_run.step05_run.run_case(strategy, main_rate, side_rate, duration, clearance_time, seed)
                    _meter_defaults(row)
                    row.update(demand_ratio=ratio, total_demand_veh_h=total)
                    rows.append(row)
    paired, confidence = step06_analysis.compare_with_uncontrolled(rows)
    results = output_dir or STEP_DIR / "results"
    raw_path = write_rows(results / "on_demand_raw.csv", rows, RAW_FIELDS)
    paired_path = write_rows(results / "paired_differences.csv", paired, PAIRED_FIELDS)
    ci_path = write_rows(results / "paired_confidence_summary.csv", confidence, CI_FIELDS)
    charts = step06_visualize.generate_charts(paired, confidence, results / "figures")
    write_metadata(results / "metadata.json", {"experiment_id": "step06_02_on_demand_ramp_metering",
        "script": "experiments/step06-02_on_demand_ramp_metering/run.py", "raw_csv": raw_path.name,
        "paired_csv": paired_path.name, "confidence_csv": ci_path.name,
        "figures": [str(path.relative_to(results)) for path in charts], "strategies": strategies,
        "total_rates": total_rates, "demand_ratios": ratios, "seeds": seeds,
        "demand_duration_s": duration, "clearance_time_s": clearance_time,
        "meter_stop_position_m": METER_STOP_POSITION_M,
        "control_entry_position_m": CONTROL_ENTRY_POSITION_M, "on_demand_settings": SETTINGS.__dict__,
        "congestion_signal": "mean speed and vehicle count on main_in_0 with persistence and hysteresis",
        "difference_definition": "strategy - uncontrolled for the same condition and seed"})
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Step 6-2 congestion-activated 4-second ramp metering.")
    parser.add_argument("--total-rates", default=",".join(map(str, DEFAULT_TOTAL_RATES)))
    parser.add_argument("--demand-ratios", default=",".join(DEFAULT_DEMAND_RATIOS))
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME)
    parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS)))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(parse_ints(args.total_rates), parse_csv(args.demand_ratios), parse_csv(args.strategies),
        args.duration, args.clearance_time, parse_ints(args.seeds), args.output_dir)
