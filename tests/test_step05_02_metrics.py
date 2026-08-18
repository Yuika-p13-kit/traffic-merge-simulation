from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STEP_DIR = ROOT / "experiments" / "step05-02_insertion_wait_tts"
spec = importlib.util.spec_from_file_location("step05_02_metrics", STEP_DIR / "metrics.py")
assert spec and spec.loader
metrics_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = metrics_module
spec.loader.exec_module(metrics_module)
CompleteTTSMetrics = metrics_module.CompleteTTSMetrics


def test_complete_tts_adds_pending_insertion_wait() -> None:
    metrics = CompleteTTSMetrics()
    metrics.observe(
        {"main_flow.0": 10.0}, {"side_flow.0"},
        {"main_flow.0", "side_flow.0"}, {"main_flow.0"}, set(), within_demand=True,
    )
    metrics.observe(
        {"main_flow.0": 10.0, "side_flow.0": 0.0}, set(),
        set(), {"side_flow.0"}, set(), within_demand=True,
    )
    metrics.observe(
        {"side_flow.0": 0.0}, set(), set(), set(), {"main_flow.0"}, within_demand=False,
    )

    result = metrics.result()
    assert result["network_time_spent_s"] == 4.0
    assert result["insertion_wait_time_s"] == 1.0
    assert result["total_time_spent_s"] == 5.0
    assert result["side_total_time_spent_s"] == 3.0
    assert result["side_pending_veh_end"] == 0
    assert result["accounted_loaded_veh"] == 2


def test_pending_vehicle_at_end_is_counted_as_unfinished() -> None:
    metrics = CompleteTTSMetrics()
    metrics.observe(
        {}, {"side_flow.0"}, {"side_flow.0"}, set(), set(), within_demand=True,
    )

    result = metrics.result()
    assert result["side_pending_veh_end"] == 1
    assert result["side_total_unfinished_veh"] == 1
    assert result["side_insertion_wait_time_s"] == 1.0
