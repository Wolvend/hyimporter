import numpy as np

from hyimporter.meshing_obj import height_to_vertex_grid
from hyimporter.qa import seam_diff_report
from hyimporter.tiling import build_tiles


def test_seam_diff_zero_with_global_processing():
    h, w = 1030, 1030
    y = np.arange(h * w, dtype=np.int32).reshape(h, w) % 320
    tiles = build_tiles(y.shape, tile_size=512, overlap=16)
    vertex_grids = {}
    for t in tiles:
        ex = y[t.ex0 : t.ex1, t.ez0 : t.ez1]
        ex_v = height_to_vertex_grid(ex)
        cx0 = t.x0 - t.ex0
        cz0 = t.z0 - t.ez0
        ch = t.x1 - t.x0
        cw = t.z1 - t.z0
        vertex_grids[(t.i, t.j)] = ex_v[cx0 : cx0 + ch + 1, cz0 : cz0 + cw + 1]

    seam_map, seam_max = seam_diff_report(y.astype(np.int16), tiles, tile_vertex_grids=vertex_grids)
    assert seam_map.shape == y.shape
    assert seam_max == 0


def test_seam_diff_detects_mismatch():
    h, w = 520, 520
    y = np.arange(h * w, dtype=np.int32).reshape(h, w) % 320
    tiles = build_tiles(y.shape, tile_size=512, overlap=16)
    vertex_grids = {}
    for t in tiles:
        ex = y[t.ex0 : t.ex1, t.ez0 : t.ez1]
        ex_v = height_to_vertex_grid(ex)
        cx0 = t.x0 - t.ex0
        cz0 = t.z0 - t.ez0
        ch = t.x1 - t.x0
        cw = t.z1 - t.z0
        vertex_grids[(t.i, t.j)] = ex_v[cx0 : cx0 + ch + 1, cz0 : cz0 + cw + 1]

    # Intentionally perturb right tile seam edge.
    if (0, 1) in vertex_grids:
        vertex_grids[(0, 1)][:, 0] += 3.0

    _seam_map, seam_max = seam_diff_report(y.astype(np.int16), tiles, tile_vertex_grids=vertex_grids)
    assert seam_max > 0
