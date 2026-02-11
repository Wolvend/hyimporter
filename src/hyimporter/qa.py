from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .tiling import TileSpec, iter_neighbor_pairs


def _get_plt():
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None
    return plt


def height_stats(y: np.ndarray) -> Dict[str, float]:
    return {
        "min": int(np.min(y)),
        "max": int(np.max(y)),
        "mean": float(np.mean(y)),
        "p01": float(np.percentile(y, 1)),
        "p99": float(np.percentile(y, 99)),
    }


def save_height_histogram(y: np.ndarray, out_png: Path) -> None:
    plt = _get_plt()
    if plt is None:
        print("WARN: matplotlib unavailable; skipping height histogram")
        return

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 4))
    plt.hist(y.ravel(), bins=64, color="#4B6EAF", alpha=0.9)
    plt.title("Height Distribution")
    plt.xlabel("Y")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(out_png, dpi=120)
    plt.close()


def seam_diff_report(
    global_height: np.ndarray,
    tiles: List[TileSpec],
    tile_vertex_grids: Optional[Dict[Tuple[int, int], np.ndarray]] = None,
) -> Tuple[np.ndarray, int]:
    # Per-cell heatmap holding max seam mismatch touching each cell.
    seam_map = np.zeros_like(global_height, dtype=np.float32)
    max_diff = 0.0

    # Backward-compatible behavior if per-tile vertex grids are not provided.
    if tile_vertex_grids is None:
        return seam_map, 0

    for a, b, _dir in iter_neighbor_pairs(tiles):
        vg_a = tile_vertex_grids.get((a.i, a.j))
        vg_b = tile_vertex_grids.get((b.i, b.j))
        if vg_a is None or vg_b is None:
            continue

        if _dir == "east":
            # Shared vertical seam: a rightmost vertex column vs b leftmost.
            n = min(vg_a.shape[0], vg_b.shape[0])
            d = np.abs(vg_a[:n, -1] - vg_b[:n, 0]).astype(np.float32)
            local_max = float(np.max(d)) if d.size else 0.0
            # Paint seam values into adjacent border cells.
            x0 = max(a.x0, b.x0)
            x1 = min(a.x1, b.x1)
            z_left = max(0, a.z1 - 1)
            z_right = min(global_height.shape[1] - 1, b.z0)
            if x1 > x0 and d.size:
                dd = d[: x1 - x0]
                seam_map[x0:x1, z_left] = np.maximum(seam_map[x0:x1, z_left], dd)
                seam_map[x0:x1, z_right] = np.maximum(seam_map[x0:x1, z_right], dd)
        else:
            # Shared horizontal seam: a bottom vertex row vs b top row.
            n = min(vg_a.shape[1], vg_b.shape[1])
            d = np.abs(vg_a[-1, :n] - vg_b[0, :n]).astype(np.float32)
            local_max = float(np.max(d)) if d.size else 0.0
            x_top = max(0, a.x1 - 1)
            x_bottom = min(global_height.shape[0] - 1, b.x0)
            z0 = max(a.z0, b.z0)
            z1 = min(a.z1, b.z1)
            if z1 > z0 and d.size:
                dd = d[: z1 - z0]
                seam_map[x_top, z0:z1] = np.maximum(seam_map[x_top, z0:z1], dd)
                seam_map[x_bottom, z0:z1] = np.maximum(seam_map[x_bottom, z0:z1], dd)

        if local_max > max_diff:
            max_diff = local_max

    return seam_map, int(np.ceil(max_diff))


def save_seam_heatmap(seam_map: np.ndarray, out_png: Path) -> None:
    plt = _get_plt()
    if plt is None:
        print("WARN: matplotlib unavailable; skipping seam heatmap")
        return

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 8))
    plt.imshow(seam_map, cmap="magma", interpolation="nearest")
    plt.colorbar(label="Seam diff")
    plt.title("Tile Seam Diff Heatmap")
    plt.tight_layout()
    plt.savefig(out_png, dpi=120)
    plt.close()


def material_coverage(labels: np.ndarray, layer_names: List[str]) -> Dict[str, float]:
    total = float(labels.size)
    out: Dict[str, float] = {}
    for i, name in enumerate(layer_names):
        out[name] = float(np.sum(labels == i)) / total if total > 0 else 0.0
    return out


def assert_height_range(y: np.ndarray, lo: int, hi: int) -> None:
    ymin = int(np.min(y))
    ymax = int(np.max(y))
    if ymin < lo or ymax > hi:
        raise AssertionError(f"Height out of range [{lo}, {hi}] => [{ymin}, {ymax}]")


def assert_seam_threshold(max_diff: int, allowed: int) -> None:
    if int(max_diff) > int(allowed):
        raise AssertionError(f"Seam diff {max_diff} exceeds allowed {allowed}")
