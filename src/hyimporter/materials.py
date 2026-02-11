from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from scipy.ndimage import binary_dilation
from skimage import color


DEFAULT_LAYER_RGB = {
    "grass": (0.33, 0.57, 0.28),
    "dirt": (0.45, 0.31, 0.20),
    "rock": (0.46, 0.46, 0.46),
    "sand": (0.76, 0.71, 0.49),
    "snow": (0.92, 0.94, 0.98),
    "mud": (0.30, 0.24, 0.18),
    "gravel": (0.54, 0.52, 0.49),
}


def _hysteresis_mask(slope: np.ndarray, s_high: float, s_low: float) -> np.ndarray:
    strong = slope > float(s_high)
    weak = slope > float(s_low)
    out = strong.copy()

    # Binary hysteresis expansion: stable cliff mask without pepper noise.
    while True:
        grown = binary_dilation(out, iterations=1) & weak
        if np.array_equal(grown, out):
            break
        out = grown
    return out


def _build_weight_stack(
    weights: Dict[str, np.ndarray],
    layers: List[str],
    default_layer: str,
    shape: Tuple[int, int],
) -> np.ndarray:
    h, w = shape
    stack = np.zeros((h, w, len(layers)), dtype=np.float32)

    if not weights:
        if default_layer in layers:
            stack[..., layers.index(default_layer)] = 1.0
        return stack

    for i, name in enumerate(layers):
        if name in weights:
            arr = np.asarray(weights[name], dtype=np.float32)
            if arr.shape != shape:
                raise ValueError(f"Weight shape mismatch for {name}: {arr.shape} vs {shape}")
            stack[..., i] = np.clip(arr, 0.0, 1.0)

    sums = np.sum(stack, axis=-1, keepdims=True)
    missing = sums[..., 0] <= 1e-8
    if default_layer in layers:
        stack[..., layers.index(default_layer)][missing] = 1.0
        sums = np.sum(stack, axis=-1, keepdims=True)

    sums = np.where(sums <= 1e-8, 1.0, sums)
    return stack / sums


def _pick_by_palette_lab(
    base_labels: np.ndarray,
    colormap: np.ndarray,
    layer_names: List[str],
    cliff_mask: np.ndarray,
    snow_mask: np.ndarray,
    beach_mask: np.ndarray,
) -> Tuple[np.ndarray, Dict[str, float]]:
    layer_to_idx = {n: i for i, n in enumerate(layer_names)}
    layer_lab = {}
    for name in layer_names:
        rgb = np.array(DEFAULT_LAYER_RGB.get(name, (0.5, 0.5, 0.5)), dtype=np.float32)[None, None, :]
        layer_lab[name] = color.rgb2lab(rgb)[0, 0, :]

    img_lab = color.rgb2lab(np.clip(colormap.astype(np.float32), 0.0, 1.0))
    labels = base_labels.copy()

    def choose(mask: np.ndarray, allowed: Iterable[str]) -> None:
        names = [n for n in allowed if n in layer_to_idx]
        if not names or not np.any(mask):
            return
        cand_idx = np.array([layer_to_idx[n] for n in names], dtype=np.int16)
        cand_lab = np.stack([layer_lab[n] for n in names], axis=0)

        de = color.deltaE_ciede2000(img_lab[..., None, :], cand_lab[None, None, :, :])
        best = np.argmin(de, axis=-1)
        labels[mask] = cand_idx[best[mask]]

    choose(cliff_mask, ["rock", "snow"])
    choose(snow_mask & (~cliff_mask), ["snow", "rock"])
    choose(beach_mask & (~cliff_mask) & (~snow_mask), ["sand", "mud", "gravel"])

    normal = (~cliff_mask) & (~snow_mask) & (~beach_mask)
    choose(normal, layer_names)

    de_all = color.deltaE_ciede2000(
        img_lab,
        np.stack([layer_lab[layer_names[int(i)]] for i in labels.ravel()], axis=0).reshape(img_lab.shape),
    )

    return labels, {
        "deltaE_mean": float(np.mean(de_all)),
        "deltaE_p95": float(np.percentile(de_all, 95)),
        "deltaE_max": float(np.max(de_all)),
    }


def assign_material_labels(
    y_int: np.ndarray,
    slope: np.ndarray,
    weights: Dict[str, np.ndarray],
    masks: Dict[str, np.ndarray],
    layer_names: List[str],
    default_layer: str,
    sea_level_y: int,
    snowline_y: int,
    beach_band_dy: int,
    cliff_slope_high: float,
    cliff_slope_low: float,
    colormap: Optional[np.ndarray] = None,
    palette_match_enabled: bool = False,
) -> Tuple[np.ndarray, Dict[str, np.ndarray], Dict[str, float]]:
    shape = y_int.shape
    layer_to_idx = {name: i for i, name in enumerate(layer_names)}
    stack = _build_weight_stack(weights, layer_names, default_layer, shape)

    labels = np.argmax(stack, axis=-1).astype(np.int16)

    cliff_mask = _hysteresis_mask(slope, cliff_slope_high, cliff_slope_low)
    snow_mask = y_int >= int(snowline_y)
    beach_mask = np.abs(y_int.astype(np.int32) - int(sea_level_y)) <= int(beach_band_dy)

    rock_idx = layer_to_idx.get("rock", 0)
    snow_idx = layer_to_idx.get("snow", rock_idx)
    sand_idx = layer_to_idx.get("sand", rock_idx)
    mud_idx = layer_to_idx.get("mud", sand_idx)

    labels[cliff_mask] = rock_idx

    # Snowline gate forces snow/rock palette.
    labels[snow_mask & (~cliff_mask)] = snow_idx
    labels[snow_mask & cliff_mask] = rock_idx

    # Beach gate biases sand; river can bias mud if available.
    beach_target = beach_mask & (~cliff_mask) & (~snow_mask)
    labels[beach_target] = sand_idx

    if "river" in masks:
        river = masks["river"].astype(bool)
        labels[river & (~cliff_mask) & (~snow_mask)] = mud_idx

    de_stats: Dict[str, float] = {}
    if palette_match_enabled and colormap is not None:
        labels, de_stats = _pick_by_palette_lab(
            labels,
            colormap,
            layer_names,
            cliff_mask,
            snow_mask,
            beach_mask,
        )

    masks_out = {
        "cliff": cliff_mask,
        "snow": snow_mask,
        "beach": beach_mask,
    }

    return labels, masks_out, de_stats
