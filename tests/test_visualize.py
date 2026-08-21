from pathlib import Path

from traffic_merge_sim.network_config import HIGHWAY_MERGE_V2
from traffic_merge_sim.visualize import build_parser, read_fcd_timestep, read_fcd_timesteps, read_network_lane_shapes, vehicle_stream


def test_read_network_lane_shapes_excludes_internal_edges() -> None:
    shapes = read_network_lane_shapes(Path("sumo/network/minimal_merge.net.xml"))

    assert len(shapes) == 3
    assert shapes[0][0] == (-0.0, -1.6)


def test_read_fcd_timestep_selects_nearest_time(tmp_path: Path) -> None:
    fcd_path = tmp_path / "case.fcd.xml"
    fcd_path.write_text(
        '<fcd-export><timestep time="10"><vehicle id="main_flow.0" x="1" y="2" speed="3"/></timestep>'
        '<timestep time="12"><vehicle id="side_flow.0" x="4" y="5" speed="6"/></timestep></fcd-export>',
        encoding="utf-8",
    )

    time_s, vehicles = read_fcd_timestep(fcd_path, 11.6)

    assert time_s == 12
    assert vehicles[0].vehicle_id == "side_flow.0"
    assert vehicles[0].speed_m_s == 6


def test_read_fcd_timesteps_returns_all_states_in_order(tmp_path: Path) -> None:
    fcd_path = tmp_path / "case.fcd.xml"
    fcd_path.write_text(
        '<fcd-export><timestep time="2"><vehicle id="main_flow.0" x="1" y="2" speed="3"/></timestep>'
        '<timestep time="3"><vehicle id="side_flow.0" x="4" y="5" speed="6"/></timestep></fcd-export>',
        encoding="utf-8",
    )

    timesteps = read_fcd_timesteps(fcd_path)

    assert [step.time_s for step in timesteps] == [2, 3]
    assert timesteps[1].vehicles[0].vehicle_id == "side_flow.0"


def test_vehicle_stream_uses_route_builder_flow_ids() -> None:
    assert vehicle_stream("main_flow.8") == "main"
    assert vehicle_stream("side_flow.3") == "side"
    assert vehicle_stream("unknown.0") == "other"


def test_visualization_accepts_highway_network_selection() -> None:
    parser = build_parser()
    args = parser.parse_args(["--network", HIGHWAY_MERGE_V2.name, "--time", "30"])

    assert args.network == HIGHWAY_MERGE_V2.name
