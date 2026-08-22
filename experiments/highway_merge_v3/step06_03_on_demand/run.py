"""Run Step 6-3 on-demand metering at the validated 0.25 s time resolution."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
STEP_DIR = Path(__file__).resolve().parent
STEP06_DIR = ROOT / "experiments/highway_merge_v3/step06_ramp_metering"
for path in (ROOT, ROOT / "src", STEP_DIR):
    if str(path) not in sys.path: sys.path.insert(0, str(path))

from controller import OnDemandMeter
from experiments.common import write_metadata, write_rows
from traffic_merge_sim.animate import save_animation, select_timesteps
from traffic_merge_sim.demand import allocate_demand
from traffic_merge_sim.metrics import summarize_step_series, summarize_tripinfo
from traffic_merge_sim.network_config import HIGHWAY_MERGE_V3
from traffic_merge_sim.paths import GENERATED_OUTPUT_DIR
from traffic_merge_sim.route_builder import build_case_route_file
from traffic_merge_sim.sumo_runner import locate_sumo_binary
from traffic_merge_sim.visualize import read_fcd_timesteps

sys.modules.pop("controller", None)
spec = importlib.util.spec_from_file_location("v3_step06_base", STEP06_DIR / "run.py"); assert spec and spec.loader
base = importlib.util.module_from_spec(spec); sys.modules[spec.name] = base; spec.loader.exec_module(base)
TOTAL_RATE, RATIO, SEEDS, STEP_LENGTH = 3950, "1:2", [7, 42, 99, 123, 2026], .25
STRATEGIES = ["uncontrolled", "cooperative_limited", "ramp_fixed_1_5s", "ramp_on_demand_1_5s"]
RAW_FIELDS = [*base.RAW_FIELDS, "meter_activations", "meter_active_time_s", "meter_active_share"]
SUMMARY_FIELDS = [*base.SUMMARY_FIELDS, "mean_meter_activations", "mean_meter_active_share"]


def on_demand_case(main_rate: int, ramp_rate: int, duration: float, clearance: float, seed: int, fcd_path: Path | None) -> dict[str, object]:
    import traci
    prefix = f"v3_step06_03_on_demand_main_{main_rate}_ramp_{ramp_rate}_seed_{seed}"
    out = GENERATED_OUTPUT_DIR / HIGHWAY_MERGE_V3.name; out.mkdir(parents=True, exist_ok=True)
    route, tripinfo, summary = (out / f"{prefix}{suffix}" for suffix in (".rou.xml", ".tripinfo.xml", ".summary.xml"))
    for path in (route, tripinfo, summary, fcd_path):
        if path is not None: path.unlink(missing_ok=True)
    if fcd_path is not None: fcd_path.parent.mkdir(parents=True, exist_ok=True)
    build_case_route_file(route, main_rate, ramp_rate, duration, network=HIGHWAY_MERGE_V3)
    command = [locate_sumo_binary(), "-n", str(HIGHWAY_MERGE_V3.network_path), "-r", str(route), "--no-step-log", "--quit-on-end", "--tripinfo-output", str(tripinfo), "--summary-output", str(summary), "--xml-validation", "never", "--time-to-teleport", "-1", "--step-length", str(STEP_LENGTH), "--end", str(duration + clearance), "--seed", str(seed)]
    if fcd_path is not None: command.extend(["--fcd-output", str(fcd_path)])
    recorder, meter, stopped = base.CompleteTTSMetrics(), OnDemandMeter(), set(); traci.start(command)
    try:
        while traci.simulation.getTime() < duration + clearance:
            traci.simulationStep(); now = float(traci.simulation.getTime()); ids = set(traci.vehicle.getIDList())
            recorder.observe({item: float(traci.vehicle.getSpeed(item)) for item in ids}, set(traci.simulation.getPendingVehicles()), set(traci.simulation.getLoadedIDList()), set(traci.simulation.getDepartedIDList()), set(traci.simulation.getArrivedIDList()), within_demand=now <= duration, step_length_s=STEP_LENGTH)
            positions = {item: float(traci.vehicle.getLanePosition(item)) for item in traci.edge.getLastStepVehicleIDs("ramp_upstream")}
            ready = {item for item, pos in positions.items() if pos >= 398.0}
            speeds = [float(traci.vehicle.getSpeed(item)) for item in traci.lane.getLastStepVehicleIDs("main_merge_1")]
            held, released = meter.update(now, speeds, positions, ready)
            for item in (held & ready) - stopped: traci.vehicle.setSpeed(item, 0); stopped.add(item)
            for item in released & stopped & ids: traci.vehicle.setSpeed(item, -1); stopped.remove(item)
    finally: traci.close()
    result = recorder.result(); steps = summarize_step_series(summary, duration); result.update(summarize_tripinfo(tripinfo, int(result["accounted_loaded_veh"])), **steps)
    result.update(strategy="ramp_on_demand_1_5s", main_veh_h=main_rate, ramp_veh_h=ramp_rate, seed=seed, meter_release_interval_s=1.5, meter_releases=meter.releases, meter_activations=meter.activations, meter_active_time_s=meter.active_time_s, meter_active_share=meter.active_time_s / (duration + clearance), unfinished_vehicles=max(0, int(steps["loaded_vehicles"]) - int(result["arrived_veh"])), throughput=int(result["arrived_veh"]) / duration, interventions=0)
    return result


def run(output_dir: Path | None = None, fcd_dir: Path | None = None, gif_output: Path | None = None) -> Path:
    main, ramp = allocate_demand(TOTAL_RATE, RATIO); fcd_dir = fcd_dir or GENERATED_OUTPUT_DIR / "trajectories/v3-step06-03"; rows = []
    for strategy in STRATEGIES:
        for seed in SEEDS:
            fcd = fcd_dir / f"{strategy}_main_{main}_ramp_{ramp}_seed_{seed}.fcd.xml" if strategy == "ramp_on_demand_1_5s" and seed == SEEDS[0] else None
            if strategy == "ramp_on_demand_1_5s": row = on_demand_case(main, ramp, 1800, 600, seed, fcd)
            elif strategy == "ramp_fixed_1_5s": row = base.run_metered_case(strategy, main, ramp, 1800, 600, seed, fcd, STEP_LENGTH)
            else: row = base.STEP05_RUN.run_case(strategy, main, ramp, 1800, 600, seed, None, STEP_LENGTH)
            row.update(total_demand_veh_h=TOTAL_RATE, demand_ratio=RATIO); row.setdefault("meter_releases", 0); row.setdefault("meter_activations", 0); row.setdefault("meter_active_time_s", 0.0); row.setdefault("meter_active_share", 0.0); rows.append(row)
    results = output_dir or STEP_DIR / "results"; raw = write_rows(results / "on_demand_raw.csv", [{field: row.get(field, 0) for field in RAW_FIELDS} for row in rows], RAW_FIELDS)
    summary=[]
    for strategy in STRATEGIES:
        selected=[row for row in rows if row["strategy"] == strategy]; aggregate={"strategy":strategy,"runs":len(selected),"mean_total_time_spent_s":mean(float(row["total_time_spent_s"]) for row in selected),"mean_network_time_spent_s":mean(float(row["network_time_spent_s"]) for row in selected),"mean_insertion_wait_time_s":mean(float(row["insertion_wait_time_s"]) for row in selected),"mean_main_total_time_spent_s":mean(float(row["main_total_time_spent_s"]) for row in selected),"mean_ramp_total_time_spent_s":mean(float(row["ramp_total_time_spent_s"]) for row in selected),"mean_unfinished_vehicles":mean(float(row["unfinished_vehicles"]) for row in selected),"mean_throughput_veh_h":mean(float(row["throughput"]) for row in selected)*3600,"breakdown_runs":sum(int(row["unfinished_vehicles"])>0 for row in selected),"collision_runs":sum(int(row["collisions"])>0 for row in selected),"teleport_runs":sum(int(row["teleports"])>0 for row in selected),"mean_meter_releases":mean(float(row["meter_releases"]) for row in selected),"mean_meter_activations":mean(float(row["meter_activations"]) for row in selected),"mean_meter_active_share":mean(float(row["meter_active_share"]) for row in selected)}; summary.append(aggregate)
    write_rows(results / "on_demand_summary.csv", summary, SUMMARY_FIELDS); paired=base.paired_summary(rows); write_rows(results / "paired_confidence_summary.csv", paired, base.PAIRED_FIELDS)
    if gif_output is not None:
        source=fcd_dir / f"ramp_on_demand_1_5s_main_{main}_ramp_{ramp}_seed_{SEEDS[0]}.fcd.xml"; save_animation(HIGHWAY_MERGE_V3, select_timesteps(read_fcd_timesteps(source), 0, 30, 1), gif_output, "gif", 10)
    write_metadata(results / "metadata.json", {"experiment_id":"highway_merge_v3_step06_03_on_demand","step_length_s":STEP_LENGTH,"strategies":STRATEGIES,"seeds":SEEDS,"on_demand_settings":{"interval_s":1.5,"activation_speed_m_s":27.0,"recovery_speed_m_s":29.0,"activation_persistence_s":3.0,"recovery_persistence_s":10.0,"min_active_s":30.0},"fcd_representative_only":True,"animation_frame_step":1,"animation_fps":10})
    return raw


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--output-dir",type=Path); parser.add_argument("--fcd-output-dir",type=Path); parser.add_argument("--gif-output",type=Path,default=GENERATED_OUTPUT_DIR / "visualization/v3-step06-03-on-demand.gif"); args=parser.parse_args(); print(run(args.output_dir,args.fcd_output_dir,args.gif_output))
