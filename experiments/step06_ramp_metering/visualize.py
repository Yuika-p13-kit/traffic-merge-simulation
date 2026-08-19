from __future__ import annotations

import html
from pathlib import Path

COLORS = {"improves": "#0f766e", "worsens": "#dc2626", "uncertain": "#64748b"}


def generate_charts(paired: list[dict[str, object]], summary: list[dict[str, object]], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for metric in sorted({str(row["metric"]) for row in summary}):
        rows = [row for row in summary if row["metric"] == metric]
        rows.sort(key=lambda row: (str(row["strategy"]), int(row["total_demand_veh_h"]), str(row["demand_ratio"])))
        values = [abs(float(row[key])) for row in rows for key in ("ci_95_low", "ci_95_high")]
        extent = max(values + [1.0]) * 1.08
        width, row_height, left, right = 1300, 38, 360, 1160
        height = 105 + row_height * len(rows)
        x = lambda value: left + (value + extent) / (2 * extent) * (right - left)
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
               '<rect width="100%" height="100%" fill="#f8fafc"/>',
               f'<text x="20" y="30" font-family="sans-serif" font-size="20" font-weight="700">{html.escape(metric)}: strategy − uncontrolled</text>',
               f'<line x1="{x(0):.1f}" y1="52" x2="{x(0):.1f}" y2="{height-20}" stroke="#0f172a"/>']
        for index, row in enumerate(rows):
            y = 72 + index * row_height
            color = COLORS[str(row["interpretation"])]
            label = f'{row["strategy"]} | {row["total_demand_veh_h"]} | {row["demand_ratio"]}'
            svg.extend([f'<text x="20" y="{y+4}" font-family="sans-serif" font-size="11">{html.escape(label)}</text>',
                        f'<line x1="{x(float(row["ci_95_low"])):.1f}" y1="{y}" x2="{x(float(row["ci_95_high"])):.1f}" y2="{y}" stroke="{color}" stroke-width="4"/>',
                        f'<circle cx="{x(float(row["mean_paired_delta"])):.1f}" cy="{y}" r="5" fill="{color}"/>',
                        f'<text x="1170" y="{y+4}" font-family="sans-serif" font-size="10" fill="{color}">{row["interpretation"]}</text>'])
        svg.append('</svg>\n')
        path = output_dir / f"paired_{metric}_95ci.svg"
        path.write_text("\n".join(svg), encoding="utf-8")
        paths.append(path)
    return paths
