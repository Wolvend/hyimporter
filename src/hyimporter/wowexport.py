from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple


ADT_OBJ_RE = re.compile(r"^adt_(?P<i>\d+)_(?P<j>\d+)\.obj$", re.IGNORECASE)
WIN_DRIVE_RE = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")


def _expand(path: str | Path) -> Path:
    raw = str(path)
    m = WIN_DRIVE_RE.match(raw)
    if m:
        drive = m.group("drive").lower()
        rest = m.group("rest").replace("\\", "/")
        raw = f"/mnt/{drive}/{rest}"
    return Path(raw).expanduser().resolve()


def _norm_relpath(s: str) -> str:
    # wow.export emits Windows-style relative paths inside CSV.
    return s.strip().replace("\\", "/")


@dataclass(frozen=True)
class AdtTileRef:
    i: int
    j: int
    obj_path: Path
    mtl_path: Path
    tex_path: Path
    placements_csv: Path


def iter_adt_tiles(map_dir: str | Path) -> Iterator[AdtTileRef]:
    root = _expand(map_dir)
    if not root.exists() or not root.is_dir():
        return

    for p in sorted(root.iterdir(), key=lambda q: q.name.lower()):
        if not p.is_file():
            continue
        m = ADT_OBJ_RE.match(p.name)
        if not m:
            continue
        i = int(m.group("i"))
        j = int(m.group("j"))
        base = f"adt_{i}_{j}"
        yield AdtTileRef(
            i=i,
            j=j,
            obj_path=p,
            mtl_path=root / f"{base}.mtl",
            tex_path=root / f"tex_{i}_{j}.png",
            placements_csv=root / f"{base}_ModelPlacementInformation.csv",
        )


def obj_bbox_minmax(path: Path) -> tuple[tuple[float, float, float], tuple[float, float, float], int]:
    vmin = [float("inf"), float("inf"), float("inf")]
    vmax = [float("-inf"), float("-inf"), float("-inf")]
    seen = 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.startswith("v "):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            x = float(parts[1])
            y = float(parts[2])
            z = float(parts[3])
            if x < vmin[0]:
                vmin[0] = x
            if y < vmin[1]:
                vmin[1] = y
            if z < vmin[2]:
                vmin[2] = z
            if x > vmax[0]:
                vmax[0] = x
            if y > vmax[1]:
                vmax[1] = y
            if z > vmax[2]:
                vmax[2] = z
            seen += 1
    if seen == 0:
        raise ValueError(f"No vertices found in OBJ: {path}")
    return (vmin[0], vmin[1], vmin[2]), (vmax[0], vmax[1], vmax[2]), seen


def list_wowexport_maps(export_root: str | Path, limit: int = 100) -> Dict[str, object]:
    root = _expand(export_root)
    maps_dir = root / "maps"
    if limit <= 0:
        raise ValueError("limit must be > 0")

    if not maps_dir.exists() or not maps_dir.is_dir():
        return {
            "export_root": str(root),
            "maps_dir": str(maps_dir),
            "exists": False,
            "maps": [],
            "total_maps": 0,
            "returned_maps": 0,
            "truncated": False,
        }

    dirs = sorted([p for p in maps_dir.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    out: List[Dict[str, object]] = []
    for p in dirs[:limit]:
        tile_count = sum(1 for _ in iter_adt_tiles(p))
        out.append(
            {
                "map_name": p.name,
                "map_path": str(p),
                "tile_obj_count": int(tile_count),
                "has_foliage_dir": (p / "foliage").exists(),
            }
        )

    return {
        "export_root": str(root),
        "maps_dir": str(maps_dir),
        "exists": True,
        "maps": out,
        "total_maps": len(dirs),
        "returned_maps": len(out),
        "truncated": len(dirs) > len(out),
    }


def parse_model_placements_csv(path: Path, max_rows: int = 0) -> Dict[str, object]:
    """Parse wow.export placement CSV (semicolon-delimited) into a lightweight summary.

    Returns:
      - ok: bool
      - path: str
      - rows: int
      - models_sample: list[str]
      - errors: list[str]
    """

    errors: List[str] = []
    models: set[str] = set()
    rows = 0

    if not path.exists():
        return {"ok": False, "path": str(path), "rows": 0, "models_sample": [], "errors": ["missing file"]}

    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                rows += 1
                mf = (row.get("ModelFile") or "").strip()
                if mf:
                    models.add(_norm_relpath(mf))
                if max_rows and rows >= max_rows:
                    break
    except Exception as exc:  # noqa: BLE001 - parsing should be resilient
        errors.append(str(exc))

    sample = sorted(models)[:100]
    return {"ok": len(errors) == 0, "path": str(path), "rows": rows, "models_sample": sample, "errors": errors}


def resolve_model_path(export_root: str | Path, map_dir: str | Path, model_file: str) -> Path:
    # ModelFile entries are relative to the tile folder.
    root = _expand(export_root)
    base = _expand(map_dir)
    rel = _norm_relpath(model_file)
    abs_path = (base / rel).resolve()
    # Best-effort: if the resolved path is outside export_root due to weirdness,
    # fall back to joining export_root with a normalized path fragment.
    try:
        abs_path.relative_to(root)
        return abs_path
    except Exception:
        # Strip any leading ../
        rel_clean = rel.lstrip("./")
        while rel_clean.startswith("../"):
            rel_clean = rel_clean[3:]
        return (root / rel_clean).resolve()


def scan_wowexport_map(
    map_dir: str | Path,
    max_tile_details: int = 100,
    compute_bboxes: bool = True,
    parse_placements: bool = True,
    max_placement_rows_per_file: int = 0,
) -> Dict[str, object]:
    root = _expand(map_dir)
    if not root.exists() or not root.is_dir():
        return {"ok": False, "map_dir": str(root), "errors": ["map_dir does not exist or is not a directory"]}

    tiles = list(iter_adt_tiles(root))
    tile_count = len(tiles)
    if tile_count == 0:
        return {"ok": False, "map_dir": str(root), "errors": ["no adt_*.obj tiles found"]}

    is_ = [t.i for t in tiles]
    js_ = [t.j for t in tiles]
    missing_tex = 0
    missing_mtl = 0
    missing_placements = 0
    placement_rows_total = 0
    models_unique: set[str] = set()

    tile_details: List[Dict[str, object]] = []
    for idx, t in enumerate(tiles):
        if not t.tex_path.exists():
            missing_tex += 1
        if not t.mtl_path.exists():
            missing_mtl += 1
        if not t.placements_csv.exists():
            missing_placements += 1

        bbox = None
        if compute_bboxes:
            try:
                vmin, vmax, vcount = obj_bbox_minmax(t.obj_path)
                bbox = {
                    "vmin": {"x": vmin[0], "y": vmin[1], "z": vmin[2]},
                    "vmax": {"x": vmax[0], "y": vmax[1], "z": vmax[2]},
                    "vertex_count": int(vcount),
                    "size": {"x": vmax[0] - vmin[0], "y": vmax[1] - vmin[1], "z": vmax[2] - vmin[2]},
                }
            except Exception:
                bbox = None

        placements_summary = None
        if parse_placements and t.placements_csv.exists():
            placements_summary = parse_model_placements_csv(t.placements_csv, max_rows=max_placement_rows_per_file)
            if placements_summary.get("ok"):
                placement_rows_total += int(placements_summary.get("rows") or 0)
                for mf in placements_summary.get("models_sample") or []:
                    models_unique.add(str(mf))

        if idx < max_tile_details:
            tile_details.append(
                {
                    "i": int(t.i),
                    "j": int(t.j),
                    "obj_path": str(t.obj_path),
                    "mtl_path": str(t.mtl_path),
                    "tex_path": str(t.tex_path),
                    "placements_csv": str(t.placements_csv),
                    "has_mtl": bool(t.mtl_path.exists()),
                    "has_tex": bool(t.tex_path.exists()),
                    "has_placements_csv": bool(t.placements_csv.exists()),
                    "bbox": bbox,
                    "placements": placements_summary,
                }
            )

    return {
        "ok": True,
        "map_dir": str(root),
        "tile_count": int(tile_count),
        "tile_index_range": {
            "min_i": int(min(is_)),
            "max_i": int(max(is_)),
            "min_j": int(min(js_)),
            "max_j": int(max(js_)),
        },
        "missing": {
            "mtl": int(missing_mtl),
            "tex": int(missing_tex),
            "placements_csv": int(missing_placements),
        },
        "placements": {
            "enabled": bool(parse_placements),
            "rows_total": int(placement_rows_total),
            "unique_models_sample": sorted(models_unique)[:200],
            "unique_models_sample_count": int(len(models_unique)),
        },
        "tile_details": tile_details,
        "tile_details_truncated": tile_count > len(tile_details),
    }


def iter_all_placement_csvs(map_dir: str | Path) -> Iterator[Path]:
    root = _expand(map_dir)
    if not root.exists() or not root.is_dir():
        return
    for p in sorted(root.iterdir(), key=lambda q: q.name.lower()):
        if p.is_file() and p.name.lower().endswith("_modelplacementinformation.csv"):
            yield p


def collect_unique_models_from_map(
    export_root: str | Path,
    map_dir: str | Path,
    max_csv_files: int = 0,
    max_rows_per_csv: int = 0,
    name_filter: str = "",
) -> Dict[str, object]:
    root = _expand(map_dir)
    ex_root = _expand(export_root)

    filter_norm = name_filter.strip().lower()
    model_abs: set[Path] = set()
    missing: List[str] = []
    csv_count = 0
    row_total = 0

    for csv_path in iter_all_placement_csvs(root):
        if max_csv_files and csv_count >= max_csv_files:
            break
        csv_count += 1

        try:
            with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                reader = csv.DictReader(f, delimiter=";")
                rows_in_file = 0
                for row in reader:
                    rows_in_file += 1
                    row_total += 1
                    mf = (row.get("ModelFile") or "").strip()
                    if not mf:
                        continue
                    mf_norm = _norm_relpath(mf)
                    if filter_norm and filter_norm not in mf_norm.lower():
                        continue
                    abs_model = resolve_model_path(ex_root, root, mf_norm)
                    if abs_model.exists() and abs_model.suffix.lower() == ".obj":
                        model_abs.add(abs_model)
                    else:
                        if len(missing) < 25:
                            missing.append(mf_norm)
                    if max_rows_per_csv and rows_in_file >= max_rows_per_csv:
                        break
        except Exception:
            continue

    models_sorted = sorted(model_abs, key=lambda p: p.as_posix().lower())
    rel_sorted: List[str] = []
    for m in models_sorted:
        try:
            rel_sorted.append(m.relative_to(ex_root).as_posix())
        except Exception:
            rel_sorted.append(m.as_posix())

    return {
        "export_root": str(ex_root),
        "map_dir": str(root),
        "csv_files_scanned": int(csv_count),
        "rows_scanned": int(row_total),
        "unique_models": rel_sorted,
        "unique_models_count": int(len(rel_sorted)),
        "missing_models_sample": missing,
    }


def export_map_placements_manifest(
    export_root: str | Path,
    map_dir: str | Path,
    out_root: str | Path,
    name_filter: str = "",
    max_csv_files: int = 0,
    max_rows_per_csv: int = 0,
    include_missing_models: bool = False,
) -> Dict[str, object]:
    """Export full placement rows (streamed) into per-tile JSONL plus a summary manifest.

    Writes:
      - <out_root>/placements/<adt_i_j>.jsonl
      - <out_root>/wowexport_placements_manifest.json
    """

    def _parse_float(s: str) -> float:
        try:
            return float(str(s).strip())
        except Exception:
            return 0.0

    def _parse_int(s: str) -> int:
        try:
            return int(float(str(s).strip()))
        except Exception:
            return 0

    ex_root = _expand(export_root)
    root = _expand(map_dir)
    dst_root = _expand(out_root)
    if not ex_root.exists() or not ex_root.is_dir():
        raise FileNotFoundError(f"export_root not found: {ex_root}")
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"map_dir not found: {root}")

    dst_root.mkdir(parents=True, exist_ok=True)
    placements_dir = dst_root / "placements"
    placements_dir.mkdir(parents=True, exist_ok=True)

    filter_norm = name_filter.strip().lower()
    csv_count = 0
    rows_total = 0
    rows_written_total = 0
    missing_models = 0
    missing_models_sample: List[str] = []
    outputs: List[Dict[str, object]] = []

    for csv_path in iter_all_placement_csvs(root):
        if max_csv_files and csv_count >= max_csv_files:
            break
        csv_count += 1

        tile_base = csv_path.name
        suffix = "_ModelPlacementInformation.csv"
        if tile_base.lower().endswith(suffix.lower()):
            tile_base = tile_base[: -len(suffix)]
        out_path = placements_dir / f"{tile_base}.jsonl"

        written = 0
        seen = 0
        try:
            with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f_in, out_path.open(
                "w", encoding="utf-8", newline="\n"
            ) as f_out:
                reader = csv.DictReader(f_in, delimiter=";")
                for row in reader:
                    seen += 1
                    rows_total += 1

                    mf_raw = (row.get("ModelFile") or "").strip()
                    if not mf_raw:
                        if max_rows_per_csv and seen >= max_rows_per_csv:
                            break
                        continue

                    mf_norm = _norm_relpath(mf_raw)
                    if filter_norm and filter_norm not in mf_norm.lower():
                        if max_rows_per_csv and seen >= max_rows_per_csv:
                            break
                        continue

                    abs_model = resolve_model_path(ex_root, root, mf_norm)
                    model_exists = abs_model.exists() and abs_model.suffix.lower() == ".obj"
                    if not model_exists:
                        missing_models += 1
                        if len(missing_models_sample) < 25:
                            missing_models_sample.append(mf_norm)
                        if not include_missing_models:
                            if max_rows_per_csv and seen >= max_rows_per_csv:
                                break
                            continue

                    try:
                        model_rel = abs_model.relative_to(ex_root).as_posix()
                    except Exception:
                        model_rel = abs_model.as_posix()

                    bo2_rel = (Path("models") / Path(model_rel)).with_suffix(".bo2").as_posix()
                    schem_rel = (Path("models") / Path(model_rel)).with_suffix(".schematic").as_posix()

                    rec = {
                        "tile": {"name": tile_base},
                        "model": {"file": mf_norm, "rel": model_rel, "exists": bool(model_exists)},
                        "artifact": {"bo2": bo2_rel, "schematic": schem_rel},
                        "position": {
                            "x": _parse_float(row.get("PositionX") or ""),
                            "y": _parse_float(row.get("PositionY") or ""),
                            "z": _parse_float(row.get("PositionZ") or ""),
                        },
                        "rotation": {
                            # wow.export emits RotationW but often leaves it blank; keep raw values.
                            "x": _parse_float(row.get("RotationX") or ""),
                            "y": _parse_float(row.get("RotationY") or ""),
                            "z": _parse_float(row.get("RotationZ") or ""),
                            "w": _parse_float(row.get("RotationW") or ""),
                        },
                        "scale": _parse_float(row.get("ScaleFactor") or "1"),
                        "meta": {
                            "type": (row.get("Type") or "").strip(),
                            "model_id": _parse_int(row.get("ModelId") or ""),
                            "file_data_id": _parse_int(row.get("FileDataID") or ""),
                            "doodad_set_indexes": (row.get("DoodadSetIndexes") or "").strip(),
                            "doodad_set_names": (row.get("DoodadSetNames") or "").strip(),
                        },
                    }

                    f_out.write(json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n")
                    written += 1
                    rows_written_total += 1

                    if max_rows_per_csv and seen >= max_rows_per_csv:
                        break
        except Exception:
            # If a single tile placement file is broken, keep going.
            continue

        outputs.append(
            {
                "tile": tile_base,
                "placements_csv": str(csv_path),
                "out_jsonl": str(out_path),
                "rows_seen": int(seen),
                "rows_written": int(written),
            }
        )

    outputs.sort(key=lambda r: str(r.get("tile") or "").lower())
    manifest_path = dst_root / "wowexport_placements_manifest.json"
    manifest = {
        "export_root": str(ex_root),
        "map_dir": str(root),
        "out_root": str(dst_root),
        "name_filter": name_filter,
        "csv_files_scanned": int(csv_count),
        "rows_seen_total": int(rows_total),
        "rows_written_total": int(rows_written_total),
        "missing_models": int(missing_models),
        "missing_models_sample": missing_models_sample,
        "include_missing_models": bool(include_missing_models),
        "outputs": outputs,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "export_root": str(ex_root),
        "map_dir": str(root),
        "out_root": str(dst_root),
        "manifest_path": str(manifest_path),
        "csv_files_scanned": int(csv_count),
        "rows_seen_total": int(rows_total),
        "rows_written_total": int(rows_written_total),
        "missing_models": int(missing_models),
        "missing_models_sample": missing_models_sample,
        "outputs": outputs,
    }
