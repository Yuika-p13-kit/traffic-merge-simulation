from pathlib import Path

from traffic_merge_sim.network_config import HIGHWAY_MERGE_V2
import matplotlib.pyplot as plt

from traffic_merge_sim.visualize import (
    LANE_GUIDE_WIDTH,
    FIGURE_SIZE,
    ROAD_EDGE_WIDTH,
    ROAD_SURFACE_WIDTH,
    build_parser,
    draw_roads,
    read_fcd_timestep,
    read_fcd_timesteps,
    read_network_lane_shapes,
    vehicle_stream,
)


def test_read_network_lane_shapes_excludes_internal_edges() -> None:
    shapes = read_network_lane_shapes(Path("sumo/network/minimal_merge.net.xml"))

    assert len(shapes) == 3
    assert shapes[0][0] == (-0.0, -1.6)


def test_draw_roads_uses_wide_road_surface_and_lane_guides() -> None:
    figure, axis = plt.subplots()

    draw_roads(axis, [[(0, 0), (10, 0)]])

    assert [line.get_linewidth() for line in axis.lines] == [ROAD_EDGE_WIDTH, ROAD_SURFACE_WIDTH, LANE_GUIDE_WIDTH]
    plt.close(figure)


def test_visualization_uses_tall_figure_for_lane_separation() -> None:
    assert FIGURE_SIZE[1] > FIGURE_SIZE[0] / 2


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
