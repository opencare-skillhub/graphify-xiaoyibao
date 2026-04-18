from __future__ import annotations

import json
from pathlib import Path

from xyb.markers_trend import generate_markers_trend


def test_generate_markers_trend_outputs_csv_and_summary(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "n1",
                        "label": "CA19-9 7.51 U/mL",
                        "source_file": "raw/2025-02-07.png",
                    },
                    {
                        "id": "n2",
                        "label": "CA19-9 10.80 U/mL",
                        "source_file": "raw/2025-06-03.png",
                    },
                    {
                        "id": "n3",
                        "label": "CEA 6.24 ng/mL",
                        "source_file": "raw/2024-11-05.png",
                    },
                ],
                "links": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    result = generate_markers_trend(graph_path=graph_path, output_dir=out_dir)

    assert (out_dir / "tumor_markers_trend.csv").exists()
    assert (out_dir / "tumor_markers_trend_summary.md").exists()
    assert result["rows"] >= 3
    text = (out_dir / "tumor_markers_trend_summary.md").read_text(encoding="utf-8")
    assert "CA19-9" in text
    assert "CEA" in text

