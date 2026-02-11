from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from opensimplex import OpenSimplex
from scipy.ndimage import binary_dilation


def _noise_field(shape: Tuple[int, int], wavelength: float, seed: int) -> np.ndarray:
    h, w = shape
    gen = OpenSimplex(seed)
    xs = np.arange(h, dtype=np.float32) / max(wavelength, 1e-6)
    zs = np.arange(w, dtype=np.float32) / max(wavelength, 1e-6)
    xv, zv = np.meshgrid(xs, zs, indexing="ij")

    fn = np.vectorize(gen.noise2, otypes=[np.float32])
    n = fn(xv, zv)
    n = np.clip(n, -1.0, 1.0)
    return n.astype(np.float32)


def apply_multiscale_noise(
    y_int: np.ndarray,
    macro_amp: float,
    macro_wavelength: float,
    micro_amp: float,
    micro_wavelength: float,
    seed: int,
    water_mask: Optional[np.ndarray] = None,
    road_mask: Optional[np.ndarray] = None,
    suppress_radius: int = 5,
) -> Tuple[np.ndarray, np.ndarray]:
    y = y_int.astype(np.float32)
    macro = _noise_field(y.shape, macro_wavelength, seed) * float(macro_amp)
    micro = _noise_field(y.shape, micro_wavelength, seed + 1) * float(micro_amp)
    delta = macro + micro

    attenuation = np.ones_like(y, dtype=np.float32)
    if water_mask is not None:
        wet = binary_dilation(water_mask.astype(bool), iterations=max(0, int(suppress_radius)))
        attenuation[wet] *= 0.25
    if road_mask is not None:
        roads = binary_dilation(road_mask.astype(bool), iterations=max(0, int(suppress_radius)))
        attenuation[roads] *= 0.35

    y2 = y + delta * attenuation
    y2 = np.clip(np.rint(y2), 0, 319).astype(np.int16)
    return y2, (delta * attenuation)
