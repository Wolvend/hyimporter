from __future__ import annotations

import gzip

import numpy as np

from hyimporter.schematic import export_tile_schematic


def test_schematic_file_created_and_gzip_header(tmp_path):
    y = np.array([[10, 11], [12, 13]], dtype=np.int16)
    labels = np.array([[0, 1], [2, 3]], dtype=np.int16)
    layers = ["grass", "dirt", "rock", "sand"]
    block_ids = {"grass": 2, "dirt": 3, "rock": 1, "sand": 12, "default": 1}

    out = tmp_path / "tile_0_0.schematic"
    export_tile_schematic(
        path=out,
        y_int=y,
        labels=labels,
        layer_names=layers,
        block_ids=block_ids,
        bottom_y=0,
        full_volume=False,
    )

    assert out.exists()
    with gzip.open(out, "rb") as f:
        data = f.read(64)
    # NBT root compound tag id = 10
    assert data[0] == 10
