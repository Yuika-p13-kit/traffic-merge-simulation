from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


STEP = Path(__file__).resolve().parents[1] / "experiments/highway_merge_v3/step05_evaluation"


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"v3_step05_{name}", STEP / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_complete_tts_counts_pending_ramp_time() -> None:
    metrics = load("metrics").CompleteTTSMetrics()
    metrics.observe({"main_flow.0": 20.0}, {"side_flow.0"}, {"main_flow.0", "side_flow.0"}, {"main_flow.0"}, set(), within_demand=True)
    metrics.observe({"side_flow.0": 0.0}, set(), set(), {"side_flow.0"}, {"main_flow.0"}, within_demand=False)
    result = metrics.result()
    assert result["network_time_spent_s"] == 2.0
    assert result["ramp_insertion_wait_time_s"] == 1.0
    assert result["total_time_spent_s"] == 3.0
    assert result["ramp_total_unfinished_veh"] == 1


def test_paired_summary_uses_same_seed_and_ci() -> None:
    analysis = load("analysis")
    rows = []
    for seed, delta in enumerate((-12, -10, -8, -11, -9), 1):
        for strategy, value in (("uncontrolled", 100), ("cooperative_limited", 100 + delta)):
            rows.append({"seed": seed, "strategy": strategy, "total_time_spent_s": value, "network_time_spent_s": value, "insertion_wait_time_s": 0, "unfinished_vehicles": 10, "throughput": 0.2})
    result = next(row for row in analysis.paired_summary(rows) if row["metric"] == "total_time_spent_s")
    assert result["mean_paired_delta"] == pytest.approx(-10)
    assert result["ci_95_high"] < 0
    assert result["interpretation"] == "improves"
