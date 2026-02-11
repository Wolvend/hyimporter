from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np


@dataclass
class MeshData:
    vertices: List[Tuple[float, float, float]] = field(default_factory=list)
    faces: List[Tuple[int, int, int]] = field(default_factory=list)

    def add_vertex(self, x: float, y: float, z: float) -> int:
        self.vertices.append((float(x), float(y), float(z)))
        return len(self.vertices)

    def add_tri(self, a: int, b: int, c: int) -> None:
        self.faces.append((a, b, c))

    def add_quad(self, a: int, b: int, c: int, d: int) -> None:
        self.add_tri(a, b, c)
        self.add_tri(a, c, d)


def height_to_vertex_grid(height_cells: np.ndarray) -> np.ndarray:
    h, w = height_cells.shape
    v = np.zeros((h + 1, w + 1), dtype=np.float32)

    for i in range(h + 1):
        for j in range(w + 1):
            vals = []
            for di in (-1, 0):
                for dj in (-1, 0):
                    ci = i + di
                    cj = j + dj
                    if 0 <= ci < h and 0 <= cj < w:
                        vals.append(float(height_cells[ci, cj]))
            if vals:
                v[i, j] = float(np.mean(vals))
            else:
                v[i, j] = 0.0
    return v


def _maybe_add_bbox_dummy(mesh: MeshData, stabilize_bbox: Optional[dict]) -> None:
    if not stabilize_bbox or not stabilize_bbox.get("enabled", False):
        return
    mn = stabilize_bbox.get("bbox_min", [0.0, 0.0, 0.0])
    mx = stabilize_bbox.get("bbox_max", [1.0, 1.0, 1.0])
    mesh.add_vertex(float(mn[0]), float(mn[1]), float(mn[2]))
    mesh.add_vertex(float(mx[0]), float(mx[1]), float(mx[2]))


def build_base_volume_mesh(
    height_cells: np.ndarray,
    bottom_y: int,
    stabilize_bbox: Optional[dict] = None,
) -> MeshData:
    top = height_to_vertex_grid(height_cells)
    return build_base_volume_mesh_from_vertex_grid(top, bottom_y=bottom_y, stabilize_bbox=stabilize_bbox)


def build_base_volume_mesh_from_vertex_grid(
    top: np.ndarray,
    bottom_y: int,
    stabilize_bbox: Optional[dict] = None,
) -> MeshData:
    """Build terrain volume mesh from an (h+1, w+1) top vertex elevation grid."""
    if top.ndim != 2 or top.shape[0] < 2 or top.shape[1] < 2:
        raise ValueError("top vertex grid must be 2D with shape >= (2,2)")

    h = top.shape[0] - 1
    w = top.shape[1] - 1
    mesh = MeshData()

    top_idx = np.zeros((h + 1, w + 1), dtype=np.int32)
    bot_idx = np.zeros((h + 1, w + 1), dtype=np.int32)

    for i in range(h + 1):
        for j in range(w + 1):
            top_idx[i, j] = mesh.add_vertex(i, float(top[i, j]), j)
    for i in range(h + 1):
        for j in range(w + 1):
            bot_idx[i, j] = mesh.add_vertex(i, float(bottom_y), j)

    for i in range(h):
        for j in range(w):
            a = top_idx[i, j]
            b = top_idx[i + 1, j]
            c = top_idx[i + 1, j + 1]
            d = top_idx[i, j + 1]
            mesh.add_quad(a, b, c, d)

            a2 = bot_idx[i, j]
            b2 = bot_idx[i, j + 1]
            c2 = bot_idx[i + 1, j + 1]
            d2 = bot_idx[i + 1, j]
            mesh.add_quad(a2, b2, c2, d2)

    # Perimeter side walls.
    for i in range(h):
        # west
        mesh.add_quad(top_idx[i, 0], top_idx[i + 1, 0], bot_idx[i + 1, 0], bot_idx[i, 0])
        # east
        mesh.add_quad(top_idx[i, w], bot_idx[i, w], bot_idx[i + 1, w], top_idx[i + 1, w])

    for j in range(w):
        # north
        mesh.add_quad(top_idx[0, j], bot_idx[0, j], bot_idx[0, j + 1], top_idx[0, j + 1])
        # south
        mesh.add_quad(top_idx[h, j], top_idx[h, j + 1], bot_idx[h, j + 1], bot_idx[h, j])

    _maybe_add_bbox_dummy(mesh, stabilize_bbox)
    return mesh


def build_surface_shell_mesh(
    height_cells: np.ndarray,
    material_mask: np.ndarray,
    thickness: int = 1,
    stabilize_bbox: Optional[dict] = None,
) -> MeshData:
    h, w = height_cells.shape
    m = material_mask.astype(bool)
    mesh = MeshData()

    def add_cell(i: int, j: int) -> None:
        x0, x1 = float(i), float(i + 1)
        z0, z1 = float(j), float(j + 1)
        y0 = float(height_cells[i, j])
        y1 = y0 + float(thickness)

        v000 = mesh.add_vertex(x0, y0, z0)
        v100 = mesh.add_vertex(x1, y0, z0)
        v110 = mesh.add_vertex(x1, y0, z1)
        v010 = mesh.add_vertex(x0, y0, z1)

        v001 = mesh.add_vertex(x0, y1, z0)
        v101 = mesh.add_vertex(x1, y1, z0)
        v111 = mesh.add_vertex(x1, y1, z1)
        v011 = mesh.add_vertex(x0, y1, z1)

        # top + bottom
        mesh.add_quad(v001, v101, v111, v011)
        mesh.add_quad(v000, v010, v110, v100)

        # boundary-only side faces
        if i == 0 or not m[i - 1, j]:
            mesh.add_quad(v000, v100, v101, v001)
        if i == h - 1 or not m[i + 1, j]:
            mesh.add_quad(v010, v011, v111, v110)
        if j == 0 or not m[i, j - 1]:
            mesh.add_quad(v000, v001, v011, v010)
        if j == w - 1 or not m[i, j + 1]:
            mesh.add_quad(v100, v110, v111, v101)

    cells = np.argwhere(m)
    for i, j in cells:
        add_cell(int(i), int(j))

    _maybe_add_bbox_dummy(mesh, stabilize_bbox)
    return mesh


def write_obj(path: Path, mesh: MeshData) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("# Generated by hyimporter\n")
        for x, y, z in mesh.vertices:
            f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for a, b, c in mesh.faces:
            f.write(f"f {a} {b} {c}\n")
