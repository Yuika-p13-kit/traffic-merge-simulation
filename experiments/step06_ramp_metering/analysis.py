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
T_CRITICAL_95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}


def t_critical_95(df: int) -> float:
    if df < 1:
        raise ValueError("At least two paired seeds are required")
    return T_CRITICAL_95.get(df, 1.96)


def compare_with_uncontrolled(raw_rows: Iterable[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows = list(raw_rows)
    indexed: dict[tuple[int, str, int, str], dict[str, object]] = {}
    for row in rows:
        key = (int(row["total_demand_veh_h"]), str(row["demand_ratio"]), int(row["seed"]), str(row["strategy"]))
        if key in indexed:
            raise ValueError(f"Duplicate experiment row: {key}")
        indexed[key] = row
    strategies = sorted({key[3] for key in indexed if key[3] != "uncontrolled"})
    conditions = sorted({key[:3] for key in indexed})
    paired: list[dict[str, object]] = []
    for total, ratio, seed in conditions:
        baseline = indexed.get((total, ratio, seed, "uncontrolled"))
        if baseline is None:
            raise ValueError(f"Missing uncontrolled baseline for {(total, ratio, seed)}")
        for strategy in strategies:
            treatment = indexed.get((total, ratio, seed, strategy))
            if treatment is None:
                raise ValueError(f"Missing strategy {strategy} for {(total, ratio, seed)}")
            for metric, (field, scale, lower_is_better) in METRICS.items():
                base_value = float(baseline[field]) * scale
                value = float(treatment[field]) * scale
                paired.append({"strategy": strategy, "total_demand_veh_h": total, "demand_ratio": ratio,
                               "seed": seed, "metric": metric, "lower_is_better": lower_is_better,
                               "uncontrolled_value": base_value, "strategy_value": value,
                               "paired_delta": value - base_value})
    summary: list[dict[str, object]] = []
    keys = sorted({(str(r["strategy"]), int(r["total_demand_veh_h"]), str(r["demand_ratio"]), str(r["metric"])) for r in paired})
    for strategy, total, ratio, metric in keys:
        selected = [r for r in paired if (r["strategy"], r["total_demand_veh_h"], r["demand_ratio"], r["metric"]) == (strategy, total, ratio, metric)]
        deltas = [float(r["paired_delta"]) for r in selected]
        if len(deltas) < 2:
            raise ValueError(f"At least two seeds required for {(strategy, total, ratio, metric)}")
        average, sd = mean(deltas), stdev(deltas)
        se = sd / len(deltas) ** 0.5
        margin = t_critical_95(len(deltas) - 1) * se
        low, high = average - margin, average + margin
        lower = bool(selected[0]["lower_is_better"])
        interpretation = "uncertain" if low <= 0 <= high else ("improves" if (high < 0 if lower else low > 0) else "worsens")
        summary.append({"strategy": strategy, "total_demand_veh_h": total, "demand_ratio": ratio,
                        "metric": metric, "lower_is_better": lower, "paired_seeds": len(deltas),
                        "mean_paired_delta": average, "sample_stddev": sd, "standard_error": se,
                        "t_critical_95": t_critical_95(len(deltas) - 1), "ci_95_low": low,
                        "ci_95_high": high, "interpretation": interpretation})
    return paired, summary
