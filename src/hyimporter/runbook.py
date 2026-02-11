from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List

from .tiling import TileSpec


def write_tile_manifest(manifest_path: Path, rows: Iterable[Dict[str, object]]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def make_manifest_rows(tiles: List[TileSpec]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for t in tiles:
        out.append(
            {
                "tile_i": t.i,
                "tile_j": t.j,
                "x0": t.x0,
                "z0": t.z0,
                "x1": t.x1,
                "z1": t.z1,
                "width": t.x1 - t.x0,
                "depth": t.z1 - t.z0,
            }
        )
    return out


def write_generated_hytale_runbook(
    path: Path,
    map_name: str,
    import_height: int,
    base_fill_item_id: str,
    material_item_ids: Dict[str, str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Generated Hytale Import Runbook",
        "",
        f"Map: {map_name}",
        "",
        "## Import order",
        "1. Import base volume OBJ files first (stone/base).",
        "2. Import surface shell OBJ files second (materials).",
        "",
        "## Creative Tools settings",
        "- Open Creative Tools -> World -> Import OBJ",
        "- Height in blocks: use default below unless overridden by tile meta",
        f"- Default Height: {import_height}",
        f"- Base fill Item ID: {base_fill_item_id}",
        "- For shell OBJ files: set Fill solid OFF",
        "",
        "## Placement",
        "Use runbook/tile_manifest.csv for tile_i_j placement at x0,z0.",
        "",
        "## Material mapping",
    ]
    for k, v in sorted(material_item_ids.items()):
        lines.append(f"- {k}: {v}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
