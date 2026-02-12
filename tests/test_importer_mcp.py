from __future__ import annotations

import csv
import json
from pathlib import Path

from hyimporter.importer_mcp import evaluate_results, run_importer_mcp_review


def _write_summary(path: Path, seam: int, hmin: int, hmax: int, speckle: float) -> None:
    payload = {
        "qa": {
            "seam_max_diff": seam,
            "speckle_rate": speckle,
            "material_coverage": {"grass": 0.5, "rock": 0.5},
        },
        "height_stats": {"min": hmin, "max": hmax},
        "warnings": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manifest(path: Path) -> None:
    rows = [
        {"tile_i": "0", "tile_j": "0", "x0": "0", "z0": "0", "x1": "512", "z1": "512"},
        {"tile_i": "0", "tile_j": "1", "x0": "0", "z0": "512", "x1": "512", "z1": "1024"},
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_evaluate_results_good():
    report = evaluate_results(
        summary={
            "qa": {"seam_max_diff": 0, "speckle_rate": 0.05, "material_coverage": {"grass": 0.6, "rock": 0.4}},
            "height_stats": {"min": 0, "max": 319},
            "warnings": [],
        },
        manifest_rows=[{"tile_i": "0", "tile_j": "0", "x0": "0", "z0": "0"}],
    )
    assert report["verdict"] in {"excellent", "good"}
    assert int(report["score"]) >= 75


def test_run_importer_mcp_review_fail_on_fail(tmp_path: Path):
    map_out = tmp_path / "map"
    qa = map_out / "qa"
    runbook = map_out / "runbook"
    qa.mkdir(parents=True, exist_ok=True)
    runbook.mkdir(parents=True, exist_ok=True)

    _write_summary(qa / "summary.json", seam=2, hmin=0, hmax=319, speckle=0.05)
    _write_manifest(runbook / "tile_manifest.csv")

    try:
        run_importer_mcp_review(map_out, fail_on="fail")
        raised = False
    except RuntimeError:
        raised = True

    assert raised is True
    assert (qa / "importer_mcp_review.json").exists()
    assert (qa / "importer_mcp_review.md").exists()
