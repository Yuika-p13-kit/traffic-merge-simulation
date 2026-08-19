from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STEP = ROOT / "experiments" / "step06_ramp_metering"


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"test_step06_{name}", STEP / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


controller = load("controller")
analysis = load("analysis")


def test_fixed_meter_releases_one_vehicle_per_interval_in_front_first() -> None:
    meter = controller.FixedIntervalMeter(4.0)
    held, released = meter.update(10.0, {"side_flow.0": 20.0, "side_flow.1": 10.0})
    assert released == "side_flow.0"
    assert held == {"side_flow.1"}
    assert meter.update(13.9, {"side_flow.1": 30.0})[1] is None
    assert meter.update(14.0, {"side_flow.1": 31.0})[1] == "side_flow.1"
    assert meter.release_times_s == [10.0, 14.0]


def test_fixed_meter_rejects_nonpositive_interval() -> None:
    with pytest.raises(ValueError, match="positive"):
        controller.FixedIntervalMeter(0.0)


def row(strategy: str, seed: int, tts: float) -> dict[str, object]:
    return {"strategy": strategy, "seed": seed, "total_demand_veh_h": 1000, "demand_ratio": "1:3",
            "total_time_spent_s": tts, "network_time_spent_s": tts / 2,
            "insertion_wait_time_s": tts / 2, "unfinished_vehicles": 10, "throughput": 0.25}


def test_analysis_compares_every_strategy_to_same_seed_baseline() -> None:
    rows = []
    for seed, delta in enumerate((-12, -10, -8, -11, -9), 1):
        rows.extend([row("uncontrolled", seed, 100), row("ramp_fixed_6s", seed, 100 + delta)])
    paired, summary = analysis.compare_with_uncontrolled(rows)
    tts = next(item for item in summary if item["metric"] == "total_time_spent_s")
    assert len([item for item in paired if item["metric"] == "total_time_spent_s"]) == 5
    assert tts["mean_paired_delta"] == pytest.approx(-10)
    assert tts["ci_95_high"] < 0
    assert tts["interpretation"] == "improves"
