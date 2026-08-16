from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from .paths import GENERATED_OUTPUT_DIR
from .sumo_runner import run_single_case

RESULT_FIELDS = [
    "main_veh_h", "side_veh_h", "expected_generated_veh", "generated_veh", "arrived_veh", "unfinished_vehicles",
    "throughput", "avg_wait_time_s", "total_wait_time_s", "queue_length",
    "avg_travel_time_s", "total_travel_time_s", "state", "seed", "duration_s",
    "clearance_time_s", "simulation_end_s", "peak_queue_vehicles",
    "final_running_vehicles", "final_waiting_vehicles", "inserted_vehicles",
    "loaded_vehicles", "teleports", "collisions",
]


def run_load_sweep(
    main_flow_rates: Iterable[int], side_flow_rates: Iterable[int],
    end_time: float = 1200.0, warmup_seconds: float = 0.0,
    *, seed: int | None = None, csv_path: Path | None = None, clearance_time: float = 0.0,
) -> Path:
    del warmup_seconds  # Reserved until warm-up exclusion is implemented.
    csv_path = csv_path or GENERATED_OUTPUT_DIR / "load_sweep.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        run_single_case(main_rate, side_rate, end_time=end_time, seed=seed, clearance_time=clearance_time)
        for main_rate in main_flow_rates
        for side_rate in side_flow_rates
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=RESULT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Load sweep completed. Results saved to: {csv_path}")
    return csv_path


def run_minimal_merge_experiment(
    *, q_main: int | None = None, q_side: int | None = None,
    seed: int | None = None, duration: float = 1800.0,
) -> Path:
    main_rates = [20, 40, 60] if q_main is None else [q_main]
    side_rates = [10, 20, 30] if q_side is None else [q_side]
    return run_load_sweep(
        main_rates,
        side_rates,
        duration,
        seed=seed,
        csv_path=GENERATED_OUTPUT_DIR / "quick_validation.csv",
    )


def run_high_load_experiment(
    *, q_main: int | None = None, q_side: int | None = None,
    seed: int | None = None, duration: float = 1800.0,
) -> Path:
    main_rates = [600, 800, 1000, 1200, 1400] if q_main is None else [q_main]
    side_rates = [200, 400, 600, 800, 1000] if q_side is None else [q_side]
    return run_load_sweep(main_rates, side_rates, duration, seed=seed)
