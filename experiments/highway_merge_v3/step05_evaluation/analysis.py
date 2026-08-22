from __future__ import annotations

from statistics import mean, stdev

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
METRICS = {"total_time_spent_s": (1.0, True), "network_time_spent_s": (1.0, True), "insertion_wait_time_s": (1.0, True), "unfinished_vehicles": (1.0, True), "throughput_veh_h": (3600.0, False)}


def paired_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    indexed = {(int(r["seed"]), str(r["strategy"])): r for r in rows}
    seeds = sorted({key[0] for key in indexed})
    if any((seed, strategy) not in indexed for seed in seeds for strategy in ("uncontrolled", "cooperative_limited")):
        raise ValueError("Each seed must include uncontrolled and cooperative_limited rows")
    output = []
    for metric, (scale, lower_is_better) in METRICS.items():
        field = "throughput" if metric == "throughput_veh_h" else metric
        deltas = [scale * (float(indexed[(seed, "cooperative_limited")][field]) - float(indexed[(seed, "uncontrolled")][field])) for seed in seeds]
        average = mean(deltas)
        if len(deltas) < 2:
            low = high = average
            interpretation = "insufficient_seeds"
        else:
            margin = T95.get(len(deltas) - 1, 1.96) * stdev(deltas) / len(deltas) ** 0.5
            low, high = average - margin, average + margin
            interpretation = "uncertain" if low <= 0 <= high else ("improves" if (high < 0 if lower_is_better else low > 0) else "worsens")
        output.append({"metric": metric, "paired_seeds": len(seeds), "mean_paired_delta": average, "ci_95_low": low, "ci_95_high": high, "lower_is_better": lower_is_better, "interpretation": interpretation})
    return output
