from pathlib import Path

import numpy as np

from hyimporter.meshing_obj import build_base_volume_mesh, write_obj


def _read_obj_vertices(path: Path):
    verts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            _, x, y, z = line.split()
            verts.append((float(x), float(y), float(z)))
    return np.array(verts, dtype=float)


def test_bbox_dummy_vertices_present(tmp_path):
    h = np.array([[10, 12], [15, 20]], dtype=np.int16)
    mesh = build_base_volume_mesh(
        h,
        bottom_y=0,
        stabilize_bbox={
            "enabled": True,
            "bbox_min": [0.0, 0.0, 0.0],
            "bbox_max": [512.0, 320.0, 512.0],
        },
    )
    out = tmp_path / "test.obj"
    write_obj(out, mesh)

    verts = _read_obj_vertices(out)
    mins = verts.min(axis=0)
    maxs = verts.max(axis=0)

    assert mins[0] <= 0.0 and mins[1] <= 0.0 and mins[2] <= 0.0
    assert maxs[0] >= 512.0 and maxs[1] >= 320.0 and maxs[2] >= 512.0
