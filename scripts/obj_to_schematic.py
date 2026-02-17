#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
from typing import Deque, Iterable, List, Tuple

import numpy as np


def _parse_obj(path: Path) -> tuple[np.ndarray, List[List[int]]]:
    verts: List[Tuple[float, float, float]] = []
    faces: List[List[int]] = []

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("v "):
            parts = line.split()
            if len(parts) >= 4:
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif line.startswith("f "):
            idxs: List[int] = []
            for token in line.split()[1:]:
                raw = token.split("/")[0]
                if raw:
                    idxs.append(int(raw) - 1)
            if len(idxs) >= 3:
                faces.append(idxs)

    if not verts:
        raise ValueError(f"No vertices in OBJ: {path}")

    return np.asarray(verts, dtype=np.float32), faces


def _sample_edge(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # Integer-length edge sampling for deterministic wireframe voxels.
    n = int(max(1.0, float(np.max(np.abs(b - a)))))
    t = np.linspace(0.0, 1.0, n + 1, dtype=np.float32)
    p = (a[None, :] * (1.0 - t[:, None])) + (b[None, :] * t[:, None])
    return np.rint(p).astype(np.int32)


def _triangulate_faces(faces: List[List[int]]) -> List[Tuple[int, int, int]]:
    tris: List[Tuple[int, int, int]] = []
    for face in faces:
        if len(face) < 3:
            continue
        if len(face) == 3:
            tris.append((face[0], face[1], face[2]))
            continue
        for i in range(1, len(face) - 1):
            tris.append((face[0], face[i], face[i + 1]))
    return tris


def _sample_triangle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    # Barycentric sampling densifies triangle surfaces before quantization.
    #
    # NOTE: This is intentionally conservative in sample density (step ~= 1 voxel)
    # to keep runtime reasonable for batch workloads.
    e0 = float(np.linalg.norm(a - b))
    e1 = float(np.linalg.norm(b - c))
    e2 = float(np.linalg.norm(c - a))
    max_edge = max(e0, e1, e2)
    steps = max(1, int(np.ceil(max_edge)))

    # Vectorized version of:
    #   for i in range(steps+1):
    #     for j in range(steps+1-i):
    #       ...
    ii = np.arange(steps + 1, dtype=np.float32)
    jj = np.arange(steps + 1, dtype=np.float32)
    I, J = np.meshgrid(ii, jj, indexing="ij")
    mask = (I + J) <= float(steps)

    u = (I[mask] / float(steps)).astype(np.float32)
    v = (J[mask] / float(steps)).astype(np.float32)
    w = (1.0 - u - v).astype(np.float32)

    pts = (a[None, :] * u[:, None]) + (b[None, :] * v[:, None]) + (c[None, :] * w[:, None])
    return np.rint(pts).astype(np.int32)


def _wireframe_mask(verts: np.ndarray, faces: List[List[int]], padding: int, voxel_scale: float) -> np.ndarray:
    # Quantize in world-scaled coordinates first, then shift by the integer min.
    # This is more stable than quantizing after subtracting per-file float mins.
    scaled = verts * float(voxel_scale)
    qv = np.rint(scaled).astype(np.int32)
    qmin = np.min(qv, axis=0)
    qmax = np.max(qv, axis=0)

    w = int(qmax[0] - qmin[0] + int(padding)) + 1
    h = int(qmax[1] - qmin[1] + int(padding)) + 1
    l = int(qmax[2] - qmin[2] + int(padding)) + 1
    w = max(1, w)
    h = max(1, h)
    l = max(1, l)

    occ = np.zeros((w, h, l), dtype=bool)

    # Vertices
    vox = qv - qmin[None, :] + int(padding)
    occ[vox[:, 0], vox[:, 1], vox[:, 2]] = True

    # Edges
    for f in faces:
        for i in range(len(f)):
            a = scaled[f[i]]
            b = scaled[f[(i + 1) % len(f)]]
            pts = _sample_edge(a, b)
            pl = pts - qmin[None, :] + int(padding)
            m = (
                (pl[:, 0] >= 0)
                & (pl[:, 0] < w)
                & (pl[:, 1] >= 0)
                & (pl[:, 1] < h)
                & (pl[:, 2] >= 0)
                & (pl[:, 2] < l)
            )
            if np.any(m):
                occ[pl[m, 0], pl[m, 1], pl[m, 2]] = True

    return occ


def _surface_mask(verts: np.ndarray, faces: List[List[int]], padding: int, voxel_scale: float) -> np.ndarray:
    scaled = verts * float(voxel_scale)
    qv = np.rint(scaled).astype(np.int32)
    qmin = np.min(qv, axis=0)
    qmax = np.max(qv, axis=0)

    w = int(qmax[0] - qmin[0] + int(padding)) + 1
    h = int(qmax[1] - qmin[1] + int(padding)) + 1
    l = int(qmax[2] - qmin[2] + int(padding)) + 1
    w = max(1, w)
    h = max(1, h)
    l = max(1, l)

    occ = np.zeros((w, h, l), dtype=bool)
    tris = _triangulate_faces(faces)
    for ia, ib, ic in tris:
        tri_pts = _sample_triangle(scaled[ia], scaled[ib], scaled[ic])
        pl = tri_pts - qmin[None, :] + int(padding)
        m = (
            (pl[:, 0] >= 0)
            & (pl[:, 0] < w)
            & (pl[:, 1] >= 0)
            & (pl[:, 1] < h)
            & (pl[:, 2] >= 0)
            & (pl[:, 2] < l)
        )
        if np.any(m):
            occ[pl[m, 0], pl[m, 1], pl[m, 2]] = True
    return occ


def _boundary_cells(width: int, height: int, length: int) -> Iterable[Tuple[int, int, int]]:
    for x in (0, width - 1):
        for y in range(height):
            for z in range(length):
                yield x, y, z
    for x in range(width):
        for y in (0, height - 1):
            for z in range(length):
                yield x, y, z
    for x in range(width):
        for y in range(height):
            for z in (0, length - 1):
                yield x, y, z


def _fill_closed_volume_mask(surface: np.ndarray) -> np.ndarray:
    if surface.size == 0 or not bool(surface.any()):
        return surface.astype(bool)

    width, height, length = surface.shape
    outside = np.zeros_like(surface, dtype=bool)
    q: Deque[Tuple[int, int, int]] = deque()
    for x, y, z in _boundary_cells(width, height, length):
        if not surface[x, y, z] and not outside[x, y, z]:
            outside[x, y, z] = True
            q.append((x, y, z))

    while q:
        x, y, z = q.popleft()
        for nx, ny, nz in (
            (x - 1, y, z),
            (x + 1, y, z),
            (x, y - 1, z),
            (x, y + 1, z),
            (x, y, z - 1),
            (x, y, z + 1),
        ):
            if nx < 0 or ny < 0 or nz < 0 or nx >= width or ny >= height or nz >= length:
                continue
            if not surface[nx, ny, nz] and not outside[nx, ny, nz]:
                outside[nx, ny, nz] = True
                q.append((nx, ny, nz))

    filled = surface.copy()
    filled[(~surface) & (~outside)] = True
    return filled


def _to_block_arrays(mask: np.ndarray, block_id: int) -> tuple[int, int, int, np.ndarray, np.ndarray]:
    if mask.size == 0 or not bool(mask.any()):
        raise ValueError("No occupied voxels to export")

    width, height, length = mask.shape
    n = width * height * length
    blocks = np.zeros(n, dtype=np.uint8)
    data = np.zeros(n, dtype=np.uint8)

    xs, ys, zs = np.nonzero(mask)
    idx = xs + zs * width + ys * width * length
    bid = int(max(0, min(255, block_id)))
    blocks[idx] = bid

    return int(width), int(height), int(length), blocks, data


def _write_bo2(path: Path, mask: np.ndarray, block_id: int) -> None:
    lines = [
        "[META]",
        "author=hyimporter",
        "spawnOnBlockType=2",
        "collisionPercentage=0",
        "needsFoundation=false",
        "randomRotation=false",
        "doReplaceBlocks=true",
        "",
        "[DATA]",
    ]
    bid = int(max(0, min(255, block_id)))

    xs, ys, zs = np.nonzero(mask)
    order = np.lexsort((zs, ys, xs))
    for k in order:
        lines.append(f"{int(xs[k])},{int(ys[k])},{int(zs[k])},{bid}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert OBJ to .schematic/.bo2 voxels")
    ap.add_argument("--obj", required=True, help="Path to input OBJ")
    ap.add_argument("--schematic", required=True, help="Path to output .schematic")
    ap.add_argument("--bo2", default="", help="Optional output .bo2 path")
    ap.add_argument("--block-id", type=int, default=1, help="Numeric block ID for voxelized export")
    ap.add_argument("--padding", type=int, default=1, help="Padding around voxelized model")
    ap.add_argument(
        "--voxel-scale",
        type=float,
        default=1.0,
        help="Scale factor before voxel quantization (higher keeps more shape detail)",
    )
    ap.add_argument(
        "--wireframe",
        action="store_true",
        help="Legacy mode: export vertices/edges only (no triangle fill / volume fill)",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    import sys

    sys.path.insert(0, str(repo_root / "src"))
    from hyimporter.schematic import write_mcedit_schematic

    obj_path = Path(args.obj)
    schem_path = Path(args.schematic)
    bo2_path = Path(args.bo2) if args.bo2 else None

    verts, faces = _parse_obj(obj_path)
    if args.voxel_scale <= 0:
        raise ValueError("--voxel-scale must be > 0")

    if args.wireframe:
        occupied = _wireframe_mask(
            verts,
            faces,
            padding=max(0, int(args.padding)),
            voxel_scale=float(args.voxel_scale),
        )
        mode = "wireframe"
    else:
        surface = _surface_mask(
            verts,
            faces,
            padding=max(0, int(args.padding)),
            voxel_scale=float(args.voxel_scale),
        )
        occupied = _fill_closed_volume_mask(surface)
        mode = "solid"

    width, height, length, blocks, data = _to_block_arrays(occupied, block_id=args.block_id)
    write_mcedit_schematic(
        path=schem_path,
        width=width,
        height=height,
        length=length,
        blocks=blocks,
        data=data,
    )
    if bo2_path is not None:
        _write_bo2(bo2_path, mask=occupied, block_id=args.block_id)

    print(f"Wrote schematic: {schem_path}")
    if bo2_path is not None:
        print(f"Wrote bo2: {bo2_path}")
    print(f"Mode: {mode}")
    print(f"Voxel scale: {float(args.voxel_scale):.3f}")
    print(f"Dims (W,H,L): {width},{height},{length} | voxels={int(occupied.sum())}")


if __name__ == "__main__":
    main()
