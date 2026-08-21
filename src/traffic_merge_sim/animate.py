"""Create MP4 or GIF animations of a SUMO merge simulation from FCD output."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.lines import Line2D

from .network_config import MINIMAL_MERGE, NETWORK_CONFIGS, MergeNetworkConfig
from .paths import GENERATED_OUTPUT_DIR
from .sumo_runner import run_single_case
from .visualize import FCDTimestep, read_fcd_timesteps, read_network_lane_shapes, vehicle_stream

SUPPORTED_FORMATS = ("mp4", "gif")
COLOURS = {"main": "#2563eb", "side": "#dc2626", "other": "#6b7280"}


def select_timesteps(timesteps: list[FCDTimestep], start_time_s: float, end_time_s: float, frame_step: int) -> list[FCDTimestep]:
    """Select chronologically ordered frames for the requested animation window."""
    selected = [step for step in timesteps if start_time_s <= step.time_s <= end_time_s]
    if not selected:
        raise ValueError("No FCD timesteps are available in the requested time range.")
    return selected[::frame_step]


def build_writer(output_format: str, fps: int):
    """Return the Matplotlib writer for an animation format."""
    if output_format == "mp4":
        if not FFMpegWriter.isAvailable():
            raise RuntimeError("MP4 output requires FFmpeg. Install it and ensure it is on PATH.")
        return FFMpegWriter(fps=fps, codec="h264")
    if output_format == "gif":
        if not PillowWriter.isAvailable():
            raise RuntimeError("GIF output requires Pillow.")
        return PillowWriter(fps=fps)
    raise ValueError(f"Unsupported animation format: {output_format}")


def default_output_path(output_dir: Path, case_name: str, output_format: str) -> Path:
    return output_dir / f"{case_name}_animation.{output_format}"


def validate_output_path(output_path: Path, output_format: str) -> None:
    expected_suffix = f".{output_format}"
    if output_path.suffix.lower() != expected_suffix:
        raise ValueError(f"--output must use the {expected_suffix} extension when --format is {output_format}.")


def save_animation(network: MergeNetworkConfig, timesteps: list[FCDTimestep], output_path: Path, output_format: str, fps: int) -> None:
    """Render selected FCD timesteps into an MP4 or GIF file."""
    lane_shapes = read_network_lane_shapes(network.network_path)
    all_points = [point for shape in lane_shapes for point in shape]
    x_values, y_values = zip(*all_points)
    x_margin = max(40.0, (max(x_values) - min(x_values)) * 0.04)
    y_margin = max(40.0, (max(y_values) - min(y_values)) * 0.12)
    figure, axis = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
    for shape in lane_shapes:
        lane_x, lane_y = zip(*shape)
        axis.plot(lane_x, lane_y, color="#4b5563", linewidth=5, solid_capstyle="round", zorder=1)
        axis.plot(lane_x, lane_y, color="#d1d5db", linewidth=2.3, solid_capstyle="round", zorder=2)
    for x, y, label in network.merge_markers:
        axis.axvline(x, color="#111827", linestyle="--", linewidth=1, alpha=0.65, zorder=0)
        axis.text(x, y, label, ha="center", va="bottom", fontsize=9)
    axis.set(xlim=(min(x_values) - x_margin, max(x_values) + x_margin), ylim=(min(y_values) - y_margin, max(y_values) + y_margin), xlabel="x (m)", ylabel="y (m)")
    axis.set_aspect("equal", adjustable="box")
    axis.grid(False)
    axis.legend(handles=[
        Line2D([0], [0], marker="o", color="w", label="mainline", markerfacecolor=COLOURS["main"], markersize=8),
        Line2D([0], [0], marker="o", color="w", label="ramp", markerfacecolor=COLOURS["side"], markersize=8),
    ], loc="upper right")
    artists = {stream: axis.scatter([], [], c=COLOURS[stream], s=52, edgecolors="white", linewidths=0.7, zorder=3) for stream in COLOURS}
    title = axis.set_title("")

    def update(frame_index: int):
        step = timesteps[frame_index]
        for stream, artist in artists.items():
            points = [(vehicle.x, vehicle.y) for vehicle in step.vehicles if vehicle_stream(vehicle.vehicle_id) == stream]
            artist.set_offsets(points if points else np.empty((0, 2)))
        title.set_text(f"{network.display_name} at t = {step.time_s:g} s ({len(step.vehicles)} vehicles)")
        return (*artists.values(), title)

    animation = FuncAnimation(figure, update, frames=len(timesteps), interval=1000 / fps, blit=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    animation.save(output_path, writer=build_writer(output_format, fps), dpi=160)
    plt.close(figure)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a merge model and save an FCD animation.")
    parser.add_argument("--network", choices=sorted(NETWORK_CONFIGS), default=MINIMAL_MERGE.name)
    parser.add_argument("--main-rate", type=int, default=200, help="Mainline demand in veh/h (default: 200).")
    parser.add_argument("--side-rate", type=int, default=820, help="Ramp demand in veh/h (default: 820).")
    parser.add_argument("--duration", type=float, default=600, help="Demand duration in seconds (default: 600).")
    parser.add_argument("--seed", type=int, default=42, help="SUMO random seed (default: 42).")
    parser.add_argument("--start-time", type=float, default=0, help="First simulation time to include (default: 0).")
    parser.add_argument("--end-time", type=float, default=None, help="Last simulation time to include (default: --duration).")
    parser.add_argument("--frame-step", type=int, default=1, help="Use every Nth FCD timestep (default: 1).")
    parser.add_argument("--fps", type=int, default=10, help="Output frames per second (default: 10).")
    parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="mp4", help="Output format (default: mp4).")
    parser.add_argument("--output", type=Path, default=None, help="Output .mp4 or .gif path.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    end_time_s = args.duration if args.end_time is None else args.end_time
    if args.start_time < 0 or end_time_s < args.start_time or end_time_s > args.duration:
        raise SystemExit("--start-time and --end-time must define a range within --duration.")
    if args.frame_step < 1:
        raise SystemExit("--frame-step must be at least 1.")
    if args.fps < 1:
        raise SystemExit("--fps must be at least 1.")
    network = NETWORK_CONFIGS[args.network]
    case_name = f"{network.name}_main_{args.main_rate}_side_{args.side_rate}_seed_{args.seed}"
    output_dir = GENERATED_OUTPUT_DIR / "visualization" / network.name
    fcd_path = output_dir / f"{case_name}.fcd.xml"
    output_path = args.output or default_output_path(output_dir, case_name, args.format)
    try:
        validate_output_path(output_path, args.format)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    run_single_case(main_veh_h=args.main_rate, side_veh_h=args.side_rate, duration=args.duration, seed=args.seed, fcd_output_path=fcd_path, network=network)
    frames = select_timesteps(read_fcd_timesteps(fcd_path), args.start_time, end_time_s, args.frame_step)
    save_animation(network, frames, output_path, args.format, args.fps)
    print(f"FCD output: {fcd_path}")
    print(f"Animation ({len(frames)} frames, {args.format}): {output_path}")


if __name__ == "__main__":
    main()
