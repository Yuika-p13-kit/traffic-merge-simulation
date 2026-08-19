from __future__ import annotations

from collections.abc import Iterable
from statistics import mean, stdev


METRICS = {
    "total_time_spent_s": ("total_time_spent_s", 1.0, True),
    "network_time_spent_s": ("network_time_spent_s", 1.0, True),
    "insertion_wait_time_s": ("insertion_wait_time_s", 1.0, True),
    "unfinished_vehicles": ("unfinished_vehicles", 1.0, True),
    "throughput_veh_h": ("throughput", 3600.0, False),
}

# Two-sided 95% Student-t critical values. Values above 30 df use the
# normal approximation, which is sufficient for the intended seed counts.
T_CRITICAL_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def t_critical_95(degrees_of_freedom: int) -> float:
    if degrees_of_freedom < 1:
        raise ValueError("At least two paired seeds are required for a confidence interval")
    return T_CRITICAL_95.get(degrees_of_freedom, 1.96)


def build_paired_rows(raw_rows: Iterable[dict[str, str]]) -> list[dict[str, object]]:
    rows = list(raw_rows)
    indexed: dict[tuple[int, str, int, str], dict[str, str]] = {}
    for row in rows:
        key = (
            int(row["total_demand_veh_h"]), str(row["demand_ratio"]),
            int(row["seed"]), str(row["strategy"]),
        )
        if key in indexed:
            raise ValueError(f"Duplicate experiment row: {key}")
        indexed[key] = row

    conditions = sorted({(key[0], key[1], key[2]) for key in indexed})
    output: list[dict[str, object]] = []
    for total_rate, ratio, seed in conditions:
        uncontrolled = indexed.get((total_rate, ratio, seed, "uncontrolled"))
        cooperative = indexed.get((total_rate, ratio, seed, "cooperative_limited"))
        if uncontrolled is None or cooperative is None:
            raise ValueError(f"Missing paired strategy for {(total_rate, ratio, seed)}")
        for metric, (source_field, scale, lower_is_better) in METRICS.items():
            uncontrolled_value = float(uncontrolled[source_field]) * scale
            cooperative_value = float(cooperative[source_field]) * scale
            output.append({
                "total_demand_veh_h": total_rate,
                "demand_ratio": ratio,
                "seed": seed,
                "metric": metric,
                "lower_is_better": lower_is_better,
                "uncontrolled_value": uncontrolled_value,
                "cooperative_value": cooperative_value,
                "paired_delta": cooperative_value - uncontrolled_value,
            })
    return output


def _interpret(ci_low: float, ci_high: float, lower_is_better: bool) -> str:
    if ci_low <= 0.0 <= ci_high:
        return "uncertain"
    improves = ci_high < 0.0 if lower_is_better else ci_low > 0.0
    return "improves" if improves else "worsens"


def summarize_paired_rows(paired_rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    rows = list(paired_rows)
    keys = sorted({
        (int(row["total_demand_veh_h"]), str(row["demand_ratio"]), str(row["metric"]))
        for row in rows
    })
    output: list[dict[str, object]] = []
    for total_rate, ratio, metric in keys:
        selected = [
            row for row in rows
            if int(row["total_demand_veh_h"]) == total_rate
            and str(row["demand_ratio"]) == ratio
            and str(row["metric"]) == metric
        ]
        selected.sort(key=lambda row: int(row["seed"]))
        deltas = [float(row["paired_delta"]) for row in selected]
        if len(deltas) < 2:
            raise ValueError(f"At least two seeds required for {(total_rate, ratio, metric)}")
        average = mean(deltas)
        standard_deviation = stdev(deltas)
        standard_error = standard_deviation / len(deltas) ** 0.5
        margin = t_critical_95(len(deltas) - 1) * standard_error
        ci_low, ci_high = average - margin, average + margin
        lower_is_better = bool(selected[0]["lower_is_better"])
        output.append({
            "total_demand_veh_h": total_rate,
            "demand_ratio": ratio,
            "metric": metric,
            "lower_is_better": lower_is_better,
            "paired_seeds": len(deltas),
            "mean_paired_delta": average,
            "sample_stddev": standard_deviation,
            "standard_error": standard_error,
            "t_critical_95": t_critical_95(len(deltas) - 1),
            "ci_95_low": ci_low,
            "ci_95_high": ci_high,
            "ci_excludes_zero": ci_low > 0.0 or ci_high < 0.0,
            "interpretation": _interpret(ci_low, ci_high, lower_is_better),
        })
    return output
