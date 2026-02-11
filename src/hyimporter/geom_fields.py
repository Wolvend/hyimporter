from __future__ import annotations

from typing import Dict

import numpy as np
from scipy.ndimage import gaussian_filter


def compute_geom_fields(y_int: np.ndarray, slope_sigma: float = 1.2) -> Dict[str, np.ndarray]:
    y = y_int.astype(np.float32)
    gy, gx = np.gradient(y)
    slope = np.sqrt(gx * gx + gy * gy)
    slope_smooth = gaussian_filter(slope, sigma=max(0.0, slope_sigma))
    aspect = np.arctan2(-gy, gx)

    return {
        "slope": slope,
        "slope_smooth": slope_smooth,
        "aspect": aspect,
        "grad_x": gx,
        "grad_y": gy,
    }
