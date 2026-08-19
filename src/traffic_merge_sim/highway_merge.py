"""Baseline entrypoints for the highway-style merge research series."""

from __future__ import annotations

from pathlib import Path

from .network_config import HIGHWAY_MERGE_V2
from .sumo_runner import run_single_case


def run_highway_single_case(
    main_veh_h: int, ramp_veh_h: int, *, duration: float = 1200.0,
    seed: int | None = None, clearance_time: float = 0.0,
) -> dict[str, float | int | str | None]:
    """Run one uncontrolled highway-merge baseline case.

    Demand calibration for Steps 1--3 belongs to this series and must not use
    results from ``minimal_merge``.
    """
    return run_single_case(
        main_veh_h, ramp_veh_h, duration, seed=seed,
        clearance_time=clearance_time, network=HIGHWAY_MERGE_V2,
    )
