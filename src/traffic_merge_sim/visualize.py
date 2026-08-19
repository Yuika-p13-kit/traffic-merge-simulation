"""Create static snapshots of a selected SUMO merge network from FCD output."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from .network_config import MINIMAL_MERGE, NETWORK_CONFIGS, MergeNetworkConfig
from .paths import GENERATED_OUTPUT_DIR
from .sumo_runner import run_single_case


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: str
    x: float
    y: float
    speed_m_s: float


def read_network_lane_shapes(network_path: Path) -> list[list[tuple[float, float]]]:
    """Return drawable (non-internal) lane centre-lines from a SUMO network."""
    root = ET.parse(network_path).getroot()
    shapes: list[list[tuple[float, float]]] = []
    for edge in root.findall("edge"):
        if edge.get("function") == "internal":
            continue
        for lane in edge.findall("lane"):
            shape = lane.get("shape")
            if shape:
                shapes.append([tuple(map(float, point.split(","))) for point in shape.split()])
    return shapes


def read_fcd_timestep(fcd_path: Path, requested_time_s: float) -> tuple[float, list[VehicleState]]:
    """Read the FCD timestep nearest to ``requested_time_s``."""
    root = ET.parse(fcd_path).getroot()
    timesteps = root.findall("timestep")
    if not timesteps:
        raise ValueError(f"No timesteps found in FCD output: {fcd_path}")
    timestep = min(timesteps, key=lambda item: abs(float(item.get("time", "0")) - requested_time_s))
    vehicles = [
        VehicleState(
            vehicle_id=vehicle.attrib["id"], x=float(vehicle.attrib["x"]), y=float(vehicle.attrib["y"]),
            speed_m_s=float(vehicle.attrib["speed"]),
        )
        for vehicle in timestep.findall("vehicle")
    ]
    return float(timestep.attrib["time"]), vehicles


def vehicle_stream(vehicle_id: str) -> str:
    if vehicle_id.startswith("main_flow"):
        return "main"
    if vehicle_id.startswith("side_flow"):
        return "side"
    return "other"


def plot_snapshot(
    network: MergeNetworkConfig, fcd_path: Path, requested_time_s: float, output_path: Path,
) -> float:
    """Save a static map of the nearest FCD timestep and return its time."""
    actual_time_s, vehicles = read_fcd_timestep(fcd_path, requested_time_s)
    figure, axis = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
    lane_shapes = read_network_lane_shapes(network.network_path)
    for shape in lane_shapes:
        x_values, y_values = zip(*shape)
        axis.plot(x_values, y_values, color="#4b5563", linewidth=5, solid_capstyle="round", zorder=1)
        axis.plot(x_values, y_values, color="#d1d5db", linewidth=2.3, solid_capstyle="round", zorder=2)

    colours = {"main": "#2563eb", "side": "#dc2626", "other": "#6b7280"}
    for stream in ("main", "side", "other"):
        selected = [vehicle for vehicle in vehicles if vehicle_stream(vehicle.vehicle_id) == stream]
        if selected:
            axis.scatter(
                [vehicle.x for vehicle in selected], [vehicle.y for vehicle in selected],
                c=colours[stream], s=52, edgecolors="white", linewidths=0.7, zorder=3,
            )

    for x, y, label in network.merge_markers:
        axis.axvline(x, color="#111827", linestyle="--", linewidth=1, alpha=0.65, zorder=0)
        axis.text(x, y, label, ha="center", va="bottom", fontsize=9)
    axis.set_aspect("equal", adjustable="box")
    all_points = [point for shape in lane_shapes for point in shape]
    x_values, y_values = zip(*all_points)
    x_margin = max(40.0, (max(x_values) - min(x_values)) * 0.04)
    y_margin = max(40.0, (max(y_values) - min(y_values)) * 0.12)
    axis.set_xlim(min(x_values) - x_margin, max(x_values) + x_margin)
    axis.set_ylim(min(y_values) - y_margin, max(y_values) + y_margin)
    axis.set_xlabel("x (m)")
    axis.set_ylabel("y (m)")
    axis.set_title(f"{network.display_name} at t = {actual_time_s:g} s ({len(vehicles)} vehicles)")
    axis.grid(False)
    axis.legend(handles=[
        Line2D([0], [0], marker="o", color="w", label="mainline", markerfacecolor=colours["main"], markersize=8),
        Line2D([0], [0], marker="o", color="w", label="ramp", markerfacecolor=colours["side"], markersize=8),
    ], loc="upper right")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)
    return actual_time_s


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a merge model and save a static FCD snapshot.")
    parser.add_argument("--network", choices=sorted(NETWORK_CONFIGS), default=MINIMAL_MERGE.name,
                        help="Network model to simulate (default: minimal_merge).")
    parser.add_argument("--time", type=float, required=True, help="Simulation time in seconds to visualise.")
    parser.add_argument("--main-rate", type=int, default=200, help="Mainline demand in veh/h (default: 200).")
    parser.add_argument("--side-rate", type=int, default=820, help="Ramp demand in veh/h (default: 820).")
    parser.add_argument("--duration", type=float, default=600, help="Demand duration in seconds (default: 600).")
    parser.add_argument("--seed", type=int, default=42, help="SUMO random seed (default: 42).")
    parser.add_argument("--output", type=Path, default=None, help="PNG output path (default: sumo/output/generated/visualization/).")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.time < 0 or args.time > args.duration:
        raise SystemExit("--time must be between 0 and --duration.")
    network = NETWORK_CONFIGS[args.network]
    case_name = f"{network.name}_main_{args.main_rate}_side_{args.side_rate}_seed_{args.seed}"
    output_dir = GENERATED_OUTPUT_DIR / "visualization" / network.name
    fcd_path = output_dir / f"{case_name}.fcd.xml"
    output_path = args.output or output_dir / f"{case_name}_t{args.time:g}.png"
    run_single_case(
        main_veh_h=args.main_rate, side_veh_h=args.side_rate, duration=args.duration,
        seed=args.seed, fcd_output_path=fcd_path, network=network,
    )
    actual_time_s = plot_snapshot(network, fcd_path, args.time, output_path)
    print(f"FCD output: {fcd_path}")
    print(f"Snapshot at t={actual_time_s:g} s: {output_path}")


if __name__ == "__main__":
    main()
