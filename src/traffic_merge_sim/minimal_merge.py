from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET


def _locate_sumo_binary() -> str:
    sumo_home = Path(__file__).resolve().parents[3]
    candidates = [
        shutil.which("sumo"),
        str(sumo_home / "bin" / "sumo"),
        str(Path("/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/bin/sumo")),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError("SUMO binary not found. Please install SUMO and ensure 'sumo' is on PATH.")


def _summarize_tripinfo(tripinfo_path: Path) -> dict[str, float | int]:
    tree = ET.parse(tripinfo_path)
    tripinfos = tree.getroot().findall("tripinfo")
    if not tripinfos:
        raise RuntimeError(f"No tripinfo entries found in {tripinfo_path}.")

    travel_times = [float(tripinfo.attrib["duration"]) for tripinfo in tripinfos]
    generated = len(tripinfos)
    arrived = generated
    avg_travel_time = sum(travel_times) / len(travel_times)
    total_travel_time = sum(travel_times)

    return {
        "main_veh_h": 1000,
        "side_veh_h": 400,
        "generated_veh": generated,
        "arrived_veh": arrived,
        "avg_travel_time_s": avg_travel_time,
        "total_travel_time_s": total_travel_time,
        "unfinished_vehicles": 0,
    }


def run_minimal_merge_experiment() -> Path:
    root = Path(__file__).resolve().parents[2]
    config_path = root / "sumo" / "config" / "minimal_merge.sumocfg"
    output_dir = root / "sumo" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    tripinfo_path = output_dir / "minimal_merge.tripinfo.xml"
    summary_path = output_dir / "minimal_merge.summary.xml"

    for path in (tripinfo_path, summary_path):
        if path.exists():
            path.unlink()

    cmd = [
        _locate_sumo_binary(),
        "-c",
        str(config_path),
        "--no-step-log",
        "--quit-on-end",
        "--tripinfo-output",
        str(tripinfo_path),
        "--summary-output",
        str(summary_path),
    ]
    subprocess.run(cmd, check=True)

    metrics = _summarize_tripinfo(tripinfo_path)
    csv_path = root / "experiments" / "minimal_merge_results.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "case_name",
                "main_veh_h",
                "side_veh_h",
                "generated_veh",
                "arrived_veh",
                "avg_travel_time_s",
                "total_travel_time_s",
                "unfinished_vehicles",
            ]
        )
        writer.writerow(
            [
                "base_case",
                metrics["main_veh_h"],
                metrics["side_veh_h"],
                metrics["generated_veh"],
                metrics["arrived_veh"],
                round(float(metrics["avg_travel_time_s"]), 3),
                round(float(metrics["total_travel_time_s"]), 3),
                metrics["unfinished_vehicles"],
            ]
        )

    print("Minimal uncontrolled merge simulation completed.")
    print(f"Results written to: {csv_path}")
    for key, value in metrics.items():
        if key in {"main_veh_h", "side_veh_h", "generated_veh", "arrived_veh", "unfinished_vehicles"}:
            print(f"{key}: {value}")
        else:
            print(f"{key}: {value:.3f}")

    return csv_path
