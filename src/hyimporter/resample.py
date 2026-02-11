from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from skimage.transform import resize, resize_local_mean


def resample_height(height: np.ndarray, target_shape: Tuple[int, int]) -> np.ndarray:
    if height.shape == target_shape:
        return height.astype(np.float32)
    out = resize(
        height,
        output_shape=target_shape,
        order=3,
        mode="reflect",
        anti_aliasing=True,
        preserve_range=True,
    )
    return out.astype(np.float32)


def resample_weights(weights: Dict[str, np.ndarray], target_shape: Tuple[int, int]) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}
    for k, v in weights.items():
        if v.shape != target_shape:
            if target_shape[0] <= v.shape[0] and target_shape[1] <= v.shape[1]:
                # Area-style downsampling to preserve fractional coverage.
                v2 = resize_local_mean(v, output_shape=target_shape)
            else:
                v2 = resize(
                    v,
                    output_shape=target_shape,
                    order=1,
                    mode="reflect",
                    anti_aliasing=True,
                    preserve_range=True,
                )
        else:
            v2 = v
        out[k] = np.clip(v2.astype(np.float32), 0.0, 1.0)
    return renormalize_weights(out)


def resample_masks(masks: Dict[str, np.ndarray], target_shape: Tuple[int, int]) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}
    for k, v in masks.items():
        if v.shape != target_shape:
            v2 = resize(
                v.astype(np.float32),
                output_shape=target_shape,
                order=0,
                mode="edge",
                anti_aliasing=False,
                preserve_range=True,
            )
            out[k] = v2 > 0.5
        else:
            out[k] = v.astype(bool)
    return out


def resample_colormap(colormap: np.ndarray, target_shape: Tuple[int, int]) -> np.ndarray:
    if colormap.shape[:2] == target_shape:
        return colormap.astype(np.float32)

    h, w = target_shape
    out = resize(
        colormap,
        output_shape=(h, w, 3),
        order=1,
        mode="reflect",
        anti_aliasing=True,
        preserve_range=True,
    )
    return np.clip(out.astype(np.float32), 0.0, 1.0)


def renormalize_weights(weights: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    if not weights:
        return weights
    layers = sorted(weights.keys())
    stack = np.stack([weights[k] for k in layers], axis=-1).astype(np.float32)
    denom = np.sum(stack, axis=-1, keepdims=True)
    denom = np.where(denom <= 1e-8, 1.0, denom)
    stack = stack / denom
    return {k: stack[..., i] for i, k in enumerate(layers)}
