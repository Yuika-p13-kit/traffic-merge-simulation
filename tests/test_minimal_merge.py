from __future__ import annotations

import subprocess
from pathlib import Path

from traffic_merge_sim.minimal_merge import run_load_sweep


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
