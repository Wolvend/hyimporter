from __future__ import annotations

import os
import json
import shlex
import subprocess
import sys
import shutil
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import math

from .wowexport import (
    collect_unique_models_from_map as _collect_unique_models_from_map,
    export_map_placements_manifest as _export_map_placements_manifest,
    list_wowexport_maps as _list_wowexport_maps,
    obj_bbox_minmax as _obj_bbox_minmax,
    scan_wowexport_map as _scan_wowexport_map,
)

_WIN_DRIVE_RE = re.compile(r"^(?P<drive>[A-Za-z]):[\\/](?P<rest>.*)$")


def _expand(path: str | Path) -> Path:
    # Allow Windows-style paths (common when user copies from wow.export GUI settings).
    raw = str(path)
    m = _WIN_DRIVE_RE.match(raw)
    if m:
        drive = m.group("drive").lower()
        rest = m.group("rest").replace("\\", "/")
        raw = f"/mnt/{drive}/{rest}"
    return Path(raw).expanduser().resolve()


def inspect_map_directory(map_dir: str | Path) -> Dict[str, object]:
    path = _expand(map_dir)
    height_path = path / "height" / "height.png"
    weights_dir = path / "weights"
    weightmaps_dir = path / "weightmaps"
    masks_dir = path / "masks"
    color_map = path / "color" / "colormap.png"

    def _count_files(dir_path: Path, suffixes: tuple[str, ...]) -> int:
        if not dir_path.exists() or not dir_path.is_dir():
            return 0
        suffixes_norm = tuple(s.lower() for s in suffixes)
        count = 0
        for p in dir_path.iterdir():
            if p.is_file() and p.suffix.lower() in suffixes_norm:
                count += 1
        return count

    objects_dir = path / "objects"
    placements_dir = path / "placements"
    object_files = _count_files(objects_dir, (".json", ".csv", ".obj"))
    placement_files = _count_files(placements_dir, (".json", ".csv"))
    weight_files = _count_files(weights_dir, (".png",))
    weightmap_files = _count_files(weightmaps_dir, (".png",))
    mask_files = _count_files(masks_dir, (".png",))

    return {
        "map_name": path.name,
        "map_path": str(path),
        "exists": path.exists() and path.is_dir(),
        "height_png": str(height_path),
        "has_height_png": height_path.exists(),
        "weights_dir": str(weights_dir),
        "weightmaps_dir": str(weightmaps_dir),
        "masks_dir": str(masks_dir),
        "has_weights_dir": weights_dir.exists() and weights_dir.is_dir(),
        "has_weightmaps_dir": weightmaps_dir.exists() and weightmaps_dir.is_dir(),
        "has_masks_dir": masks_dir.exists() and masks_dir.is_dir(),
        "has_colormap_png": color_map.exists(),
        "weight_file_count": weight_files,
        "weightmap_file_count": weightmap_files,
        "mask_file_count": mask_files,
        "object_file_count": object_files,
        "placement_file_count": placement_files,
        "is_ready_for_build": height_path.exists(),
    }


def list_maps(input_root: str | Path, limit: int = 100) -> Dict[str, object]:
    root = _expand(input_root)
    if limit <= 0:
        raise ValueError("limit must be > 0")

    if not root.exists() or not root.is_dir():
        return {
            "input_root": str(root),
            "exists": False,
            "maps": [],
            "total_maps": 0,
            "returned_maps": 0,
            "truncated": False,
        }

    dirs = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    out: List[Dict[str, object]] = []
    for p in dirs[:limit]:
        out.append(inspect_map_directory(p))

    return {
        "input_root": str(root),
        "exists": True,
        "maps": out,
        "total_maps": len(dirs),
        "returned_maps": len(out),
        "truncated": len(dirs) > len(out),
    }


def validate_map(input_root: str | Path, map_name: str) -> Dict[str, object]:
    root = _expand(input_root)
    map_dir = root / map_name
    errors: List[str] = []
    warnings: List[str] = []

    if not root.exists() or not root.is_dir():
        errors.append(f"Input root does not exist: {root}")
    if not map_dir.exists() or not map_dir.is_dir():
        errors.append(f"Map directory does not exist: {map_dir}")

    details = inspect_map_directory(map_dir)
    if not details["has_height_png"]:
        errors.append("Missing required file: height/height.png")

    has_weights = bool(details["weight_file_count"]) or bool(details["weightmap_file_count"])
    if not has_weights:
        warnings.append("No weight maps found in weights/ or weightmaps/; semantic materials may be weak.")

    if not details["has_colormap_png"]:
        warnings.append("No color/colormap.png found; optional palette matching and visual checks are limited.")

    if not details["has_masks_dir"] or not details["mask_file_count"]:
        warnings.append("No mask PNG files found in masks/; river/road constraints may be weaker.")

    if not details["object_file_count"] and not details["placement_file_count"]:
        warnings.append("No objects/placements detected; terrain-only build will still run.")

    return {
        "ok": len(errors) == 0,
        "input_root": str(root),
        "map_name": map_name,
        "map_path": str(map_dir),
        "errors": errors,
        "warnings": warnings,
        "details": details,
    }


def run_world_build(
    config_path: str | Path,
    allow_8bit_height: bool = False,
    sync_tiles: bool = False,
    tile_workers: Optional[int] = None,
) -> Dict[str, object]:
    from .config import load_config
    from .export import run_pipeline

    cfg_path = _expand(config_path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    cfg = load_config(cfg_path)
    if sync_tiles:
        cfg.runtime.async_tile_export = False

    if tile_workers is not None:
        if tile_workers < 0:
            raise ValueError("tile_workers must be >= 0")
        cfg.runtime.tile_workers = int(tile_workers)

    summary = run_pipeline(cfg, allow_8bit_override=allow_8bit_height)
    return {
        "config_path": str(cfg_path),
        "allow_8bit_height": bool(allow_8bit_height),
        "sync_tiles": bool(sync_tiles),
        "tile_workers": cfg.runtime.tile_workers,
        "summary": summary,
    }


def _format_command(cmd: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def run_obj_to_schematic(
    obj_path: str | Path,
    schematic_path: str | Path,
    bo2_path: str | Path = "",
    block_id: int = 1,
    padding: int = 1,
    voxel_scale: float = 1.0,
    wireframe: bool = False,
) -> Dict[str, object]:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "obj_to_schematic.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Missing conversion script: {script_path}")

    src_obj = _expand(obj_path)
    if not src_obj.exists():
        raise FileNotFoundError(f"OBJ file not found: {src_obj}")
    dst_schem = _expand(schematic_path)
    dst_schem.parent.mkdir(parents=True, exist_ok=True)

    cmd: List[str] = [
        sys.executable,
        str(script_path),
        "--obj",
        str(src_obj),
        "--schematic",
        str(dst_schem),
        "--block-id",
        str(int(block_id)),
        "--padding",
        str(int(padding)),
        "--voxel-scale",
        str(float(voxel_scale)),
    ]

    bo2_out = None
    bo2_text = str(bo2_path).strip()
    if bo2_text:
        bo2_out = _expand(bo2_text)
        bo2_out.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--bo2", str(bo2_out)])

    if wireframe:
        cmd.append("--wireframe")

    proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=False)

    if proc.returncode != 0:
        raise RuntimeError(
            f"obj_to_schematic failed (exit={proc.returncode})\n"
            f"CMD: {_format_command(cmd)}\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    mode = ""
    dims_line = ""
    for line in proc.stdout.splitlines():
        if line.startswith("Mode:"):
            mode = line.split(":", 1)[1].strip()
        if line.startswith("Dims (W,H,L):"):
            dims_line = line.strip()

    return {
        "ok": True,
        "command": _format_command(cmd),
        "obj_path": str(src_obj),
        "schematic_path": str(dst_schem),
        "bo2_path": str(bo2_out) if bo2_out is not None else "",
        "mode": mode,
        "dims": dims_line,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def list_obj_exports(export_root: str | Path, max_results: int = 200, name_filter: str = "") -> Dict[str, object]:
    root = _expand(export_root)
    if max_results <= 0:
        raise ValueError("max_results must be > 0")
    if not root.exists() or not root.is_dir():
        return {
            "export_root": str(root),
            "exists": False,
            "results": [],
            "returned_count": 0,
            "total_matching": 0,
            "truncated": False,
        }

    filter_norm = name_filter.strip().lower()
    results: List[Dict[str, object]] = []
    total_matching = 0

    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in sorted(filenames):
            if not fname.lower().endswith(".obj"):
                continue
            full = Path(dirpath) / fname
            rel = full.relative_to(root).as_posix()
            if filter_norm and filter_norm not in rel.lower():
                continue

            total_matching += 1
            if len(results) < max_results:
                stat = full.stat()
                results.append(
                    {
                        "relative_path": rel,
                        "absolute_path": str(full.resolve()),
                        "size_bytes": int(stat.st_size),
                    }
                )

    return {
        "export_root": str(root),
        "exists": True,
        "results": results,
        "returned_count": len(results),
        "total_matching": total_matching,
        "truncated": total_matching > len(results),
    }


def batch_obj_to_schematic(
    export_root: str | Path,
    out_root: str | Path,
    name_filter: str = "",
    max_files: int = 0,
    workers: int = 0,
    block_id: int = 1,
    padding: int = 1,
    voxel_scale: float = 1.0,
    wireframe: bool = False,
    write_bo2: bool = True,
    resume: bool = True,
    max_obj_mb: float = 200.0,
    max_cells: int = 25_000_000,
) -> Dict[str, object]:
    src_root = _expand(export_root)
    dst_root = _expand(out_root)
    if not src_root.exists() or not src_root.is_dir():
        raise FileNotFoundError(f"export_root not found: {src_root}")

    if max_files < 0:
        raise ValueError("max_files must be >= 0")
    if workers < 0:
        raise ValueError("workers must be >= 0")
    if max_obj_mb <= 0:
        raise ValueError("max_obj_mb must be > 0")
    if max_cells <= 0:
        raise ValueError("max_cells must be > 0")

    filter_norm = name_filter.strip().lower()
    obj_paths: List[Path] = []
    for dirpath, _dirnames, filenames in os.walk(src_root):
        for fname in filenames:
            if not fname.lower().endswith(".obj"):
                continue
            full = Path(dirpath) / fname
            rel = full.relative_to(src_root).as_posix()
            if filter_norm and filter_norm not in rel.lower():
                continue
            obj_paths.append(full)

    obj_paths.sort(key=lambda p: p.as_posix().lower())
    total_candidates = len(obj_paths)
    if max_files and len(obj_paths) > max_files:
        obj_paths = obj_paths[:max_files]

    dst_root.mkdir(parents=True, exist_ok=True)

    max_bytes = int(max_obj_mb * 1024 * 1024)
    skipped_existing = 0
    skipped_too_large = 0
    skipped_too_many_cells = 0

    def _obj_bbox_minmax(path: Path) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
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
        return (vmin[0], vmin[1], vmin[2]), (vmax[0], vmax[1], vmax[2])

    # Pre-filter on file size and resume checks to avoid spawning subprocesses.
    work: List[Tuple[Path, Path, str]] = []
    for obj in obj_paths:
        rel = obj.relative_to(src_root).as_posix()
        if obj.stat().st_size > max_bytes:
            skipped_too_large += 1
            continue

        # Guardrail: avoid generating massive dense schematic arrays by default.
        try:
            vmin, vmax = _obj_bbox_minmax(obj)
            dx = max(0.0, float(vmax[0]) - float(vmin[0]))
            dy = max(0.0, float(vmax[1]) - float(vmin[1]))
            dz = max(0.0, float(vmax[2]) - float(vmin[2]))
            w = int(math.ceil(dx * float(voxel_scale))) + int(padding) + 2
            h = int(math.ceil(dy * float(voxel_scale))) + int(padding) + 2
            l = int(math.ceil(dz * float(voxel_scale))) + int(padding) + 2
            if w * h * l > int(max_cells):
                skipped_too_many_cells += 1
                continue
        except Exception:
            # If bbox scan fails, fall back to trying conversion (and allow it to error).
            pass

        out_dir = dst_root / Path(rel).parent
        base = Path(rel).stem
        schem = out_dir / f"{base}.schematic"
        bo2 = out_dir / f"{base}.bo2"

        if resume and schem.exists() and (not write_bo2 or bo2.exists()):
            try:
                obj_mtime = obj.stat().st_mtime
                if schem.stat().st_mtime >= obj_mtime and (not write_bo2 or bo2.stat().st_mtime >= obj_mtime):
                    skipped_existing += 1
                    continue
            except OSError:
                pass

        work.append((obj, schem, str(bo2) if write_bo2 else ""))

    requested_workers = int(workers)
    if requested_workers == 0:
        requested_workers = max(1, min(len(work) or 1, os.cpu_count() or 1))
    requested_workers = max(1, min(len(work) or 1, requested_workers))

    started = time.time()
    ok = 0
    failed = 0
    failures: List[Dict[str, str]] = []

    def _one(item: Tuple[Path, Path, str]) -> Dict[str, object]:
        obj, schem, bo2_path = item
        rel = obj.relative_to(src_root).as_posix()
        out_dir = schem.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        try:
            result = run_obj_to_schematic(
                obj_path=obj,
                schematic_path=schem,
                bo2_path=bo2_path,
                block_id=block_id,
                padding=padding,
                voxel_scale=voxel_scale,
                wireframe=wireframe,
            )
            dt = time.time() - t0
            return {"ok": True, "rel": rel, "seconds": dt, "result": result}
        except Exception as e:  # noqa: BLE001 - capture and continue batch
            dt = time.time() - t0
            return {"ok": False, "rel": rel, "seconds": dt, "error": str(e)}

    if work:
        with ThreadPoolExecutor(max_workers=requested_workers) as pool:
            futures = {pool.submit(_one, item): item for item in work}
            for fut in as_completed(futures):
                r = fut.result()
                if r.get("ok"):
                    ok += 1
                else:
                    failed += 1
                    if len(failures) < 25:
                        failures.append({"rel": str(r.get("rel", "")), "error": str(r.get("error", ""))})

    elapsed = time.time() - started
    return {
        "export_root": str(src_root),
        "out_root": str(dst_root),
        "name_filter": name_filter,
        "total_candidates": total_candidates,
        "selected": len(obj_paths),
        "to_process": len(work),
        "skipped_existing": skipped_existing,
        "skipped_too_large": skipped_too_large,
        "skipped_too_many_cells": skipped_too_many_cells,
        "max_obj_mb": float(max_obj_mb),
        "max_cells": int(max_cells),
        "workers": requested_workers,
        "params": {
            "block_id": int(block_id),
            "padding": int(padding),
            "voxel_scale": float(voxel_scale),
            "wireframe": bool(wireframe),
            "write_bo2": bool(write_bo2),
            "resume": bool(resume),
        },
        "ok": ok,
        "failed": failed,
        "failures_sample": failures,
        "elapsed_seconds": elapsed,
    }


def list_wowexport_maps(export_root: str | Path, limit: int = 100) -> Dict[str, object]:
    """List wow.export map folders under <export_root>/maps."""
    return _list_wowexport_maps(export_root=export_root, limit=limit)


def scan_wowexport_map(
    map_dir: str | Path,
    max_tile_details: int = 100,
    compute_bboxes: bool = True,
    parse_placements: bool = True,
    max_placement_rows_per_file: int = 0,
) -> Dict[str, object]:
    """Scan a wow.export map folder (maps/<name>) for tiles, textures, and placement CSVs."""
    return _scan_wowexport_map(
        map_dir=map_dir,
        max_tile_details=max_tile_details,
        compute_bboxes=compute_bboxes,
        parse_placements=parse_placements,
        max_placement_rows_per_file=max_placement_rows_per_file,
    )


def wowexport_map_export_placements_manifest(
    export_root: str | Path,
    map_dir: str | Path,
    out_root: str | Path,
    name_filter: str = "",
    max_csv_files: int = 0,
    max_rows_per_csv: int = 0,
    include_missing_models: bool = False,
) -> Dict[str, object]:
    """Export wow.export placement CSV rows into per-tile JSONL plus a summary manifest."""
    return _export_map_placements_manifest(
        export_root=export_root,
        map_dir=map_dir,
        out_root=out_root,
        name_filter=name_filter,
        max_csv_files=max_csv_files,
        max_rows_per_csv=max_rows_per_csv,
        include_missing_models=include_missing_models,
    )


def wowexport_map_models_to_schematic(
    export_root: str | Path,
    map_dir: str | Path,
    out_root: str | Path,
    name_filter: str = "",
    max_models: int = 0,
    workers: int = 0,
    block_id: int = 1,
    padding: int = 1,
    voxel_scale: float = 0.0,
    target_max_dim: int = 64,
    wireframe: bool = False,
    write_bo2: bool = True,
    resume: bool = True,
    max_obj_mb: float = 200.0,
    max_cells: int = 25_000_000,
) -> Dict[str, object]:
    """Convert every unique OBJ referenced by a map's placement CSVs into voxels.

    Outputs are written under:
      <out_root>/models/<relative_to_export_root>.{schematic,bo2}

    A machine-readable manifest is also written to:
      <out_root>/wowexport_models_manifest.json
    """

    src_root = _expand(export_root)
    dst_root = _expand(out_root)
    if not src_root.exists() or not src_root.is_dir():
        raise FileNotFoundError(f"export_root not found: {src_root}")

    if max_models < 0:
        raise ValueError("max_models must be >= 0")
    if workers < 0:
        raise ValueError("workers must be >= 0")
    if voxel_scale < 0:
        raise ValueError("voxel_scale must be >= 0 (0 means auto-fit by target_max_dim)")
    if target_max_dim <= 0:
        raise ValueError("target_max_dim must be > 0")
    if max_obj_mb <= 0:
        raise ValueError("max_obj_mb must be > 0")
    if max_cells <= 0:
        raise ValueError("max_cells must be > 0")

    dst_root.mkdir(parents=True, exist_ok=True)

    model_listing = _collect_unique_models_from_map(
        export_root=src_root,
        map_dir=map_dir,
        max_csv_files=0,
        max_rows_per_csv=0,
        name_filter=name_filter,
    )
    rel_models: List[str] = list(model_listing.get("unique_models") or [])
    if max_models and len(rel_models) > max_models:
        rel_models = rel_models[:max_models]

    max_bytes = int(max_obj_mb * 1024 * 1024)
    skipped_existing = 0
    skipped_missing = 0
    skipped_too_large = 0
    skipped_too_many_cells = 0

    work: List[Tuple[Path, Path, str, float, Dict[str, object]]] = []
    for rel in rel_models:
        rel_posix = str(rel).replace("\\", "/")
        obj = (src_root / rel_posix).resolve()
        if not obj.exists():
            skipped_missing += 1
            continue
        if obj.stat().st_size > max_bytes:
            skipped_too_large += 1
            continue

        out_dir = dst_root / "models" / Path(rel_posix).parent
        base = Path(rel_posix).stem
        schem = out_dir / f"{base}.schematic"
        bo2 = out_dir / f"{base}.bo2"

        if resume and schem.exists() and (not write_bo2 or bo2.exists()):
            try:
                obj_mtime = obj.stat().st_mtime
                if schem.stat().st_mtime >= obj_mtime and (not write_bo2 or bo2.stat().st_mtime >= obj_mtime):
                    skipped_existing += 1
                    continue
            except OSError:
                pass

        # Compute a per-model voxel scale to target a consistent maximum dimension.
        # For whole-map reconstruction you typically want a fixed scale so relative sizes
        # between models are preserved. For preview/browsing, auto-fit keeps output sizes
        # bounded via `target_max_dim`.
        meta: Dict[str, object] = {"rel": rel_posix, "obj_path": str(obj)}
        used_scale = float(voxel_scale)
        scale_mode = "fixed" if used_scale > 0 else "fit"
        try:
            vmin, vmax, _vcount = _obj_bbox_minmax(obj)
            dx = float(vmax[0] - vmin[0])
            dy = float(vmax[1] - vmin[1])
            dz = float(vmax[2] - vmin[2])
            if used_scale <= 0:
                max_dim = max(1e-6, dx, dy, dz)
                used_scale = float(target_max_dim) / float(max_dim)
                # Guardrail: keep scale in a sane range; extreme scales tend to explode runtime/memory.
                used_scale = float(max(0.05, min(50.0, used_scale)))

            w = int(math.ceil(dx * used_scale)) + int(padding) + 2
            h = int(math.ceil(dy * used_scale)) + int(padding) + 2
            l = int(math.ceil(dz * used_scale)) + int(padding) + 2
            if w * h * l > int(max_cells):
                skipped_too_many_cells += 1
                continue

            meta["bbox"] = {"vmin": {"x": vmin[0], "y": vmin[1], "z": vmin[2]}, "vmax": {"x": vmax[0], "y": vmax[1], "z": vmax[2]}}
            meta["dims_estimate"] = {"w": w, "h": h, "l": l, "cells": int(w * h * l)}
        except Exception as exc:  # noqa: BLE001 - bbox failures should not kill batch
            meta["bbox_error"] = str(exc)

        meta["voxel_scale"] = float(used_scale)
        meta["voxel_scale_mode"] = scale_mode

        work.append((obj, schem, str(bo2) if write_bo2 else "", float(used_scale), meta))

    requested_workers = int(workers)
    if requested_workers == 0:
        requested_workers = max(1, min(len(work) or 1, os.cpu_count() or 1))
    requested_workers = max(1, min(len(work) or 1, requested_workers))

    started = time.time()
    ok = 0
    failed = 0
    failures: List[Dict[str, str]] = []
    results: List[Dict[str, object]] = []

    def _one(item: Tuple[Path, Path, str, float, Dict[str, object]]) -> Dict[str, object]:
        obj, schem, bo2_path, voxel_scale, meta = item
        out_dir = schem.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        try:
            result = run_obj_to_schematic(
                obj_path=obj,
                schematic_path=schem,
                bo2_path=bo2_path,
                block_id=block_id,
                padding=padding,
                voxel_scale=voxel_scale,
                wireframe=wireframe,
            )
            dt = time.time() - t0
            meta_out = dict(meta)
            meta_out.update({"ok": True, "seconds": dt, "result": result})
            return meta_out
        except Exception as e:  # noqa: BLE001 - capture and continue batch
            dt = time.time() - t0
            meta_out = dict(meta)
            meta_out.update({"ok": False, "seconds": dt, "error": str(e)})
            return meta_out

    if work:
        with ThreadPoolExecutor(max_workers=requested_workers) as pool:
            futures = {pool.submit(_one, item): item for item in work}
            for fut in as_completed(futures):
                r = fut.result()
                results.append(r)
                if r.get("ok"):
                    ok += 1
                else:
                    failed += 1
                    if len(failures) < 25:
                        failures.append({"rel": str(r.get("rel", "")), "error": str(r.get("error", ""))})

    elapsed = time.time() - started

    # Stable output order for manifest reproducibility.
    results.sort(key=lambda r: str(r.get("rel") or "").lower())

    manifest_path = dst_root / "wowexport_models_manifest.json"
    manifest = {
        "export_root": str(src_root),
        "map_dir": str(_expand(map_dir)),
        "out_root": str(dst_root),
        "name_filter": name_filter,
        "requested": len(rel_models),
        "to_process": len(work),
        "skipped_existing": skipped_existing,
        "skipped_missing": skipped_missing,
        "skipped_too_large": skipped_too_large,
        "skipped_too_many_cells": skipped_too_many_cells,
        "max_obj_mb": float(max_obj_mb),
        "max_cells": int(max_cells),
        "workers": requested_workers,
        "params": {
            "block_id": int(block_id),
            "padding": int(padding),
            "voxel_scale": float(voxel_scale),
            "target_max_dim": int(target_max_dim),
            "wireframe": bool(wireframe),
            "write_bo2": bool(write_bo2),
            "resume": bool(resume),
        },
        "ok": int(ok),
        "failed": int(failed),
        "failures_sample": failures,
        "elapsed_seconds": float(elapsed),
        "results": results,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "export_root": str(src_root),
        "map_dir": str(_expand(map_dir)),
        "out_root": str(dst_root),
        "manifest_path": str(manifest_path),
        "requested": len(rel_models),
        "to_process": len(work),
        "skipped_existing": skipped_existing,
        "skipped_missing": skipped_missing,
        "skipped_too_large": skipped_too_large,
        "skipped_too_many_cells": skipped_too_many_cells,
        "workers": requested_workers,
        "voxel_scale": float(voxel_scale),
        "ok": ok,
        "failed": failed,
        "failures_sample": failures,
        "elapsed_seconds": elapsed,
    }


def voxelviewer_screenshot_bo2(
    bo2_path: str | Path,
    png_path: str | Path,
    zoom: int = 10,
    yaw: int = 270,
    width: int = 1365,
    height: int = 768,
    timeout_seconds: int = 180,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Render a `.bo2` file via tools/voxelviewer in Playwright and write a PNG screenshot.

    Notes:
    - This depends on the agent_playground repo-local Playwright checkout.
    - Use `dry_run=true` in environments where Chromium cannot be launched.
    """

    if not dry_run and not shutil.which("node"):
        raise RuntimeError("Missing dependency: node (required to run tools/voxelviewer/screenshot_bo2.js)")

    repo_root = Path(__file__).resolve().parents[2]  # .../source/agents/tooling/hyimporter
    workspace_root = repo_root.parents[3]  # .../agent_playground
    script = workspace_root / "tools" / "voxelviewer" / "screenshot_bo2.js"
    if not script.exists():
        raise FileNotFoundError(f"Missing voxelviewer screenshot script: {script}")

    src_bo2 = _expand(bo2_path)
    if not src_bo2.exists():
        raise FileNotFoundError(f"BO2 file not found: {src_bo2}")

    dst_png = _expand(png_path)
    dst_png.parent.mkdir(parents=True, exist_ok=True)

    cmd: List[str] = [
        "node",
        str(script),
        "--bo2",
        str(src_bo2),
        "--out",
        str(dst_png),
        "--zoom",
        str(int(zoom)),
        "--yaw",
        str(int(yaw)),
        "--width",
        str(int(width)),
        "--height",
        str(int(height)),
    ]

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "command": _format_command(cmd),
            "bo2_path": str(src_bo2),
            "png_path": str(dst_png),
        }

    proc = subprocess.run(
        cmd,
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        check=False,
        timeout=max(1, int(timeout_seconds)),
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"voxelviewer screenshot failed (exit={proc.returncode})\n"
            f"CMD: {_format_command(cmd)}\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    return {
        "ok": True,
        "command": _format_command(cmd),
        "bo2_path": str(src_bo2),
        "png_path": str(dst_png),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }
