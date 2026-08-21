from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .metrics import classify_state, estimate_generated_vehicles, summarize_step_series, summarize_tripinfo
from .network_config import MINIMAL_MERGE, MergeNetworkConfig
from .paths import GENERATED_OUTPUT_DIR
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
    fcd_output_path: Path | None = None,
    network: MergeNetworkConfig = MINIMAL_MERGE,
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
    case_name = f"{network.name}_main_{main_veh_h}_side_{side_veh_h}_seed_{seed_suffix}"
    output_dir = GENERATED_OUTPUT_DIR / network.name
    output_dir.mkdir(parents=True, exist_ok=True)
    route_path = output_dir / f"{case_name}.rou.xml"
    tripinfo_path = output_dir / f"{case_name}.tripinfo.xml"
    summary_path = output_dir / f"{case_name}.summary.xml"
    for path in (route_path, tripinfo_path, summary_path, fcd_output_path):
        if path is None:
            continue
        path.unlink(missing_ok=True)

    build_case_route_file(route_path, main_veh_h, side_veh_h, demand_duration, network=network)
    command = [
        locate_sumo_binary(), "-n", str(network.network_path), "-r", str(route_path),
        "--no-step-log", "--quit-on-end", "--tripinfo-output", str(tripinfo_path),
        "--summary-output", str(summary_path), "--xml-validation", "never",
        "--time-to-teleport", "-1", "--end", str(simulation_end),
    ]
    if fcd_output_path is not None:
        fcd_output_path.parent.mkdir(parents=True, exist_ok=True)
        command.extend(["--fcd-output", str(fcd_output_path)])
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
