"""Compare fixed-interval ramp metering with v3 Step 5's paired baseline."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
STEP_DIR = Path(__file__).resolve().parent
STEP05_DIR = ROOT / "experiments/highway_merge_v3/step05_evaluation"
STEP04_DIR = ROOT / "experiments/highway_merge_v3/step04_cooperative_merge"
for path in (ROOT, ROOT / "src", STEP_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from analysis import paired_summary
from config import (DEFAULT_CLEARANCE_TIME_S, DEFAULT_DEMAND_RATIO, DEFAULT_DURATION_S, DEFAULT_SEEDS,
                    DEFAULT_STRATEGIES, DEFAULT_TOTAL_RATE, METER_INTERVALS_S, METER_STOP_POSITION_M)
from controller import FixedIntervalMeter
from experiments.common import write_metadata, write_rows
from metrics import CompleteTTSMetrics
from traffic_merge_sim.animate import save_animation, select_timesteps
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.metrics import summarize_step_series, summarize_tripinfo
from traffic_merge_sim.network_config import HIGHWAY_MERGE_V3
from traffic_merge_sim.paths import GENERATED_OUTPUT_DIR
from traffic_merge_sim.route_builder import build_case_route_file
from traffic_merge_sim.sumo_runner import locate_sumo_binary
from traffic_merge_sim.visualize import read_fcd_timesteps

RAW_FIELDS = ["strategy", "total_demand_veh_h", "demand_ratio", "seed", "main_veh_h", "ramp_veh_h", "meter_release_interval_s", "meter_releases", "network_time_spent_s", "insertion_wait_time_s", "total_time_spent_s", "main_total_time_spent_s", "ramp_total_time_spent_s", "main_insertion_wait_time_s", "ramp_insertion_wait_time_s", "unfinished_vehicles", "throughput", "peak_queue_vehicles", "collisions", "teleports", "interventions"]
SUMMARY_FIELDS = ["strategy", "runs", "mean_total_time_spent_s", "mean_network_time_spent_s", "mean_insertion_wait_time_s", "mean_main_total_time_spent_s", "mean_ramp_total_time_spent_s", "mean_unfinished_vehicles", "mean_throughput_veh_h", "breakdown_runs", "collision_runs", "teleport_runs", "mean_meter_releases"]
PAIRED_FIELDS = ["strategy", "metric", "paired_seeds", "mean_paired_delta", "ci_95_low", "ci_95_high", "lower_is_better", "interpretation"]


def _load_step05_run():
    """Load Step 5 independently, keeping its fixed cooperative implementation intact."""
    original_config = sys.modules.get("config")
    original_analysis = sys.modules.get("analysis")
    original_controller = sys.modules.get("controller")
    original_metrics = sys.modules.get("metrics")
    original_visualize = sys.modules.get("visualize")
    for name, path in (("step06_v3_step05_config", STEP04_DIR / "config.py"), ("step06_v3_step05_analysis", STEP05_DIR / "analysis.py")):
        spec = importlib.util.spec_from_file_location(name, path); assert spec and spec.loader
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
        if name.endswith("config"): step05_config = module
        else: step05_analysis = module
    def load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path); assert spec and spec.loader
        loaded = importlib.util.module_from_spec(spec); sys.modules[name] = loaded; spec.loader.exec_module(loaded)
        return loaded
    sys.modules["config"], sys.modules["analysis"] = step05_config, step05_analysis
    sys.modules["controller"] = load("step06_v3_step04_controller", STEP04_DIR / "controller.py")
    sys.modules["metrics"] = load("step06_v3_step05_metrics", STEP05_DIR / "metrics.py")
    sys.modules["visualize"] = load("step06_v3_step05_visualize", STEP05_DIR / "visualize.py")
    try:
        spec = importlib.util.spec_from_file_location("step06_v3_step05_run", STEP05_DIR / "run.py"); assert spec and spec.loader
        module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
        return module
    finally:
        if original_config is None: sys.modules.pop("config", None)
        else: sys.modules["config"] = original_config
        if original_analysis is None: sys.modules.pop("analysis", None)
        else: sys.modules["analysis"] = original_analysis
        if original_controller is None: sys.modules.pop("controller", None)
        else: sys.modules["controller"] = original_controller
        if original_metrics is None: sys.modules.pop("metrics", None)
        else: sys.modules["metrics"] = original_metrics
        if original_visualize is None: sys.modules.pop("visualize", None)
        else: sys.modules["visualize"] = original_visualize


STEP05_RUN = _load_step05_run()


def run_metered_case(strategy: str, main_rate: int, ramp_rate: int, duration: float, clearance: float, seed: int, fcd_path: Path | None = None) -> dict[str, object]:
    import traci
    interval = METER_INTERVALS_S[strategy]
    output_dir = GENERATED_OUTPUT_DIR / HIGHWAY_MERGE_V3.name; output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"v3_step06_{strategy}_main_{main_rate}_ramp_{ramp_rate}_seed_{seed}"
    route, tripinfo, summary = (output_dir / f"{prefix}{suffix}" for suffix in (".rou.xml", ".tripinfo.xml", ".summary.xml"))
    for path in (route, tripinfo, summary, fcd_path):
        if path is not None: path.unlink(missing_ok=True)
    if fcd_path is not None: fcd_path.parent.mkdir(parents=True, exist_ok=True)
    build_case_route_file(route, main_rate, ramp_rate, duration, network=HIGHWAY_MERGE_V3)
    command = [locate_sumo_binary(), "-n", str(HIGHWAY_MERGE_V3.network_path), "-r", str(route), "--no-step-log", "--quit-on-end", "--tripinfo-output", str(tripinfo), "--summary-output", str(summary), "--xml-validation", "never", "--time-to-teleport", "-1", "--end", str(duration + clearance), "--seed", str(seed)]
    if fcd_path is not None: command.extend(["--fcd-output", str(fcd_path)])
    recorder, meter, stopped = CompleteTTSMetrics(), FixedIntervalMeter(interval), set()
    traci.start(command)
    try:
        while traci.simulation.getTime() < duration + clearance:
            traci.simulationStep(); now = float(traci.simulation.getTime()); ids = set(traci.vehicle.getIDList())
            recorder.observe({vehicle: float(traci.vehicle.getSpeed(vehicle)) for vehicle in ids}, set(traci.simulation.getPendingVehicles()), set(traci.simulation.getLoadedIDList()), set(traci.simulation.getDepartedIDList()), set(traci.simulation.getArrivedIDList()), within_demand=now <= duration)
            positions = {vehicle: float(traci.vehicle.getLanePosition(vehicle)) for vehicle in traci.edge.getLastStepVehicleIDs("ramp_upstream")}
            # Stop only after the vehicle reaches the metering point.  A
            # scheduled stop ahead of every ramp vehicle can itself cap the
            # discharge rate, masking the configured interval.
            ready = {vehicle for vehicle, position in positions.items() if position >= METER_STOP_POSITION_M - 2.0}
            held, released = meter.update(now, positions, ready)
            for vehicle in (held & ready) - stopped:
                traci.vehicle.setSpeed(vehicle, 0); stopped.add(vehicle)
            if released in stopped and released in ids:
                traci.vehicle.setSpeed(released, -1); stopped.remove(released)
    finally:
        traci.close()
    result = recorder.result(); steps = summarize_step_series(summary, duration); result.update(summarize_tripinfo(tripinfo, int(result["accounted_loaded_veh"])), **steps)
    result.update(strategy=strategy, main_veh_h=main_rate, ramp_veh_h=ramp_rate, seed=seed, meter_release_interval_s=interval, meter_releases=meter.releases, unfinished_vehicles=max(0, int(steps["loaded_vehicles"]) - int(result["arrived_veh"])), throughput=int(result["arrived_veh"]) / duration, interventions=0)
    return result


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{"strategy": strategy, "runs": len(selected := [row for row in rows if row["strategy"] == strategy]), "mean_total_time_spent_s": mean(float(row["total_time_spent_s"]) for row in selected), "mean_network_time_spent_s": mean(float(row["network_time_spent_s"]) for row in selected), "mean_insertion_wait_time_s": mean(float(row["insertion_wait_time_s"]) for row in selected), "mean_main_total_time_spent_s": mean(float(row["main_total_time_spent_s"]) for row in selected), "mean_ramp_total_time_spent_s": mean(float(row["ramp_total_time_spent_s"]) for row in selected), "mean_unfinished_vehicles": mean(float(row["unfinished_vehicles"]) for row in selected), "mean_throughput_veh_h": mean(float(row["throughput"]) for row in selected) * 3600, "breakdown_runs": sum(int(row["unfinished_vehicles"]) > 0 for row in selected), "collision_runs": sum(int(row["collisions"]) > 0 for row in selected), "teleport_runs": sum(int(row["teleports"]) > 0 for row in selected), "mean_meter_releases": mean(float(row["meter_releases"]) for row in selected)} for strategy in sorted({str(row["strategy"]) for row in rows})]


def run(seeds: list[int] = DEFAULT_SEEDS, duration: float = DEFAULT_DURATION_S, clearance: float = DEFAULT_CLEARANCE_TIME_S, strategies: list[str] = DEFAULT_STRATEGIES, output_dir: Path | None = None, fcd_output_dir: Path | None = None, gif_output: Path | None = None, gif_end_time_s: float = 120.0) -> Path:
    if "uncontrolled" not in strategies or set(strategies) - set(DEFAULT_STRATEGIES): raise ValueError("strategies must be a subset of the Step 6 strategies and include uncontrolled")
    main_rate, ramp_rate = allocate_demand(DEFAULT_TOTAL_RATE, DEFAULT_DEMAND_RATIO); fcd_dir = fcd_output_dir or GENERATED_OUTPUT_DIR / "trajectories" / "v3-step06"; rows = []
    for strategy in strategies:
        for seed in seeds:
            save_fcd = strategy == "ramp_fixed_1s" and seed == seeds[0]
            fcd_path = fcd_dir / f"{strategy}_main_{main_rate}_ramp_{ramp_rate}_seed_{seed}.fcd.xml" if save_fcd else None
            row = run_metered_case(strategy, main_rate, ramp_rate, duration, clearance, seed, fcd_path) if strategy in METER_INTERVALS_S else STEP05_RUN.run_case(strategy, main_rate, ramp_rate, duration, clearance, seed, fcd_dir if save_fcd else None)
            row.update(total_demand_veh_h=DEFAULT_TOTAL_RATE, demand_ratio=DEFAULT_DEMAND_RATIO, meter_release_interval_s=METER_INTERVALS_S.get(strategy, 0.0), meter_releases=0 if strategy not in METER_INTERVALS_S else row["meter_releases"]); rows.append(row)
    result_dir = output_dir or STEP_DIR / "results"; raw = write_rows(result_dir / "ramp_metering_raw.csv", [{field: row.get(field, 0) for field in RAW_FIELDS} for row in rows], RAW_FIELDS); write_rows(result_dir / "ramp_metering_summary.csv", summarize(rows), SUMMARY_FIELDS); paired = paired_summary(rows); write_rows(result_dir / "paired_confidence_summary.csv", paired, PAIRED_FIELDS)
    if gif_output is not None:
        source = fcd_dir / f"ramp_fixed_1s_main_{main_rate}_ramp_{ramp_rate}_seed_{seeds[0]}.fcd.xml"; save_animation(HIGHWAY_MERGE_V3, select_timesteps(read_fcd_timesteps(source), 0, min(duration, gif_end_time_s), 1), gif_output, "gif", 10)
    write_metadata(result_dir / "metadata.json", {"experiment_id": "highway_merge_v3_step06_ramp_metering", "network": HIGHWAY_MERGE_V3.name, "strategies": strategies, "total_rate_veh_h": DEFAULT_TOTAL_RATE, "demand_ratio": DEFAULT_DEMAND_RATIO, "seeds": seeds, "demand_duration_s": duration, "clearance_time_s": clearance, "meter_stop_position_m": METER_STOP_POSITION_M, "meter_intervals_s": METER_INTERVALS_S, "fcd_output_dir": str(fcd_dir), "gif_output": str(gif_output) if gif_output else None, "animation_start_time_s": 0, "animation_end_time_s": min(duration, gif_end_time_s), "animation_frame_step": 1, "animation_fps": 10, "difference_definition": "strategy - uncontrolled for the same seed"})
    return raw


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--seeds", default=",".join(map(str, DEFAULT_SEEDS))); parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S); parser.add_argument("--clearance-time", type=float, default=DEFAULT_CLEARANCE_TIME_S); parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES)); parser.add_argument("--output-dir", type=Path); parser.add_argument("--fcd-output-dir", type=Path, default=GENERATED_OUTPUT_DIR / "trajectories" / "v3-step06"); parser.add_argument("--gif-output", type=Path, default=GENERATED_OUTPUT_DIR / "visualization" / "v3-step06-ramp-fixed-1s.gif"); parser.add_argument("--gif-end-time", type=float, default=120.0); args = parser.parse_args()
    print(run([int(item) for item in args.seeds.split(",")], args.duration, args.clearance_time, args.strategies.split(","), args.output_dir, args.fcd_output_dir, args.gif_output, args.gif_end_time))
