from __future__ import annotations

import numpy as np

from hyimporter.bo2 import export_tile_bo2


def test_bo2_file_created_with_sections(tmp_path):
    y = np.array([[10, 11], [12, 13]], dtype=np.int16)
    labels = np.array([[0, 1], [2, 3]], dtype=np.int16)
    layers = ["grass", "dirt", "rock", "sand"]
    block_ids = {"grass": 2, "dirt": 3, "rock": 1, "sand": 12, "default": 1}

    out = tmp_path / "tile_0_0.bo2"
    export_tile_bo2(
        path=out,
        y_int=y,
        labels=labels,
        layer_names=layers,
        block_ids=block_ids,
        include_subsurface=False,
        bottom_y=0,
    )

    text = out.read_text(encoding="utf-8")
    assert "[META]" in text
    assert "[DATA]" in text
    assert "0,10,0,2" in text
