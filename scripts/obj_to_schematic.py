#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

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


def _occupancy_from_obj(verts: np.ndarray, faces: List[List[int]], padding: int) -> set[Tuple[int, int, int]]:
    vmin = np.min(verts, axis=0)
    shifted = verts - vmin[None, :] + float(padding)
    vox = np.rint(shifted).astype(np.int32)

    occ: set[Tuple[int, int, int]] = set((int(x), int(y), int(z)) for x, y, z in vox)
    for f in faces:
        for i in range(len(f)):
            a = shifted[f[i]]
            b = shifted[f[(i + 1) % len(f)]]
            for p in _sample_edge(a, b):
                occ.add((int(p[0]), int(p[1]), int(p[2])))
    return occ


def _to_block_arrays(
    occupied: Iterable[Tuple[int, int, int]], block_id: int
) -> tuple[int, int, int, np.ndarray, np.ndarray]:
    pts = list(occupied)
    if not pts:
        raise ValueError("No occupied voxels to export")

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    width = int(max(xs) + 1)
    height = int(max(ys) + 1)
    length = int(max(zs) + 1)

    n = width * height * length
    blocks = np.zeros(n, dtype=np.uint8)
    data = np.zeros(n, dtype=np.uint8)

    def idx(x: int, y: int, z: int) -> int:
        return x + z * width + y * width * length

    bid = int(max(0, min(255, block_id)))
    for x, y, z in pts:
        if 0 <= x < width and 0 <= y < height and 0 <= z < length:
            blocks[idx(x, y, z)] = bid

    return width, height, length, blocks, data


def _write_bo2(path: Path, occupied: Iterable[Tuple[int, int, int]], block_id: int) -> None:
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
    for x, y, z in sorted(occupied):
        lines.append(f"{x},{y},{z},{bid}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert OBJ to .schematic/.bo2 wireframe voxels")
    ap.add_argument("--obj", required=True, help="Path to input OBJ")
    ap.add_argument("--schematic", required=True, help="Path to output .schematic")
    ap.add_argument("--bo2", default="", help="Optional output .bo2 path")
    ap.add_argument("--block-id", type=int, default=1, help="Numeric block ID for voxelized export")
    ap.add_argument("--padding", type=int, default=1, help="Padding around voxelized model")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    import sys

    sys.path.insert(0, str(repo_root / "src"))
    from hyimporter.schematic import write_mcedit_schematic

    obj_path = Path(args.obj)
    schem_path = Path(args.schematic)
    bo2_path = Path(args.bo2) if args.bo2 else None

    verts, faces = _parse_obj(obj_path)
    occupied = _occupancy_from_obj(verts, faces, padding=max(0, int(args.padding)))
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
        _write_bo2(bo2_path, occupied=occupied, block_id=args.block_id)

    print(f"Wrote schematic: {schem_path}")
    if bo2_path is not None:
        print(f"Wrote bo2: {bo2_path}")
    print(f"Dims (W,H,L): {width},{height},{length} | voxels={len(occupied)}")


if __name__ == "__main__":
    main()

