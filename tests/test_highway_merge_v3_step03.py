from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STEP_DIR = ROOT / "experiments" / "highway_merge_v3" / "step03_demand_ratio"
spec = importlib.util.spec_from_file_location("highway_merge_v3_step03", STEP_DIR / "run.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_capacity_state_requires_unfinished_vehicle_after_clearance() -> None:
    assert module.classify_capacity_state({"unfinished_vehicles": 0}) == "recovered"
    assert module.classify_capacity_state({"unfinished_vehicles": 1}) == "breakdown"


def test_summary_uses_breakdown_for_a_tied_seed_vote_and_converts_throughput() -> None:
    rows = [
        {
            "total_demand_veh_h": 4000, "demand_ratio": "1:2", "main_veh_h": 1333,
            "side_veh_h": 2667, "capacity_state": "recovered", "peak_queue_vehicles": 8,
            "avg_wait_time_s": 2.0, "unfinished_vehicles": 0, "throughput": 1.0,
            "collisions": 0, "teleports": 0,
        },
        {
            "total_demand_veh_h": 4000, "demand_ratio": "1:2", "main_veh_h": 1333,
            "side_veh_h": 2667, "capacity_state": "breakdown", "peak_queue_vehicles": 12,
            "avg_wait_time_s": 6.0, "unfinished_vehicles": 3, "throughput": 0.9,
            "collisions": 1, "teleports": 1,
        },
    ]

    summary = module.summarize(rows)

    assert summary[0]["classification"] == "breakdown"
    assert summary[0]["ramp_veh_h"] == 2667
    assert summary[0]["mean_unfinished_vehicles"] == 1.5
    assert summary[0]["mean_throughput_veh_h"] == 3420.0
    assert summary[0]["collision_runs"] == 1
    assert summary[0]["teleport_runs"] == 1
