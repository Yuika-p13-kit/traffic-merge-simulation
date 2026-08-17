from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .metrics import classify_state, estimate_generated_vehicles, summarize_step_series, summarize_tripinfo
from .fixed_control import FixedRatioController, parse_strategy
from .paths import FIXED_CONTROL_NETWORK_PATH, GENERATED_OUTPUT_DIR, NETWORK_PATH
from .route_builder import build_case_route_file

DEFAULT_SUMO_HOME = Path("/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO")
os.environ.setdefault("SUMO_HOME", str(DEFAULT_SUMO_HOME))


def locate_sumo_binary() -> str:
    configured_home = Path(os.environ["SUMO_HOME"])
    for candidate in (shutil.which("sumo"), str(configured_home / "bin" / "sumo")):
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("SUMO binary not found. Install SUMO and ensure 'sumo' is on PATH.")


def run_single_case(
    main_veh_h: int | None = None, side_veh_h: int | None = None, end_time: float | None = None,
    *, q_main: int | None = None, q_side: int | None = None,
    duration: float | None = None, seed: int | None = None,
    clearance_time: float = 0.0,
) -> dict[str, float | int | str | None]:
    main_veh_h = q_main if q_main is not None else main_veh_h
    side_veh_h = q_side if q_side is not None else side_veh_h
    end_time = duration if duration is not None else end_time
    if main_veh_h is None or side_veh_h is None:
        raise ValueError("main_veh_h/q_main and side_veh_h/q_side must be provided.")
    demand_duration = 1200.0 if end_time is None else end_time
    simulation_end = demand_duration + clearance_time

    GENERATED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    seed_suffix = "none" if seed is None else str(seed)
    case_name = f"main_{main_veh_h}_side_{side_veh_h}_seed_{seed_suffix}"
    route_path = GENERATED_OUTPUT_DIR / f"{case_name}.rou.xml"
    tripinfo_path = GENERATED_OUTPUT_DIR / f"{case_name}.tripinfo.xml"
    summary_path = GENERATED_OUTPUT_DIR / f"{case_name}.summary.xml"
    for path in (route_path, tripinfo_path, summary_path):
        path.unlink(missing_ok=True)

    build_case_route_file(route_path, main_veh_h, side_veh_h, demand_duration)
    command = [
        locate_sumo_binary(), "-n", str(NETWORK_PATH), "-r", str(route_path),
        "--no-step-log", "--quit-on-end", "--tripinfo-output", str(tripinfo_path),
        "--summary-output", str(summary_path), "--xml-validation", "never",
        "--time-to-teleport", "-1", "--end", str(simulation_end),
    ]
    if seed is not None:
        command.extend(["--seed", str(seed)])
    subprocess.run(command, check=True)

    expected = estimate_generated_vehicles(main_veh_h, side_veh_h, demand_duration)
    metrics = summarize_tripinfo(tripinfo_path, expected)
    step_metrics = summarize_step_series(summary_path, demand_duration)
    metrics.update(step_metrics)
    metrics["expected_generated_veh"] = expected
    metrics["generated_veh"] = step_metrics["loaded_vehicles"]
    metrics["unfinished_vehicles"] = max(0, step_metrics["loaded_vehicles"] - int(metrics["arrived_veh"]))
    metrics.update(
        main_veh_h=main_veh_h, side_veh_h=side_veh_h, seed=seed,
        duration_s=float(demand_duration), clearance_time_s=float(clearance_time),
        simulation_end_s=float(simulation_end),
    )
    metrics["throughput"] = metrics["arrived_veh"] / demand_duration if demand_duration else 0.0
    metrics["queue_length"] = step_metrics["final_running_vehicles"] + step_metrics["final_waiting_vehicles"]
    metrics["state"] = classify_state(int(metrics["unfinished_vehicles"]), step_metrics["peak_queue_vehicles"])
    return metrics


def run_fixed_control_case(
    main_veh_h: int, side_veh_h: int, strategy: str, duration: float,
    clearance_time: float, seed: int,
) -> dict[str, float | int | str | None]:
    """Run a vehicle-count fixed-ratio merge using a dedicated TLS network."""
    import traci

    main_quota, side_quota = parse_strategy(strategy)
    simulation_end = duration + clearance_time
    GENERATED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_strategy = strategy.replace(":", "to")
    case_name = f"fixed_{safe_strategy}_main_{main_veh_h}_side_{side_veh_h}_seed_{seed}"
    route_path = GENERATED_OUTPUT_DIR / f"{case_name}.rou.xml"
    tripinfo_path = GENERATED_OUTPUT_DIR / f"{case_name}.tripinfo.xml"
    summary_path = GENERATED_OUTPUT_DIR / f"{case_name}.summary.xml"
    for path in (route_path, tripinfo_path, summary_path):
        path.unlink(missing_ok=True)
    build_case_route_file(route_path, main_veh_h, side_veh_h, duration)

    command = [
        locate_sumo_binary(), "-n", str(FIXED_CONTROL_NETWORK_PATH), "-r", str(route_path),
        "--no-step-log", "--quit-on-end", "--tripinfo-output", str(tripinfo_path),
        "--summary-output", str(summary_path), "--xml-validation", "never",
        "--time-to-teleport", "-1", "--end", str(simulation_end), "--seed", str(seed),
    ]
    controller = FixedRatioController(main_quota, side_quota)
    previous_out: set[str] = set()
    last_active = controller.active
    traci.start(command)
    try:
        traci.trafficlight.setRedYellowGreenState("merge", controller.signal_state)
        while traci.simulation.getTime() < simulation_end:
            traci.simulationStep()
            current_out = set(traci.edge.getLastStepVehicleIDs("out"))
            newly_passed = current_out - previous_out
            main_present = bool(traci.edge.getLastStepVehicleNumber("main_in"))
            side_present = bool(traci.edge.getLastStepVehicleNumber("side_in"))
            state = controller.signal_state
            if not newly_passed:
                state = controller.update(None, main_present, side_present)
            for vehicle_id in sorted(newly_passed):
                passed_approach = "main" if vehicle_id.startswith("main_flow") else "side"
                state = controller.update(passed_approach, main_present, side_present)
            if controller.active != last_active:
                state = "rr"  # One simulation step of all-red between conflicting approaches.
                last_active = controller.active
            traci.trafficlight.setRedYellowGreenState("merge", state)
            previous_out = current_out
    finally:
        traci.close()

    expected = estimate_generated_vehicles(main_veh_h, side_veh_h, duration)
    metrics = summarize_tripinfo(tripinfo_path, expected)
    step_metrics = summarize_step_series(summary_path, duration)
    metrics.update(step_metrics)
    metrics["expected_generated_veh"] = expected
    metrics["generated_veh"] = step_metrics["loaded_vehicles"]
    metrics["unfinished_vehicles"] = max(0, step_metrics["loaded_vehicles"] - int(metrics["arrived_veh"]))
    metrics.update(
        main_veh_h=main_veh_h, side_veh_h=side_veh_h, seed=seed,
        duration_s=float(duration), clearance_time_s=float(clearance_time),
        simulation_end_s=float(simulation_end), strategy=strategy,
    )
    metrics["throughput"] = metrics["arrived_veh"] / duration if duration else 0.0
    metrics["queue_length"] = step_metrics["final_running_vehicles"] + step_metrics["final_waiting_vehicles"]
    metrics["state"] = classify_state(int(metrics["unfinished_vehicles"]), step_metrics["peak_queue_vehicles"])
    return metrics
