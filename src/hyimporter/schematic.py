from __future__ import annotations

import gzip
import struct
from pathlib import Path
from typing import Dict, List

import numpy as np


def _w_u8(buf: bytearray, v: int) -> None:
    buf.extend(struct.pack(">B", int(v) & 0xFF))


def _w_i16(buf: bytearray, v: int) -> None:
    buf.extend(struct.pack(">h", int(v)))


def _w_i32(buf: bytearray, v: int) -> None:
    buf.extend(struct.pack(">i", int(v)))


def _w_name(buf: bytearray, name: str) -> None:
    nb = name.encode("utf-8")
    _w_i16(buf, len(nb))
    buf.extend(nb)


def _tag_short(buf: bytearray, name: str, value: int) -> None:
    _w_u8(buf, 2)
    _w_name(buf, name)
    _w_i16(buf, value)


def _tag_string(buf: bytearray, name: str, value: str) -> None:
    _w_u8(buf, 8)
    _w_name(buf, name)
    vb = value.encode("utf-8")
    _w_i16(buf, len(vb))
    buf.extend(vb)


def _tag_byte_array(buf: bytearray, name: str, data: bytes) -> None:
    _w_u8(buf, 7)
    _w_name(buf, name)
    _w_i32(buf, len(data))
    buf.extend(data)


def _tag_list_empty_compound(buf: bytearray, name: str) -> None:
    # TAG_List of TAG_Compound with 0 entries
    _w_u8(buf, 9)
    _w_name(buf, name)
    _w_u8(buf, 10)
    _w_i32(buf, 0)


def write_mcedit_schematic(
    path: Path,
    width: int,
    height: int,
    length: int,
    blocks: np.ndarray,
    data: np.ndarray,
) -> None:
    if blocks.dtype != np.uint8 or data.dtype != np.uint8:
        raise ValueError("blocks/data must be uint8")
    if blocks.size != width * height * length:
        raise ValueError("blocks length mismatch")
    if data.size != width * height * length:
        raise ValueError("data length mismatch")

    buf = bytearray()

    # Root TAG_Compound named "Schematic"
    _w_u8(buf, 10)
    _w_name(buf, "Schematic")

    _tag_short(buf, "Width", width)
    _tag_short(buf, "Height", height)
    _tag_short(buf, "Length", length)
    _tag_string(buf, "Materials", "Alpha")
    _tag_byte_array(buf, "Blocks", blocks.tobytes(order="C"))
    _tag_byte_array(buf, "Data", data.tobytes(order="C"))
    _tag_list_empty_compound(buf, "Entities")
    _tag_list_empty_compound(buf, "TileEntities")

    # End root compound
    _w_u8(buf, 0)

    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as f:
        f.write(buf)


def _block_id_for_label(label_name: str, block_ids: Dict[str, int]) -> int:
    if label_name in block_ids:
        return int(block_ids[label_name])
    return int(block_ids.get("default", 1))


def build_tile_block_arrays(
    y_int: np.ndarray,
    labels: np.ndarray,
    layer_names: List[str],
    block_ids: Dict[str, int],
    bottom_y: int,
    full_volume: bool,
) -> tuple[int, int, int, np.ndarray, np.ndarray]:
    width, length = int(y_int.shape[0]), int(y_int.shape[1])
    max_y = int(np.max(y_int))
    min_h = max(1, max_y + 1)
    height = min(320, min_h)

    # Flatten order x + z*W + y*W*L
    n = width * height * length
    blocks = np.zeros(n, dtype=np.uint8)
    data = np.zeros(n, dtype=np.uint8)

    # Default stone fill ID
    stone_id = int(block_ids.get("rock", block_ids.get("default", 1)))

    def idx(x: int, y: int, z: int) -> int:
        return x + z * width + y * width * length

    for x in range(width):
        for z in range(length):
            top = int(np.clip(y_int[x, z], 0, height - 1))
            lname = layer_names[int(labels[x, z])] if 0 <= int(labels[x, z]) < len(layer_names) else "default"
            top_id = _block_id_for_label(lname, block_ids)

            if full_volume:
                for yy in range(int(bottom_y), top):
                    if 0 <= yy < height:
                        blocks[idx(x, yy, z)] = stone_id
            if 0 <= top < height:
                blocks[idx(x, top, z)] = top_id

    return width, height, length, blocks, data


def export_tile_schematic(
    path: Path,
    y_int: np.ndarray,
    labels: np.ndarray,
    layer_names: List[str],
    block_ids: Dict[str, int],
    bottom_y: int,
    full_volume: bool,
) -> None:
    w, h, l, blocks, data = build_tile_block_arrays(
        y_int=y_int,
        labels=labels,
        layer_names=layer_names,
        block_ids=block_ids,
        bottom_y=bottom_y,
        full_volume=full_volume,
    )
    write_mcedit_schematic(path=path, width=w, height=h, length=l, blocks=blocks, data=data)
