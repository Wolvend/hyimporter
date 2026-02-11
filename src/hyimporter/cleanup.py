from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from scipy.ndimage import generic_filter, binary_dilation
from skimage.measure import label as cc_label


def majority_filter_labels(labels: np.ndarray, radius: int = 1) -> np.ndarray:
    if radius <= 0:
        return labels.astype(np.int16)

    size = radius * 2 + 1

    def mode_fn(window: np.ndarray) -> int:
        vals = window.astype(np.int32)
        vals = vals[vals >= 0]
        if vals.size == 0:
            return 0
        counts = np.bincount(vals)
        return int(np.argmax(counts))

    out = generic_filter(labels.astype(np.int16), mode_fn, size=size, mode="nearest")
    return out.astype(np.int16)


def cleanup_small_components(labels: np.ndarray, min_area: int = 32) -> Tuple[np.ndarray, float]:
    out = labels.astype(np.int16).copy()
    total_pixels = labels.size
    small_pixels = 0

    for lab in np.unique(labels):
        mask = out == lab
        comps = cc_label(mask, connectivity=1)
        n_comp = int(comps.max())
        for cid in range(1, n_comp + 1):
            comp = comps == cid
            area = int(np.sum(comp))
            if area >= min_area:
                continue

            small_pixels += area
            border = binary_dilation(comp, iterations=1) & (~comp)
            neighbors = out[border]
            neighbors = neighbors[neighbors != lab]
            if neighbors.size == 0:
                global_mode = int(np.argmax(np.bincount(out.ravel().astype(np.int32))))
                repl = global_mode
            else:
                repl = int(np.argmax(np.bincount(neighbors.astype(np.int32))))
            out[comp] = repl

    speckle_rate = float(small_pixels) / float(total_pixels if total_pixels > 0 else 1)
    return out, speckle_rate


def cleanup_labels(labels: np.ndarray, majority_radius: int, min_area: int) -> Tuple[np.ndarray, Dict[str, float]]:
    stage1 = majority_filter_labels(labels, radius=majority_radius)
    stage2, speckle_rate = cleanup_small_components(stage1, min_area=min_area)
    return stage2, {"speckle_rate": speckle_rate}
