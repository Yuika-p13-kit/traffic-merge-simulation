"""Network-specific identifiers and paths used by simulation experiments.

Keeping these definitions together prevents a controller for one research model
from silently being applied to another model with similarly named edges.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import SUMO_DIR


@dataclass(frozen=True)
class MergeNetworkConfig:
    name: str
    network_path: Path
    main_route_edges: tuple[str, ...]
    ramp_route_edges: tuple[str, ...]
    main_monitor_lane: str
    ramp_monitor_lane: str
    downstream_edge: str
    merge_completion_edges: tuple[str, ...]
    display_name: str
    merge_markers: tuple[tuple[float, float, str], ...]


MINIMAL_MERGE = MergeNetworkConfig(
    name="minimal_merge",
    network_path=SUMO_DIR / "network" / "minimal_merge.net.xml",
    main_route_edges=("main_in", "out"),
    ramp_route_edges=("side_in", "out"),
    main_monitor_lane="main_in_0",
    ramp_monitor_lane="side_in_0",
    downstream_edge="out",
    merge_completion_edges=("out",),
    display_name="Minimal merge",
    merge_markers=((500.0, 412.0, "merge"),),
)

HIGHWAY_MERGE_V2 = MergeNetworkConfig(
    name="highway_merge_v2",
    network_path=SUMO_DIR / "network" / "highway_merge_v2.net.xml",
    main_route_edges=("main_upstream", "main_merge", "downstream"),
    ramp_route_edges=("ramp_upstream", "ramp_merge", "downstream"),
    main_monitor_lane="main_merge_0",
    ramp_monitor_lane="ramp_merge_0",
    downstream_edge="downstream",
    merge_completion_edges=("downstream",),
    display_name="Highway merge v2",
    merge_markers=((500.0, 58.0, "parallel merge starts"), (1100.0, 58.0, "merge completes")),
)

NETWORK_CONFIGS = {config.name: config for config in (MINIMAL_MERGE, HIGHWAY_MERGE_V2)}
