from __future__ import annotations

import csv
from pathlib import Path


def generate(summary_csv: Path, output: Path) -> Path:
    with summary_csv.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    maximum = max(float(row["mean_total_time_spent_s"]) for row in rows)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="300" viewBox="0 0 900 300">', '<rect width="100%" height="100%" fill="#ffffff"/>', '<text x="40" y="38" font-family="sans-serif" font-size="22" font-weight="700">v3 Step 5 — Complete TTS</text>', '<text x="40" y="62" font-family="sans-serif" font-size="14">3,950 veh/h, main:ramp=1:2, five paired seeds</text>']
    for index, row in enumerate(rows):
        value = float(row["mean_total_time_spent_s"]); y = 100 + index * 80; width = value / maximum * 580; color = "#64748b" if row["strategy"] == "uncontrolled" else "#0f766e"
        parts += [f'<text x="40" y="{y + 24}" font-family="sans-serif" font-size="16">{row["strategy"]}</text>', f'<rect x="260" y="{y}" width="{width:.1f}" height="34" fill="{color}"/>', f'<text x="{270 + width:.1f}" y="{y + 23}" font-family="sans-serif" font-size="15">{value:,.0f} s</text>']
    parts.append('</svg>\n'); output.parent.mkdir(parents=True, exist_ok=True); output.write_text("\n".join(parts), encoding="utf-8")
    return output
