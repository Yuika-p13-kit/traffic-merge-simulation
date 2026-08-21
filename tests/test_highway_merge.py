from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from traffic_merge_sim.network_config import HIGHWAY_MERGE_V2, HIGHWAY_MERGE_V3
from traffic_merge_sim.route_builder import build_case_route_file


def test_highway_merge_network_and_config_are_present() -> None:
    root = Path(__file__).resolve().parents[1]

    assert HIGHWAY_MERGE_V2.network_path == root / "sumo/network/highway_merge_v2.net.xml"
    assert HIGHWAY_MERGE_V2.network_path.exists()
    assert HIGHWAY_MERGE_V2.main_route_edges == ("main_upstream", "main_merge", "downstream")
    assert HIGHWAY_MERGE_V2.ramp_route_edges == ("ramp_upstream", "ramp_merge", "downstream")
    assert HIGHWAY_MERGE_V2.merge_completion_edges == ("downstream",)


def test_highway_route_builder_uses_only_highway_network_ids(tmp_path: Path) -> None:
    route_path = tmp_path / "case.rou.xml"

    build_case_route_file(route_path, 1200, 400, network=HIGHWAY_MERGE_V2)

    contents = route_path.read_text(encoding="utf-8")
    assert 'edges="main_upstream main_merge downstream"' in contents
    assert 'edges="ramp_upstream ramp_merge downstream"' in contents
    assert "main_in" not in contents


def test_highway_v3_has_a_three_lane_merge_and_two_lane_downstream() -> None:
    root = ET.parse(HIGHWAY_MERGE_V3.network_path).getroot()
    edges = {edge.attrib["id"]: edge for edge in root.findall("edge") if "id" in edge.attrib}

    assert len(edges["main_upstream"].findall("lane")) == 2
    assert len(edges["main_merge"].findall("lane")) == 3
    assert len(edges["downstream"].findall("lane")) == 2
    assert HIGHWAY_MERGE_V3.ramp_route_edges == ("ramp_upstream", "main_merge", "downstream")
