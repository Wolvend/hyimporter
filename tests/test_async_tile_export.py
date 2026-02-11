import numpy as np

from hyimporter.config import PipelineConfig
from hyimporter.export import _export_tiles


def _minimal_test_config() -> PipelineConfig:
    cfg = PipelineConfig()
    cfg.outputs.export_obj = False
    cfg.outputs.export_schematic = False
    cfg.outputs.export_bo2 = False
    cfg.mesh.export_base = False
    cfg.mesh.export_shells = False
    return cfg


def test_async_tile_export_matches_sync(tmp_path):
    cfg = _minimal_test_config()

    y = (np.arange(1030 * 1030, dtype=np.int32).reshape(1030, 1030) % 320).astype(np.int16)
    labels = np.zeros_like(y, dtype=np.int16)

    out_dir = tmp_path / "tiles"
    out_dir.mkdir(parents=True, exist_ok=True)

    warnings_sync = []
    cfg.runtime.async_tile_export = False
    rows_sync, grids_sync = _export_tiles(cfg, y, labels, out_dir, warnings_sync)

    warnings_async = []
    cfg.runtime.async_tile_export = True
    cfg.runtime.tile_workers = 4
    rows_async, grids_async = _export_tiles(cfg, y, labels, out_dir, warnings_async)

    assert rows_async == rows_sync
    assert warnings_async == warnings_sync
    assert sorted(grids_async.keys()) == sorted(grids_sync.keys())
    for key in sorted(grids_sync.keys()):
        np.testing.assert_array_equal(grids_async[key], grids_sync[key])


def test_async_tile_manifest_order_is_stable(tmp_path):
    cfg = _minimal_test_config()
    cfg.runtime.async_tile_export = True
    cfg.runtime.tile_workers = 8

    y = (np.arange(1030 * 1030, dtype=np.int32).reshape(1030, 1030) % 320).astype(np.int16)
    labels = np.zeros_like(y, dtype=np.int16)

    out_dir = tmp_path / "tiles"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows, _grids = _export_tiles(cfg, y, labels, out_dir, warnings=[])
    tile_keys = [(int(r["tile_i"]), int(r["tile_j"])) for r in rows]
    assert tile_keys == sorted(tile_keys)
