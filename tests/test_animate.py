from pathlib import Path

import pytest

from traffic_merge_sim.animate import FCDTimestep, build_parser, default_output_path, save_animation, select_timesteps, validate_output_path
from traffic_merge_sim.network_config import MINIMAL_MERGE
from traffic_merge_sim.visualize import VehicleState


def test_animation_defaults_to_mp4() -> None:
    args = build_parser().parse_args([])

    assert args.format == "mp4"
    assert args.fps == 10
    assert args.end_time is None
    assert args.fcd_input is None


def test_animation_accepts_existing_fcd_input() -> None:
    args = build_parser().parse_args(["--network", "highway_merge_v3", "--fcd-input", "results/case.fcd.xml"])

    assert args.network == "highway_merge_v3"
    assert args.fcd_input == Path("results/case.fcd.xml")


def test_select_timesteps_respects_range_and_sampling() -> None:
    timesteps = [FCDTimestep(time_s=float(time_s), vehicles=[]) for time_s in range(6)]

    selected = select_timesteps(timesteps, start_time_s=1, end_time_s=5, frame_step=2)

    assert [step.time_s for step in selected] == [1, 3, 5]


def test_select_timesteps_rejects_empty_range() -> None:
    with pytest.raises(ValueError, match="No FCD timesteps"):
        select_timesteps([FCDTimestep(time_s=0, vehicles=[])], start_time_s=1, end_time_s=2, frame_step=1)


def test_output_path_uses_selected_format() -> None:
    assert default_output_path(Path("output"), "case", "gif") == Path("output/case_animation.gif")


def test_output_path_extension_must_match_format() -> None:
    validate_output_path(Path("output/case.mp4"), "mp4")
    with pytest.raises(ValueError, match=".gif"):
        validate_output_path(Path("output/case.mp4"), "gif")


def test_save_animation_supports_empty_vehicle_frames(tmp_path: Path) -> None:
    output_path = tmp_path / "animation.gif"
    frames = [
        FCDTimestep(time_s=0, vehicles=[]),
        FCDTimestep(time_s=1, vehicles=[VehicleState("main_flow.0", x=10, y=-1.6, speed_m_s=20)]),
    ]

    save_animation(MINIMAL_MERGE, frames, output_path, "gif", fps=2)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
