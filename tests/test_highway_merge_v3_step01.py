from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STEP_DIR = ROOT / "experiments" / "highway_merge_v3" / "step01_baseline"
spec = importlib.util.spec_from_file_location("highway_merge_v3_step01", STEP_DIR / "run.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_baseline_summary_counts_recovery_and_integrity_events() -> None:
    rows = [
        {
            "main_veh_h": 1200, "side_veh_h": 600, "unfinished_vehicles": 0,
            "collisions": 0, "teleports": 0, "peak_queue_vehicles": 2,
            "avg_wait_time_s": 1.0, "throughput": 0.4,
        },
        {
            "main_veh_h": 1200, "side_veh_h": 600, "unfinished_vehicles": 3,
            "collisions": 1, "teleports": 0, "peak_queue_vehicles": 8,
            "avg_wait_time_s": 5.0, "throughput": 0.3,
        },
    ]

    summary = module.summarize(rows)

    assert summary == [{
        "main_veh_h": 1200, "ramp_veh_h": 600, "runs": 2,
        "recovered_runs": 1, "unfinished_runs": 1, "collision_runs": 1,
        "teleport_runs": 0, "mean_peak_queue_vehicles": 5.0,
        "mean_avg_wait_time_s": 3.0, "mean_unfinished_vehicles": 1.5,
        "mean_throughput_veh_s": 0.35,
    }]
