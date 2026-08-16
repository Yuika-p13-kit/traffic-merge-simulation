from __future__ import annotations

import subprocess
from pathlib import Path

from traffic_merge_sim.minimal_merge import run_load_sweep, run_single_case


def test_minimal_merge_config_exists_and_python_runner_completes() -> None:
    root = Path(__file__).resolve().parents[1]

    assert (root / "sumo" / "config" / "minimal_merge.sumocfg").exists()
    assert (root / "sumo" / "network" / "minimal_merge.nod.xml").exists()
    assert (root / "sumo" / "network" / "minimal_merge.edg.xml").exists()

    result = subprocess.run(
        ["uv", "run", "python", "main.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_load_sweep_creates_summary_csv() -> None:
    csv_path = run_load_sweep(
        main_flow_rates=[600, 800],
        side_flow_rates=[200, 400],
        warmup_seconds=0,
    )
    assert csv_path.exists()
    assert csv_path.stat().st_size > 0


def test_run_single_case_accepts_explicit_experiment_parameters() -> None:
    metrics = run_single_case(
        main_veh_h=600,
        side_veh_h=200,
        end_time=300.0,
        clearance_time=120.0,
        seed=7,
    )

    assert metrics["main_veh_h"] == 600
    assert metrics["side_veh_h"] == 200
    assert metrics["seed"] == 7
    assert metrics["duration_s"] == 300.0
    assert metrics["clearance_time_s"] == 120.0
    assert metrics["simulation_end_s"] == 420.0
    assert metrics["unfinished_vehicles"] == 0


def test_cli_allows_overriding_q_main_q_side_seed_and_duration() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "main.py",
            "--q-main",
            "600",
            "--q-side",
            "200",
            "--seed",
            "7",
            "--duration",
            "300",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
