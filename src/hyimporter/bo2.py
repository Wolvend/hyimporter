from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np


def _block_id_for_label(label_name: str, block_ids: Dict[str, int]) -> int:
    if label_name in block_ids:
        return int(block_ids[label_name])
    return int(block_ids.get("default", 1))


def export_tile_bo2(
    path: Path,
    y_int: np.ndarray,
    labels: np.ndarray,
    layer_names: List[str],
    block_ids: Dict[str, int],
    include_subsurface: bool,
    bottom_y: int,
) -> None:
    h, w = y_int.shape
    stone_id = int(block_ids.get("rock", block_ids.get("default", 1)))

    lines: List[str] = [
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

    for x in range(h):
        for z in range(w):
            top = int(y_int[x, z])
            top = max(0, min(319, top))
            li = int(labels[x, z])
            lname = layer_names[li] if 0 <= li < len(layer_names) else "default"
            top_id = _block_id_for_label(lname, block_ids)

            if include_subsurface:
                for yy in range(int(bottom_y), top):
                    lines.append(f"{x},{yy},{z},{stone_id}")

            lines.append(f"{x},{top},{z},{top_id}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
