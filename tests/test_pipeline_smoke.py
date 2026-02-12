from __future__ import annotations

import csv
from pathlib import Path

import imageio.v3 as iio
import numpy as np

from hyimporter.config import PipelineConfig
from hyimporter.export import run_pipeline


def _write_height_16bit(path: Path, h: int = 520, w: int = 520) -> None:
    # Deterministic terrain with varied gradient and low-frequency wave patterns.
    x = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    z = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    terrain = 6000.0 * x + 2500.0 * np.sin(2.0 * np.pi * z) + 900.0 * np.cos(4.0 * np.pi * x * z)

    # Normalize to uint16 full range for realistic 16-bit input handling.
    tmin = float(np.min(terrain))
    tmax = float(np.max(terrain))
    scaled = (terrain - tmin) / max(tmax - tmin, 1e-6)
    arr16 = np.clip(np.round(scaled * 65535.0), 0, 65535).astype(np.uint16)
    iio.imwrite(path, arr16)


def _build_cfg(input_root: Path, output_root: Path, async_tiles: bool) -> PipelineConfig:
    cfg = PipelineConfig()
    cfg.project.map_name = "smoke_map"
    cfg.paths.input_root = str(input_root)
    cfg.paths.output_root = str(output_root)

    # Keep smoke test quick while still exercising deterministic tiling + QA.
    cfg.outputs.export_obj = False
    cfg.outputs.export_schematic = False
    cfg.outputs.export_bo2 = False
    cfg.mesh.export_base = False
    cfg.mesh.export_shells = False

    cfg.runtime.async_tile_export = async_tiles
    cfg.runtime.tile_workers = 4
    return cfg


def _load_manifest_rows(manifest_csv: Path) -> list[dict[str, str]]:
    with manifest_csv.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _tile_index_projection(rows: list[dict[str, str]]) -> list[tuple[int, int, int, int]]:
    out = []
    for r in rows:
        out.append((int(r["tile_i"]), int(r["tile_j"]), int(r["x0"]), int(r["z0"])))
    return sorted(out)


def test_pipeline_smoke_sync_vs_async(tmp_path: Path):
    input_root = tmp_path / "input"
    map_root = input_root / "smoke_map"
    (map_root / "height").mkdir(parents=True, exist_ok=True)
    _write_height_16bit(map_root / "height" / "height.png")

    cfg_sync = _build_cfg(input_root=input_root, output_root=tmp_path / "out_sync", async_tiles=False)
    summary_sync = run_pipeline(cfg_sync)

    cfg_async = _build_cfg(input_root=input_root, output_root=tmp_path / "out_async", async_tiles=True)
    summary_async = run_pipeline(cfg_async)

    # Core safety guarantees.
    assert int(summary_sync["height_stats"]["min"]) >= 0
    assert int(summary_sync["height_stats"]["max"]) <= 319
    assert int(summary_sync["qa"]["seam_max_diff"]) == 0

    # Deterministic sync/async parity.
    assert summary_sync["height_stats"] == summary_async["height_stats"]
    assert summary_sync["height_fit"] == summary_async["height_fit"]
    assert summary_sync["qa"]["seam_max_diff"] == summary_async["qa"]["seam_max_diff"]
    assert summary_sync["qa"]["material_coverage"] == summary_async["qa"]["material_coverage"]

    manifest_sync = (
        Path(cfg_sync.paths.output_root) / cfg_sync.project.map_name / "runbook" / "tile_manifest.csv"
    )
    manifest_async = (
        Path(cfg_async.paths.output_root) / cfg_async.project.map_name / "runbook" / "tile_manifest.csv"
    )
    assert manifest_sync.exists()
    assert manifest_async.exists()

    rows_sync = _load_manifest_rows(manifest_sync)
    rows_async = _load_manifest_rows(manifest_async)
    assert _tile_index_projection(rows_sync) == _tile_index_projection(rows_async)
