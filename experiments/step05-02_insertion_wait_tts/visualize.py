from __future__ import annotations

import csv
import html
from pathlib import Path


COLORS = {"uncontrolled": "#64748b", "cooperative_limited": "#0f766e"}


def write_metric_chart(summary_csv: Path, output_path: Path, metric: str) -> Path:
    with summary_csv.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise ValueError(f"No rows in {summary_csv}")
    values = [float(row[metric]) for row in rows]
    maximum = max(values) or 1.0
    width, height = 1100, max(360, 105 + 34 * len(rows))
    plot_width = width - 390
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="24" y="38" font-family="sans-serif" font-size="22" font-weight="700">{html.escape(metric)}</text>',
        '<text x="24" y="62" font-family="sans-serif" font-size="13" fill="#475569">需要条件・戦略別（複数 seed 平均）</text>',
    ]
    for index, (row, value) in enumerate(zip(rows, values, strict=True)):
        y = 88 + index * 34
        bar_width = value / maximum * plot_width
        condition = html.escape(f'{row["total_demand_veh_h"]} veh/h  {row["demand_ratio"]}  {row["strategy"]}')
        color = COLORS.get(row["strategy"], "#7c3aed")
        parts.extend([
            f'<text x="24" y="{y + 15}" font-family="sans-serif" font-size="12">{condition}</text>',
            f'<rect x="350" y="{y}" width="{bar_width:.1f}" height="20" rx="3" fill="{color}"/>',
            f'<text x="{355 + bar_width:.1f}" y="{y + 15}" font-family="sans-serif" font-size="12">{value:.1f}</text>',
        ])
    parts.append("</svg>\n")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    return output_path


def generate_charts(summary_csv: Path, output_dir: Path) -> list[Path]:
    metrics = [
        "mean_total_time_spent_s", "mean_network_time_spent_s",
        "mean_insertion_wait_time_s", "mean_main_insertion_wait_time_s",
        "mean_side_insertion_wait_time_s", "mean_pending_vehicles_end",
        "mean_throughput_veh_h",
    ]
    return [write_metric_chart(summary_csv, output_dir / f"{metric}.svg", metric) for metric in metrics]
