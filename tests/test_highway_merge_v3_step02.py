from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STEP_DIR = ROOT / "experiments" / "highway_merge_v3" / "step02_throughput"
spec = importlib.util.spec_from_file_location("highway_merge_v3_step02", STEP_DIR / "run.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_capacity_state_requires_unfinished_vehicle_after_clearance() -> None:
    assert module.classify_capacity_state({"unfinished_vehicles": 0}) == "recovered"
    assert module.classify_capacity_state({"unfinished_vehicles": 1}) == "breakdown"


def test_summary_uses_breakdown_for_a_tied_seed_vote() -> None:
    rows = [
        {
            "main_veh_h": 1800, "side_veh_h": 2000, "capacity_state": "recovered",
            "peak_queue_vehicles": 4, "avg_wait_time_s": 2.0,
            "unfinished_vehicles": 0, "throughput": 0.8,
        },
        {
            "main_veh_h": 1800, "side_veh_h": 2000, "capacity_state": "breakdown",
            "peak_queue_vehicles": 8, "avg_wait_time_s": 6.0,
            "unfinished_vehicles": 3, "throughput": 0.7,
        },
    ]

    summary = module.summarize(rows)

    assert summary[0]["classification"] == "breakdown"
    assert summary[0]["ramp_veh_h"] == 2000
    assert summary[0]["mean_unfinished_vehicles"] == 1.5
