from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
STEP_DIR = ROOT / "experiments" / "step05-03_paired_confidence"
spec = importlib.util.spec_from_file_location("step05_03_analysis", STEP_DIR / "analysis.py")
assert spec and spec.loader
analysis = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = analysis
spec.loader.exec_module(analysis)


def raw_row(strategy: str, seed: int, tts: float, throughput: float = 0.25) -> dict[str, str]:
    return {
        "strategy": strategy, "seed": str(seed), "total_demand_veh_h": "1000",
        "demand_ratio": "1:3", "total_time_spent_s": str(tts),
        "network_time_spent_s": str(tts / 2), "insertion_wait_time_s": str(tts / 2),
        "unfinished_vehicles": "10", "throughput": str(throughput),
    }


def test_build_paired_rows_joins_the_same_seed() -> None:
    rows = [
        raw_row("uncontrolled", 1, 100.0), raw_row("cooperative_limited", 1, 90.0),
        raw_row("uncontrolled", 2, 120.0), raw_row("cooperative_limited", 2, 125.0),
    ]
    paired = analysis.build_paired_rows(rows)
    tts = [row for row in paired if row["metric"] == "total_time_spent_s"]

    assert [row["seed"] for row in tts] == [1, 2]
    assert [row["paired_delta"] for row in tts] == [-10.0, 5.0]


def test_summary_uses_student_t_interval_and_interprets_direction() -> None:
    rows = []
    for seed, delta in enumerate((-12.0, -10.0, -8.0, -11.0, -9.0), start=1):
        rows.extend([
            raw_row("uncontrolled", seed, 100.0),
            raw_row("cooperative_limited", seed, 100.0 + delta),
        ])
    paired = analysis.build_paired_rows(rows)
    summary = analysis.summarize_paired_rows(paired)
    tts = next(row for row in summary if row["metric"] == "total_time_spent_s")

    assert tts["paired_seeds"] == 5
    assert tts["mean_paired_delta"] == pytest.approx(-10.0)
    assert tts["t_critical_95"] == pytest.approx(2.776)
    assert tts["ci_95_high"] < 0
    assert tts["interpretation"] == "improves"


def test_missing_strategy_pair_is_rejected() -> None:
    with pytest.raises(ValueError, match="Missing paired strategy"):
        analysis.build_paired_rows([raw_row("uncontrolled", 1, 100.0)])
