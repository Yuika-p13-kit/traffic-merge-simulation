from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "experiments" / "step05-02_insertion_wait_tts" / "results" / "complete_tts_raw.csv"
for path in (ROOT, ROOT / "src", STEP_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from analysis import build_paired_rows, summarize_paired_rows
from experiments.common import write_metadata, write_rows
from visualize import generate_charts


PAIRED_FIELDS = [
    "total_demand_veh_h", "demand_ratio", "seed", "metric", "lower_is_better",
    "uncontrolled_value", "cooperative_value", "paired_delta",
]
SUMMARY_FIELDS = [
    "total_demand_veh_h", "demand_ratio", "metric", "lower_is_better", "paired_seeds",
    "mean_paired_delta", "sample_stddev", "standard_error", "t_critical_95",
    "ci_95_low", "ci_95_high", "ci_excludes_zero", "interpretation",
]


def run(input_csv: Path = DEFAULT_INPUT, output_dir: Path | None = None) -> Path:
    with input_csv.open(encoding="utf-8", newline="") as source:
        raw_rows = list(csv.DictReader(source))
    paired_rows = build_paired_rows(raw_rows)
    summary_rows = summarize_paired_rows(paired_rows)

    results_dir = output_dir or STEP_DIR / "results"
    paired_path = write_rows(results_dir / "paired_differences.csv", paired_rows, PAIRED_FIELDS)
    summary_path = write_rows(results_dir / "paired_confidence_summary.csv", summary_rows, SUMMARY_FIELDS)
    charts = generate_charts(paired_rows, summary_rows, results_dir / "figures")
    write_metadata(results_dir / "metadata.json", {
        "experiment_id": "step05_03_paired_confidence",
        "script": "experiments/step05-03_paired_confidence/run.py",
        "source_csv": str(input_csv.relative_to(ROOT)) if input_csv.is_relative_to(ROOT) else str(input_csv),
        "paired_csv": paired_path.name,
        "summary_csv": summary_path.name,
        "figures": [str(path.relative_to(results_dir)) for path in charts],
        "difference_definition": "cooperative_limited - uncontrolled for the same demand condition and seed",
        "confidence_interval": "two-sided 95% Student-t interval for the mean paired difference",
        "metrics": sorted({str(row["metric"]) for row in summary_rows}),
    })
    return paired_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Step 5-3 paired-seed difference and 95% CI charts.")
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    run(args.input_csv, args.output_dir)
