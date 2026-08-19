from __future__ import annotations

import html
from pathlib import Path


INTERPRETATION_COLORS = {
    "improves": "#0f766e",
    "worsens": "#dc2626",
    "uncertain": "#64748b",
}


def write_paired_ci_chart(
    paired_rows: list[dict[str, object]], summary_rows: list[dict[str, object]],
    metric: str, output_path: Path,
) -> Path:
    summaries = [row for row in summary_rows if row["metric"] == metric]
    summaries.sort(key=lambda row: (int(row["total_demand_veh_h"]), str(row["demand_ratio"])))
    selected_pairs = [row for row in paired_rows if row["metric"] == metric]
    extent = max(
        [abs(float(row["paired_delta"])) for row in selected_pairs]
        + [abs(float(row["ci_95_low"])) for row in summaries]
        + [abs(float(row["ci_95_high"])) for row in summaries]
        + [1.0]
    ) * 1.08
    width, row_height = 1200, 52
    height = 130 + len(summaries) * row_height
    left, right = 255, width - 70
    plot_width = right - left

    def x(value: float) -> float:
        return left + (value + extent) / (2.0 * extent) * plot_width

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="24" y="34" font-family="sans-serif" font-size="21" font-weight="700">Paired difference: {html.escape(metric)}</text>',
        '<text x="24" y="58" font-family="sans-serif" font-size="13" fill="#475569">cooperative_limited − uncontrolled（点: 各seed、太線: 平均、横線: 95% CI）</text>',
        f'<line x1="{x(0):.1f}" y1="78" x2="{x(0):.1f}" y2="{height - 38}" stroke="#0f172a" stroke-width="1.5"/>',
        f'<text x="{left}" y="82" text-anchor="middle" font-family="sans-serif" font-size="11">{-extent:.0f}</text>',
        f'<text x="{x(0):.1f}" y="82" text-anchor="middle" font-family="sans-serif" font-size="11">0</text>',
        f'<text x="{right}" y="82" text-anchor="middle" font-family="sans-serif" font-size="11">{extent:.0f}</text>',
    ]
    for index, summary in enumerate(summaries):
        center_y = 108 + index * row_height
        label = html.escape(f'{summary["total_demand_veh_h"]} veh/h  {summary["demand_ratio"]}')
        interpretation = str(summary["interpretation"])
        color = INTERPRETATION_COLORS[interpretation]
        ci_low, ci_high = float(summary["ci_95_low"]), float(summary["ci_95_high"])
        average = float(summary["mean_paired_delta"])
        parts.extend([
            f'<text x="24" y="{center_y + 5}" font-family="sans-serif" font-size="12">{label}</text>',
            f'<line x1="{left}" y1="{center_y + 18}" x2="{right}" y2="{center_y + 18}" stroke="#e2e8f0"/>',
            f'<line x1="{x(ci_low):.1f}" y1="{center_y}" x2="{x(ci_high):.1f}" y2="{center_y}" stroke="{color}" stroke-width="4"/>',
            f'<line x1="{x(ci_low):.1f}" y1="{center_y - 6}" x2="{x(ci_low):.1f}" y2="{center_y + 6}" stroke="{color}"/>',
            f'<line x1="{x(ci_high):.1f}" y1="{center_y - 6}" x2="{x(ci_high):.1f}" y2="{center_y + 6}" stroke="{color}"/>',
            f'<circle cx="{x(average):.1f}" cy="{center_y}" r="6" fill="{color}" stroke="white" stroke-width="1.5"/>',
        ])
        condition_pairs = [
            row for row in selected_pairs
            if int(row["total_demand_veh_h"]) == int(summary["total_demand_veh_h"])
            and str(row["demand_ratio"]) == str(summary["demand_ratio"])
        ]
        condition_pairs.sort(key=lambda row: int(row["seed"]))
        for seed_index, row in enumerate(condition_pairs):
            offset = (seed_index - (len(condition_pairs) - 1) / 2) * 3.0
            parts.append(
                f'<circle cx="{x(float(row["paired_delta"])):.1f}" cy="{center_y + offset:.1f}" r="2.8" fill="#0f172a" opacity="0.65"/>'
            )
        parts.append(
            f'<text x="{right + 8}" y="{center_y + 4}" font-family="sans-serif" font-size="10" fill="{color}">{interpretation}</text>'
        )
    parts.extend([
        f'<text x="{left}" y="{height - 12}" font-family="sans-serif" font-size="11" fill="#475569">← negative</text>',
        f'<text x="{right}" y="{height - 12}" text-anchor="end" font-family="sans-serif" font-size="11" fill="#475569">positive →</text>',
        "</svg>\n",
    ])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    return output_path


def generate_charts(
    paired_rows: list[dict[str, object]], summary_rows: list[dict[str, object]], output_dir: Path,
) -> list[Path]:
    metrics = sorted({str(row["metric"]) for row in summary_rows})
    return [
        write_paired_ci_chart(paired_rows, summary_rows, metric, output_dir / f"paired_{metric}_95ci.svg")
        for metric in metrics
    ]
