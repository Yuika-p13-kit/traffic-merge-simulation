from pathlib import Path

from traffic_merge_sim.visualize import read_fcd_timestep, read_network_lane_shapes, vehicle_stream


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


def test_vehicle_stream_uses_route_builder_flow_ids() -> None:
    assert vehicle_stream("main_flow.8") == "main"
    assert vehicle_stream("side_flow.3") == "side"
    assert vehicle_stream("unknown.0") == "other"
