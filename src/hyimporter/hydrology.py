from __future__ import annotations

import heapq
from typing import Dict, Optional, Tuple

import numpy as np


_D8 = [
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
]


def fill_sinks_priority_flood(dem: np.ndarray) -> np.ndarray:
    h, w = dem.shape
    out = dem.astype(np.float32).copy()
    visited = np.zeros((h, w), dtype=bool)
    heap: list[tuple[float, int, int]] = []

    def push(i: int, j: int) -> None:
        visited[i, j] = True
        heapq.heappush(heap, (float(out[i, j]), i, j))

    for i in range(h):
        push(i, 0)
        if w > 1:
            push(i, w - 1)
    for j in range(1, w - 1):
        push(0, j)
        if h > 1:
            push(h - 1, j)

    while heap:
        elev, i, j = heapq.heappop(heap)
        for di, dj in _D8:
            ni, nj = i + di, j + dj
            if ni < 0 or ni >= h or nj < 0 or nj >= w or visited[ni, nj]:
                continue
            visited[ni, nj] = True
            n_elev = float(out[ni, nj])
            if n_elev < elev:
                out[ni, nj] = elev
                n_elev = elev
            heapq.heappush(heap, (n_elev, ni, nj))

    return out


def d8_flow_direction(dem: np.ndarray) -> np.ndarray:
    h, w = dem.shape
    direction = np.full((h, w), -1, dtype=np.int16)

    for i in range(h):
        for j in range(w):
            cur = dem[i, j]
            best_drop = 0.0
            best_k = -1
            for k, (di, dj) in enumerate(_D8):
                ni, nj = i + di, j + dj
                if 0 <= ni < h and 0 <= nj < w:
                    drop = cur - dem[ni, nj]
                    if drop > best_drop:
                        best_drop = drop
                        best_k = k
            direction[i, j] = best_k
    return direction


def d8_flow_accumulation(direction: np.ndarray) -> np.ndarray:
    h, w = direction.shape
    idx = np.arange(h * w, dtype=np.int32).reshape(h, w)

    downstream = np.full(h * w, -1, dtype=np.int32)
    indeg = np.zeros(h * w, dtype=np.int32)

    for i in range(h):
        for j in range(w):
            k = int(direction[i, j])
            if k < 0:
                continue
            di, dj = _D8[k]
            ni, nj = i + di, j + dj
            if 0 <= ni < h and 0 <= nj < w:
                src = int(idx[i, j])
                dst = int(idx[ni, nj])
                downstream[src] = dst
                indeg[dst] += 1

    acc = np.ones(h * w, dtype=np.float32)
    q = [int(i) for i in np.where(indeg == 0)[0]]
    head = 0
    while head < len(q):
        u = q[head]
        head += 1
        v = downstream[u]
        if v >= 0:
            acc[v] += acc[u]
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(int(v))

    return acc.reshape(h, w)


def apply_hydrology(
    y_int: np.ndarray,
    fill_sinks: bool,
    river_threshold_percentile: float,
    carve_depth: int,
    river_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    y = y_int.astype(np.float32)
    if fill_sinks:
        y = fill_sinks_priority_flood(y)

    direction = d8_flow_direction(y)
    accumulation = d8_flow_accumulation(direction)

    inferred_threshold = float(np.percentile(accumulation, river_threshold_percentile))
    inferred_rivers = accumulation >= inferred_threshold
    if river_mask is not None:
        rivers = river_mask.astype(bool) | inferred_rivers
    else:
        rivers = inferred_rivers

    carved = y.copy()
    carved[rivers] -= float(carve_depth)
    carved = np.clip(carved, 0.0, 319.0)

    return np.rint(carved).astype(np.int16), {
        "flow_direction": direction,
        "flow_accumulation": accumulation,
        "river_mask": rivers,
    }
