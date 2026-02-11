from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from scipy.ndimage import gaussian_filter


def fit_height_to_budget(
    height: np.ndarray,
    total_height: int = 320,
    margin_bottom: int = 12,
    margin_top: int = 24,
    p_low: float = 1.0,
    p_high: float = 99.0,
    gamma: float = 0.85,
    smooth_sigma: float = 0.0,
) -> Tuple[np.ndarray, Dict[str, float]]:
    if total_height != 320:
        raise ValueError("This pipeline assumes a fixed 320 block vertical budget")

    h = height.astype(np.float32)
    if smooth_sigma > 0:
        h = gaussian_filter(h, sigma=smooth_sigma)

    h_min = float(np.percentile(h, p_low))
    h_max = float(np.percentile(h, p_high))
    h = np.clip(h, h_min, h_max)

    eps = 1e-8
    u = (h - h_min) / (h_max - h_min + eps)
    u = np.clip(u, 0.0, 1.0)
    u = np.power(u, gamma)

    h_eff = total_height - margin_bottom - margin_top
    y = margin_bottom + np.rint(u * h_eff)
    y = np.clip(y, 0, total_height - 1).astype(np.int16)

    stats = {
        "h_min_percentile": h_min,
        "h_max_percentile": h_max,
        "y_min": int(y.min()),
        "y_max": int(y.max()),
        "h_eff": h_eff,
    }
    return y, stats
