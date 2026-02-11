from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterator, List, Tuple


@dataclass(frozen=True)
class TileSpec:
    i: int
    j: int
    x0: int
    x1: int
    z0: int
    z1: int
    ex0: int
    ex1: int
    ez0: int
    ez1: int

    @property
    def core_shape(self) -> Tuple[int, int]:
        return self.x1 - self.x0, self.z1 - self.z0

    @property
    def core_slice(self):
        return slice(self.x0, self.x1), slice(self.z0, self.z1)

    @property
    def expanded_slice(self):
        return slice(self.ex0, self.ex1), slice(self.ez0, self.ez1)

    @property
    def core_in_expanded(self):
        return (
            slice(self.x0 - self.ex0, self.x1 - self.ex0),
            slice(self.z0 - self.ez0, self.z1 - self.ez0),
        )


def build_tiles(shape: Tuple[int, int], tile_size: int = 512, overlap: int = 16) -> List[TileSpec]:
    h, w = shape
    ni = int(ceil(h / float(tile_size)))
    nj = int(ceil(w / float(tile_size)))
    out: List[TileSpec] = []

    for i in range(ni):
        for j in range(nj):
            x0 = i * tile_size
            z0 = j * tile_size
            x1 = min(x0 + tile_size, h)
            z1 = min(z0 + tile_size, w)

            ex0 = max(0, x0 - overlap)
            ez0 = max(0, z0 - overlap)
            ex1 = min(h, x1 + overlap)
            ez1 = min(w, z1 + overlap)

            out.append(TileSpec(i, j, x0, x1, z0, z1, ex0, ex1, ez0, ez1))

    return out


def iter_neighbor_pairs(tiles: List[TileSpec]) -> Iterator[Tuple[TileSpec, TileSpec, str]]:
    by_ij = {(t.i, t.j): t for t in tiles}
    for t in tiles:
        r = by_ij.get((t.i + 1, t.j))
        if r is not None:
            yield t, r, "south"
        c = by_ij.get((t.i, t.j + 1))
        if c is not None:
            yield t, c, "east"
