from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = Path(__file__).resolve().parent
STEP05_DIR = ROOT / "experiments" / "step05-02_insertion_wait_tts"
for path in (ROOT, ROOT / "src", STEP_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from analysis import compare_with_uncontrolled
from config import (DEFAULT_CLEARANCE_TIME, DEFAULT_DEMAND_RATIOS, DEFAULT_DURATION,
                    DEFAULT_SEEDS, DEFAULT_STRATEGIES, DEFAULT_TOTAL_RATES,
                    METER_INTERVALS_S, METER_STOP_POSITION_M)
from controller import FixedIntervalMeter
from experiments.common import write_metadata, write_rows
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.metrics import classify_state, estimate_generated_vehicles, summarize_step_series, summarize_tripinfo
from traffic_merge_sim.minimal_merge import RESULT_FIELDS
from traffic_merge_sim.paths import GENERATED_OUTPUT_DIR, NETWORK_PATH
from traffic_merge_sim.route_builder import build_case_route_file
from traffic_merge_sim.sumo_runner import locate_sumo_binary
from visualize import generate_charts


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(f"step06_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


step05_metrics = _load("complete_metrics", STEP05_DIR / "metrics.py")
step05_config = _load("step05_config", STEP05_DIR / "config.py")
_saved_config = sys.modules.get("config")
_saved_metrics = sys.modules.get("metrics")
sys.modules["config"] = step05_config
sys.modules["metrics"] = step05_metrics
try:
    step05_run = _load("step05_run", STEP05_DIR / "run.py")
finally:
    if _saved_config is None:
        sys.modules.pop("config", None)
    else:
        sys.modules["config"] = _saved_config
    if _saved_metrics is None:
        sys.modules.pop("metrics", None)
    else:
        sys.modules["metrics"] = _saved_metrics
CompleteTTSMetrics = step05_metrics.CompleteTTSMetrics

METER_FIELDS = ["meter_release_interval_s", "meter_releases"]
RAW_FIELDS = ["strategy", "demand_ratio", "total_demand_veh_h", *step05_run.CONTROL_FIELDS, *METER_FIELDS,
              *step05_run.EXTENDED_FIELDS, *RESULT_FIELDS]
PAIRED_FIELDS = ["strategy", "total_demand_veh_h", "demand_ratio", "seed", "metric", "lower_is_better",
                 "uncontrolled_value", "strategy_value", "paired_delta"]
CI_FIELDS = ["strategy", "total_demand_veh_h", "demand_ratio", "metric", "lower_is_better", "paired_seeds",
             "mean_paired_delta", "sample_stddev", "standard_error", "t_critical_95", "ci_95_low", "ci_95_high", "interpretation"]


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_ints(raw: str) -> list[int]:
    return [int(item) for item in parse_csv(raw)]


def run_metered_case(strategy: str, main_rate: int, side_rate: int, duration: float,
                     clearance_time: float, seed: int) -> dict[str, object]:
    import traci

    interval = METER_INTERVALS_S[strategy]
    simulation_end = duration + clearance_time
    GENERATED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    case = f"step06_{strategy}_main_{main_rate}_side_{side_rate}_seed_{seed}"
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
    meter = FixedIntervalMeter(interval)
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
            side_ids = traci.edge.getLastStepVehicleIDs("side_in")
            positions = {vehicle_id: float(traci.vehicle.getLanePosition(vehicle_id)) for vehicle_id in side_ids}
            ready = {vehicle_id for vehicle_id, position in positions.items() if position >= METER_STOP_POSITION_M - 0.2}
            held, released = meter.update(now_s, positions, ready)
            for vehicle_id in held - stopped:
                traci.vehicle.setStop(vehicle_id, "side_in", pos=METER_STOP_POSITION_M, laneIndex=0)
                stopped.add(vehicle_id)
            if released in stopped and released in ids:
                # duration=0 removes both a reached stop and a stop that is
                # still scheduled ahead of the vehicle. ``resume`` only works
                # after the stop has physically been reached.
                traci.vehicle.setStop(released, "side_in", pos=METER_STOP_POSITION_M, laneIndex=0, duration=0)
                stopped.remove(released)
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
                   clearance_time_s=float(clearance_time), simulation_end_s=float(simulation_end), strategy=strategy)
    metrics["throughput"] = int(metrics["arrived_veh"]) / duration if duration else 0.0
    metrics["queue_length"] = step_metrics["final_running_vehicles"] + step_metrics["final_waiting_vehicles"]
    metrics["state"] = classify_state(int(metrics["unfinished_vehicles"]), step_metrics["peak_queue_vehicles"])
    metrics.update(interventions=0, successful_releases=0, timed_out_interventions=0,
                   yielded_main_vehicles=0, side_merges_after_intervention=0)
    metrics.update(meter_release_interval_s=interval, meter_releases=meter.releases)
    return metrics


def run(total_rates: list[int], ratios: list[str], strategies: list[str], duration: float,
        clearance_time: float, seeds: list[int], output_dir: Path | None = None) -> Path:
    unknown = set(strategies) - {"uncontrolled", "cooperative_limited", *METER_INTERVALS_S}
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
                    if strategy in METER_INTERVALS_S:
                        row = run_metered_case(strategy, main_rate, side_rate, duration, clearance_time, seed)
                    else:
                        row = step05_run.run_case(strategy, main_rate, side_rate, duration, clearance_time, seed)
                        row.update(meter_release_interval_s=0.0, meter_releases=0)
                    row.update(demand_ratio=ratio, total_demand_veh_h=total)
                    rows.append(row)
    paired, confidence = compare_with_uncontrolled(rows)
    results = output_dir or STEP_DIR / "results"
    raw_path = write_rows(results / "ramp_metering_raw.csv", rows, RAW_FIELDS)
    paired_path = write_rows(results / "paired_differences.csv", paired, PAIRED_FIELDS)
    ci_path = write_rows(results / "paired_confidence_summary.csv", confidence, CI_FIELDS)
    charts = generate_charts(paired, confidence, results / "figures")
    write_metadata(results / "metadata.json", {"experiment_id": "step06_ramp_metering", "script": "experiments/step06_ramp_metering/run.py",
        "raw_csv": raw_path.name, "paired_csv": paired_path.name, "confidence_csv": ci_path.name,
        "figures": [str(path.relative_to(results)) for path in charts], "strategies": strategies,
        "total_rates": total_rates, "demand_ratios": ratios, "seeds": seeds, "demand_duration_s": duration,
        "clearance_time_s": clearance_time, "meter_stop_position_m": METER_STOP_POSITION_M,
        "meter_intervals_s": METER_INTERVALS_S, "difference_definition": "strategy - uncontrolled for the same condition and seed"})
    return raw_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Step 6 fixed-interval ramp metering comparison.")
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
