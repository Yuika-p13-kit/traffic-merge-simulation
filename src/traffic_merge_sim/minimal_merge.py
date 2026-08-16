from __future__ import annotations

import csv
import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from xml.etree import ElementTree as ET


SUMO_HOME = Path("/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO")
os.environ.setdefault("SUMO_HOME", str(SUMO_HOME))


def _locate_sumo_binary() -> str:
    candidates = [
        shutil.which("sumo"),
        str(SUMO_HOME / "bin" / "sumo"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("SUMO binary not found. Please install SUMO and ensure 'sumo' is on PATH.")


def _build_case_route_file(route_path: Path, main_veh_h: int, side_veh_h: int, end_time: float = 1200.0) -> None:
    route_path.parent.mkdir(parents=True, exist_ok=True)
    main_period = 3600.0 / main_veh_h if main_veh_h > 0 else None
    side_period = 3600.0 / side_veh_h if side_veh_h > 0 else None

    def flow_xml(flow_id: str, route_id: str, rate: float | None) -> str:
        if rate is None:
            return ""
        return (
            f'    <flow id="{flow_id}" type="car" route="{route_id}" begin="0" end="{end_time:.1f}" '
            f'period="{rate:.6f}" departLane="free" departSpeed="max"/>'
        )

    xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<routes xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"
        xsi:noNamespaceSchemaLocation=\"http://sumo.dlr.de/xsd/routes_file.xsd\">
    <vType id=\"car\" accel=\"2.6\" decel=\"4.5\" length=\"5.0\" maxSpeed=\"30.0\" sigma=\"0.5\"/>

    <route id=\"main_route\" edges=\"main_in out\"/>
    <route id=\"side_route\" edges=\"side_in out\"/>

"""
    xml += flow_xml("main_flow", "main_route", main_period) + "\n"
    xml += flow_xml("side_flow", "side_route", side_period) + "\n"
    xml += "</routes>\n"
    route_path.write_text(xml, encoding="utf-8")


def _estimate_generated_vehicles(main_veh_h: int, side_veh_h: int, end_time: float = 1200.0) -> int:
    return int(round(main_veh_h * end_time / 3600.0)) + int(round(side_veh_h * end_time / 3600.0))


def _state_from_metrics(avg_travel_time_s: float, unfinished_vehicles: int) -> str:
    if unfinished_vehicles == 0 and avg_travel_time_s <= 60.0:
        return "free_flow"
    if unfinished_vehicles == 0 and avg_travel_time_s <= 75.0:
        return "deceleration"
    if unfinished_vehicles <= 5 and avg_travel_time_s <= 90.0:
        return "queue"
    return "breakdown"


def _summarize_tripinfo(tripinfo_path: Path, expected_generated: int) -> dict[str, float | int | str]:
    tree = ET.parse(tripinfo_path)
    tripinfos = tree.getroot().findall("tripinfo")

    if not tripinfos:
        return {
            "generated_veh": expected_generated,
            "arrived_veh": 0,
            "avg_travel_time_s": 0.0,
            "total_travel_time_s": 0.0,
            "unfinished_vehicles": expected_generated,
            "state": "breakdown",
        }

    travel_times = [float(tripinfo.attrib["duration"]) for tripinfo in tripinfos]
    reached = len(tripinfos)
    avg_travel_time = sum(travel_times) / len(travel_times)
    total_travel_time = sum(travel_times)
    unfinished = max(0, expected_generated - reached)
    state = _state_from_metrics(avg_travel_time, unfinished)

    return {
        "generated_veh": expected_generated,
        "arrived_veh": reached,
        "avg_travel_time_s": avg_travel_time,
        "total_travel_time_s": total_travel_time,
        "unfinished_vehicles": unfinished,
        "state": state,
    }


def run_single_case(
    main_veh_h: int | None = None,
    side_veh_h: int | None = None,
    end_time: float | None = None,
    *,
    q_main: int | None = None,
    q_side: int | None = None,
    duration: float | None = None,
    seed: int | None = None,
) -> dict[str, float | int | str]:
    if q_main is not None:
        main_veh_h = q_main
    if q_side is not None:
        side_veh_h = q_side
    if duration is not None:
        end_time = duration
    if main_veh_h is None or side_veh_h is None:
        raise ValueError("main_veh_h/q_main and side_veh_h/q_side must be provided.")
    if end_time is None:
        end_time = 1200.0

    root = Path(__file__).resolve().parents[2]
    output_dir = root / "sumo" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    case_name = f"main_{main_veh_h}_side_{side_veh_h}"
    route_path = output_dir / f"{case_name}.rou.xml"
    tripinfo_path = output_dir / f"{case_name}.tripinfo.xml"
    summary_path = output_dir / f"{case_name}.summary.xml"

    for path in (route_path, tripinfo_path, summary_path):
        if path.exists():
            path.unlink()

    _build_case_route_file(route_path, main_veh_h, side_veh_h, end_time=end_time)
    cmd = [
        _locate_sumo_binary(),
        "-n",
        str(root / "sumo" / "network" / "minimal_merge.net.xml"),
        "-r",
        str(route_path),
        "--no-step-log",
        "--quit-on-end",
        "--tripinfo-output",
        str(tripinfo_path),
        "--summary-output",
        str(summary_path),
        "--time-to-teleport",
        "-1",
        "--end",
        str(end_time),
    ]
    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    subprocess.run(cmd, check=True)

    expected_generated = _estimate_generated_vehicles(main_veh_h, side_veh_h, end_time=end_time)
    metrics = _summarize_tripinfo(tripinfo_path, expected_generated)
    metrics["main_veh_h"] = main_veh_h
    metrics["side_veh_h"] = side_veh_h
    metrics["seed"] = seed
    metrics["duration_s"] = float(end_time)
    return metrics


def run_load_sweep(
    main_flow_rates: Iterable[int],
    side_flow_rates: Iterable[int],
    end_time: float = 1200.0,
    warmup_seconds: float = 0.0,
    *,
    seed: int | None = None,
) -> Path:
    root = Path(__file__).resolve().parents[2]
    output_dir = root / "experiments"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "minimal_merge_load_sweep.csv"

    rows: list[dict[str, float | int | str]] = []
    for main_veh_h in main_flow_rates:
        for side_veh_h in side_flow_rates:
            if warmup_seconds > 0:
                pass
            metrics = run_single_case(main_veh_h, side_veh_h, end_time=end_time, seed=seed)
            rows.append(metrics)

    fieldnames = [
        "main_veh_h",
        "side_veh_h",
        "generated_veh",
        "arrived_veh",
        "unfinished_vehicles",
        "avg_travel_time_s",
        "total_travel_time_s",
        "state",
        "seed",
        "duration_s",
    ]

    with csv_path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Load sweep completed. Results saved to: {csv_path}")
    for row in rows:
        print(row)
    return csv_path


def run_minimal_merge_experiment(
    *,
    q_main: int | None = None,
    q_side: int | None = None,
    seed: int | None = None,
    duration: float = 1800.0,
) -> Path:
    """Default validation run for the uncontrolled merge model.

    This low-load sweep is intended to confirm the natural transition from
    free-flow to deceleration and queueing as vehicle demand increases.
    """
    main_flow_rates = [20, 40, 60] if q_main is None else [q_main]
    side_flow_rates = [10, 20, 30] if q_side is None else [q_side]
    return run_load_sweep(main_flow_rates, side_flow_rates, end_time=duration, seed=seed)


def run_high_load_experiment(
    *,
    q_main: int | None = None,
    q_side: int | None = None,
    seed: int | None = None,
    duration: float = 1800.0,
) -> Path:
    """Exploratory high-load sweep retained for comparison studies."""
    main_flow_rates = [600, 800, 1000, 1200, 1400] if q_main is None else [q_main]
    side_flow_rates = [200, 400, 600, 800, 1000] if q_side is None else [q_side]
    return run_load_sweep(main_flow_rates, side_flow_rates, end_time=duration, seed=seed)
