from __future__ import annotations

from statistics import mean, stdev

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}
METRICS = {"total_time_spent_s": ("total_time_spent_s", 1.0, True), "network_time_spent_s": ("network_time_spent_s", 1.0, True), "insertion_wait_time_s": ("insertion_wait_time_s", 1.0, True), "unfinished_vehicles": ("unfinished_vehicles", 1.0, True), "throughput_veh_h": ("throughput", 3600.0, False)}


def paired_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    indexed = {(str(row["strategy"]), int(row["seed"])): row for row in rows}
    seeds = sorted(seed for strategy, seed in indexed if strategy == "uncontrolled")
    output: list[dict[str, object]] = []
    for strategy in sorted({str(row["strategy"]) for row in rows} - {"uncontrolled"}):
        if any((strategy, seed) not in indexed for seed in seeds):
            raise ValueError(f"Missing paired result for {strategy}")
        for metric, (field, scale, lower_is_better) in METRICS.items():
            deltas = [scale * (float(indexed[(strategy, seed)][field]) - float(indexed[("uncontrolled", seed)][field])) for seed in seeds]
            average = mean(deltas)
            if len(deltas) < 2:
                low = high = average; interpretation = "insufficient_seeds"
            else:
                margin = T95.get(len(deltas) - 1, 1.96) * stdev(deltas) / len(deltas) ** .5
                low, high = average - margin, average + margin
                interpretation = "uncertain" if low <= 0 <= high else ("improves" if (high < 0 if lower_is_better else low > 0) else "worsens")
            output.append({"strategy": strategy, "metric": metric, "paired_seeds": len(seeds), "mean_paired_delta": average, "ci_95_low": low, "ci_95_high": high, "lower_is_better": lower_is_better, "interpretation": interpretation})
    return output
