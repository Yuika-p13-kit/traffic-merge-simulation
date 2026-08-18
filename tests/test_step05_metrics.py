from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STEP_DIR = ROOT / "experiments" / "step05_metrics_visualization"
spec = importlib.util.spec_from_file_location("step05_metrics", STEP_DIR / "metrics.py")
assert spec and spec.loader
metrics_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = metrics_module
spec.loader.exec_module(metrics_module)
NetworkMetrics = metrics_module.NetworkMetrics
InterventionResponseTracker = metrics_module.InterventionResponseTracker


def test_tts_and_waiting_include_unfinished_vehicles() -> None:
    metrics = NetworkMetrics()
    metrics.observe(
        {"main_flow.0": 10.0, "side_flow.0": 0.0},
        {"main_flow.0", "side_flow.0"}, set(), within_demand=True,
    )
    metrics.observe(
        {"side_flow.0": 0.0}, set(), {"main_flow.0"}, within_demand=True,
    )

    result = metrics.result()
    assert result["total_time_spent_s"] == 3.0
    assert result["main_arrived_veh"] == 1
    assert result["side_unfinished_veh"] == 1
    assert result["side_total_time_spent_s"] == 2.0
    assert result["side_total_wait_time_s"] == 2.0
    assert result["side_peak_queue_vehicles"] == 1


def test_intervention_response_counts_unique_side_merges_in_window() -> None:
    tracker = InterventionResponseTracker(response_window_s=30.0)
    tracker.start(10.0)
    tracker.observe_side_merges(20.0, {"side_flow.1"})
    tracker.observe_side_merges(25.0, {"side_flow.1", "side_flow.2"})
    tracker.observe_side_merges(41.0, {"side_flow.3"})

    assert tracker.side_merges_after_intervention == 2
