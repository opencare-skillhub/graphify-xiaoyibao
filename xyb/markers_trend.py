from __future__ import annotations

import csv
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import median


@dataclass(frozen=True)
class MarkerSpec:
    key: str
    label: str
    pattern: re.Pattern[str]


MARKERS: list[MarkerSpec] = [
    MarkerSpec("ca19_9", "CA19-9", re.compile(r"ca\s*19\s*-?\s*9", re.I)),
    MarkerSpec("cea", "CEA", re.compile(r"\bcea\b", re.I)),
    MarkerSpec("afp", "AFP", re.compile(r"\bafp\b", re.I)),
    MarkerSpec("ca50", "CA50", re.compile(r"ca\s*50\b", re.I)),
    MarkerSpec("ca72_4", "CA72-4", re.compile(r"ca\s*72\s*-?\s*4", re.I)),
    MarkerSpec("ca125", "CA125", re.compile(r"ca\s*125\b", re.I)),
]

_DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-_/年](\d{1,2})[-_/月](\d{1,2})"),
    re.compile(r"(20\d{2})(\d{2})(\d{2})"),
]


def _extract_date(*texts: str) -> dt.date | None:
    for text in texts:
        for pat in _DATE_PATTERNS:
            m = pat.search(text or "")
            if not m:
                continue
            y, mth, d = map(int, m.groups())
            try:
                return dt.date(y, mth, d)
            except ValueError:
                continue
    return None


def _extract_value_for_marker(text: str, marker: MarkerSpec) -> tuple[float, str] | None:
    # 截断策略：仅取 marker 后的一段文本，避免抓到其它指标值
    m_marker = marker.pattern.search(text)
    if not m_marker:
        return None
    tail = text[m_marker.end(): m_marker.end() + 36]
    m_val = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(U/mL|IU/mL|ng/mL|ug/ml)?", tail, re.I)
    if not m_val:
        return None
    value = float(m_val.group(1))
    unit = (m_val.group(2) or "").strip() or "U/mL"
    return value, unit


def extract_marker_rows(graph: dict, markers: list[MarkerSpec] | None = None) -> list[dict]:
    markers = markers or MARKERS
    rows: list[dict] = []
    for node in graph.get("nodes", []):
        label = str(node.get("label", ""))
        source_file = str(node.get("source_file", ""))
        node_id = str(node.get("id", ""))
        for marker in markers:
            mv = _extract_value_for_marker(label, marker)
            if not mv:
                continue
            value, unit = mv
            date = _extract_date(label, source_file, node_id)
            if date is None:
                continue
            rows.append({
                "date": date,
                "marker_key": marker.key,
                "marker_label": marker.label,
                "value": value,
                "unit": unit,
                "source_file": source_file,
                "label": label,
            })
    # 去重
    dedup: dict[tuple[dt.date, str, float, str], dict] = {}
    for r in rows:
        dedup[(r["date"], r["marker_key"], r["value"], r["unit"])] = r
    return sorted(dedup.values(), key=lambda x: (x["marker_key"], x["date"], x["value"]))


def aggregate_marker_series(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, dict[dt.date, list[float]]] = {}
    for r in rows:
        grouped.setdefault(r["marker_key"], {}).setdefault(r["date"], []).append(r["value"])
    out: dict[str, list[dict]] = {}
    for marker_key, by_date in grouped.items():
        series = []
        for d in sorted(by_date):
            values = by_date[d]
            series.append({
                "date": d,
                "value_median": float(median(values)),
                "sample_count": len(values),
                "values": values,
            })
        out[marker_key] = series
    return out


def generate_markers_trend(graph_path: Path, output_dir: Path, markers: list[MarkerSpec] | None = None) -> dict:
    markers = markers or MARKERS
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    rows = extract_marker_rows(graph, markers)
    series = aggregate_marker_series(rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "tumor_markers_trend.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["marker", "date", "median_value", "unit", "samples_same_day", "raw_values"])
        marker_by_key = {m.key: m.label for m in markers}
        for key in marker_by_key:
            for p in series.get(key, []):
                w.writerow([
                    marker_by_key[key],
                    p["date"].isoformat(),
                    f'{p["value_median"]:.2f}',
                    "U/mL",
                    p["sample_count"],
                    ";".join(f"{x:.2f}" for x in p["values"]),
                ])

    summary_path = output_dir / "tumor_markers_trend_summary.md"
    marker_by_key = {m.key: m.label for m in markers}
    lines = ["# 肿瘤标志物趋势摘要", ""]
    for key in marker_by_key:
        s = series.get(key, [])
        if not s:
            lines += [f"## {marker_by_key[key]}", "- 无可用日期数据", ""]
            continue
        first = s[0]["value_median"]
        last = s[-1]["value_median"]
        delta = last - first
        trend = "上升" if delta > 0 else ("下降" if delta < 0 else "持平")
        lines += [
            f"## {marker_by_key[key]}",
            f"- 日期点数：{len(s)}",
            f"- 首次：{s[0]['date'].isoformat()} = {first:.2f}",
            f"- 最新：{s[-1]['date'].isoformat()} = {last:.2f}",
            f"- 变化：{delta:+.2f}（{trend}）",
            "",
        ]
    lines += [
        "## 文件",
        f"- CSV: `{csv_path.name}`",
        f"- PNG: `tumor_markers_trend.png`（若本地有 matplotlib 则生成）",
        "",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    png_path = output_dir / "tumor_markers_trend.png"
    plot_ok = False
    try:
        import matplotlib.pyplot as plt  # type: ignore

        plt.figure(figsize=(10, 5))
        for key, label in marker_by_key.items():
            s = series.get(key, [])
            if not s:
                continue
            xs = [p["date"] for p in s]
            ys = [p["value_median"] for p in s]
            plt.plot(xs, ys, marker="o", linewidth=1.8, label=label)
        plt.title("Tumor Marker Trends")
        plt.xlabel("Date")
        plt.ylabel("Median Value")
        plt.grid(alpha=0.25)
        plt.legend()
        plt.tight_layout()
        plt.savefig(png_path, dpi=180)
        plt.close()
        plot_ok = True
    except Exception:
        pass

    return {
        "csv": str(csv_path),
        "summary": str(summary_path),
        "plot": str(png_path) if plot_ok else None,
        "rows": len(rows),
        "markers_with_data": sum(1 for k in marker_by_key if series.get(k)),
    }

