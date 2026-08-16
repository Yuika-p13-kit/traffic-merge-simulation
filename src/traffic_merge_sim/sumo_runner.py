from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .metrics import estimate_generated_vehicles, summarize_tripinfo
from .paths import GENERATED_OUTPUT_DIR, NETWORK_PATH
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
) -> dict[str, float | int | str | None]:
    main_veh_h = q_main if q_main is not None else main_veh_h
    side_veh_h = q_side if q_side is not None else side_veh_h
    end_time = duration if duration is not None else end_time
    if main_veh_h is None or side_veh_h is None:
        raise ValueError("main_veh_h/q_main and side_veh_h/q_side must be provided.")
    end_time = 1200.0 if end_time is None else end_time

    GENERATED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    case_name = f"main_{main_veh_h}_side_{side_veh_h}"
    route_path = GENERATED_OUTPUT_DIR / f"{case_name}.rou.xml"
    tripinfo_path = GENERATED_OUTPUT_DIR / f"{case_name}.tripinfo.xml"
    summary_path = GENERATED_OUTPUT_DIR / f"{case_name}.summary.xml"
    for path in (route_path, tripinfo_path, summary_path):
        path.unlink(missing_ok=True)

    build_case_route_file(route_path, main_veh_h, side_veh_h, end_time)
    command = [
        locate_sumo_binary(), "-n", str(NETWORK_PATH), "-r", str(route_path),
        "--no-step-log", "--quit-on-end", "--tripinfo-output", str(tripinfo_path),
        "--summary-output", str(summary_path), "--time-to-teleport", "-1", "--end", str(end_time),
    ]
    if seed is not None:
        command.extend(["--seed", str(seed)])
    subprocess.run(command, check=True)

    expected = estimate_generated_vehicles(main_veh_h, side_veh_h, end_time)
    metrics = summarize_tripinfo(tripinfo_path, expected)
    metrics.update(main_veh_h=main_veh_h, side_veh_h=side_veh_h, seed=seed, duration_s=float(end_time))
    metrics["throughput"] = metrics["arrived_veh"] / end_time if end_time else 0.0
    metrics["queue_length"] = metrics["unfinished_vehicles"]
    return metrics
