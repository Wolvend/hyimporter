from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

import imageio.v3 as iio
import numpy as np


def _to_float01(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr)
    if np.issubdtype(arr.dtype, np.integer):
        info = np.iinfo(arr.dtype)
        return arr.astype(np.float32) / float(info.max)
    arr = arr.astype(np.float32)
    amax = float(np.max(arr)) if arr.size else 0.0
    if amax > 1.0:
        arr = arr / max(amax, 1e-6)
    return np.clip(arr, 0.0, 1.0)


def load_height_image(path: Path, allow_8bit: bool = False) -> Tuple[np.ndarray, Dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Height image not found: {path}")
    arr = iio.imread(path)
    if arr.ndim == 3:
        arr = arr[..., 0]
    bit_depth: int
    if np.issubdtype(arr.dtype, np.integer):
        bit_depth = np.iinfo(arr.dtype).bits
    else:
        bit_depth = 32

    is_8bit = bit_depth <= 8
    if is_8bit and not allow_8bit:
        print(f"WARN: 8-bit heightmap detected at {path}")
        raise ValueError(
            f"8-bit heightmap detected at {path}. Abort by policy. "
            "Use --allow-8bit-height only if you explicitly accept terracing risk."
        )
    if is_8bit and allow_8bit:
        print(f"WARN: 8-bit heightmap allowed by override at {path}")

    meta = {
        "dtype": str(arr.dtype),
        "bit_depth": int(bit_depth),
        "is_8bit": bool(is_8bit),
        "shape": [int(arr.shape[0]), int(arr.shape[1])],
    }
    return arr.astype(np.float32), meta


def load_weight_maps(weights_dir: Path) -> Dict[str, np.ndarray]:
    if not weights_dir.exists():
        return {}

    out: Dict[str, np.ndarray] = {}
    for p in sorted(weights_dir.glob("*.png")):
        layer = p.stem.lower()
        out[layer] = _to_float01(iio.imread(p))
    return out


def load_masks(masks_dir: Path) -> Dict[str, np.ndarray]:
    if not masks_dir.exists():
        return {}

    out: Dict[str, np.ndarray] = {}
    for p in sorted(masks_dir.glob("*.png")):
        name = p.stem.lower()
        arr = iio.imread(p)
        if arr.ndim == 3:
            arr = arr[..., 0]
        out[name] = arr > 0
    return out


def load_colormap(color_path: Path) -> Optional[np.ndarray]:
    if not color_path.exists():
        return None
    arr = iio.imread(color_path)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.shape[-1] > 3:
        arr = arr[..., :3]
    return _to_float01(arr)


def load_object_placements(map_dir: Path) -> Dict[str, int]:
    """Best-effort ingestion of optional WMO/M2/object placement data."""

    def count_json(path: Path) -> Dict[str, int]:
        out = {"entries": 0, "wmo": 0, "m2": 0}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return out

        if isinstance(payload, list):
            out["entries"] = len(payload)
            for row in payload:
                if not isinstance(row, dict):
                    continue
                kind = str(row.get("type", row.get("kind", ""))).lower()
                if kind == "wmo":
                    out["wmo"] += 1
                elif kind == "m2":
                    out["m2"] += 1
        elif isinstance(payload, dict):
            # Common forms: { "objects": [...] } / { "wmo": [...], "m2": [...] }
            if isinstance(payload.get("objects"), list):
                out["entries"] += len(payload["objects"])
            if isinstance(payload.get("wmo"), list):
                out["wmo"] += len(payload["wmo"])
                out["entries"] += len(payload["wmo"])
            if isinstance(payload.get("m2"), list):
                out["m2"] += len(payload["m2"])
                out["entries"] += len(payload["m2"])
        return out

    def count_csv(path: Path) -> Dict[str, int]:
        out = {"entries": 0, "wmo": 0, "m2": 0}
        try:
            with path.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except Exception:
            return out
        out["entries"] = len(rows)
        for row in rows:
            kind = str(row.get("type", row.get("kind", ""))).lower()
            if kind == "wmo":
                out["wmo"] += 1
            elif kind == "m2":
                out["m2"] += 1
        return out

    roots = [
        map_dir / "objects",
        map_dir / "placements",
        map_dir / "wmo",
        map_dir / "m2",
    ]
    json_files = []
    csv_files = []
    for r in roots:
        if not r.exists():
            continue
        json_files.extend(sorted(r.glob("*.json")))
        csv_files.extend(sorted(r.glob("*.csv")))

    summary = {"source_files": 0, "entries": 0, "wmo": 0, "m2": 0}
    for p in json_files:
        c = count_json(p)
        summary["source_files"] += 1
        summary["entries"] += c["entries"]
        summary["wmo"] += c["wmo"]
        summary["m2"] += c["m2"]
    for p in csv_files:
        c = count_csv(p)
        summary["source_files"] += 1
        summary["entries"] += c["entries"]
        summary["wmo"] += c["wmo"]
        summary["m2"] += c["m2"]

    return summary
