from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from .cleanup import cleanup_labels
from .bo2 import export_tile_bo2
from .config import PipelineConfig, map_input_dir, map_output_dir
from .geom_fields import compute_geom_fields
from .height_fit import fit_height_to_budget
from .hydrology import apply_hydrology
from .io_images import (
    load_colormap,
    load_height_image,
    load_masks,
    load_object_placements,
    load_weight_maps,
)
from .materials import assign_material_labels
from .meshing_obj import (
    build_base_volume_mesh_from_vertex_grid,
    build_surface_shell_mesh,
    height_to_vertex_grid,
    write_obj,
)
from .noise import apply_multiscale_noise
from .qa import (
    assert_height_range,
    assert_seam_threshold,
    height_stats,
    material_coverage,
    save_height_histogram,
    save_seam_heatmap,
    seam_diff_report,
)
from .resample import resample_colormap, resample_height, resample_masks, resample_weights
from .runbook import write_generated_hytale_runbook, write_tile_manifest
from .schematic import export_tile_schematic
from .tiling import TileSpec, build_tiles
from .utils import ensure_dir, read_optional_csv, write_json


def _warn(msg: str, warnings: List[str]) -> None:
    warnings.append(msg)
    print(f"WARN: {msg}")


@dataclass
class TileExportResult:
    tile_i: int
    tile_j: int
    manifest_row: Dict[str, object]
    vertex_grid: np.ndarray
    warnings: List[str]


def _load_inputs(cfg: PipelineConfig, allow_8bit_override: bool = False):
    in_dir = map_input_dir(cfg)
    allow_8bit = bool(cfg.input.allow_8bit_height or allow_8bit_override)

    height, height_meta = load_height_image(
        in_dir / "height" / "height.png",
        allow_8bit=allow_8bit,
    )

    weights_dir = in_dir / "weights"
    if not weights_dir.exists():
        weights_dir = in_dir / "weightmaps"

    weights = load_weight_maps(weights_dir)
    masks = load_masks(in_dir / "masks")
    colormap = load_colormap(in_dir / "color" / "colormap.png")
    anchors = read_optional_csv(in_dir / "anchors" / "landmarks.csv")
    objects = load_object_placements(in_dir)

    return in_dir, height, height_meta, weights, masks, colormap, anchors, objects


def _target_shape(height: np.ndarray, cfg: PipelineConfig) -> tuple[int, int]:
    if cfg.resample.target_resolution is None:
        return int(height.shape[0]), int(height.shape[1])
    r = int(cfg.resample.target_resolution)
    return r, r


def _check_tile_coverage(shape: Tuple[int, int], tiles: List[TileSpec]) -> None:
    coverage = np.zeros(shape, dtype=np.int16)
    for t in tiles:
        coverage[t.x0 : t.x1, t.z0 : t.z1] += 1

    missing = int(np.sum(coverage == 0))
    overlaps = int(np.sum(coverage > 1))
    if missing > 0 or overlaps > 0:
        raise RuntimeError(
            f"Missing tile regions detected (missing={missing}, overlaps={overlaps}). "
            "Abort by safety policy."
        )


def _core_vertex_grid_from_expanded(y_int: np.ndarray, t: TileSpec) -> np.ndarray:
    ex = y_int[t.ex0 : t.ex1, t.ez0 : t.ez1]
    ex_v = height_to_vertex_grid(ex)

    cx0 = t.x0 - t.ex0
    cz0 = t.z0 - t.ez0
    h = t.x1 - t.x0
    w = t.z1 - t.z0

    core_v = ex_v[cx0 : cx0 + h + 1, cz0 : cz0 + w + 1]
    exp_shape = (h + 1, w + 1)
    if core_v.shape != exp_shape:
        raise RuntimeError(f"Core vertex grid shape mismatch for tile {t.i},{t.j}: {core_v.shape} != {exp_shape}")
    return core_v


def _check_mesh_limits(
    cfg: PipelineConfig,
    tile_name: str,
    mesh_vertices: int,
    tile_obj_paths: List[Path],
    warnings: List[str],
) -> None:
    if mesh_vertices > int(cfg.safety.max_vertices_per_tile):
        _warn(
            f"{tile_name} vertices={mesh_vertices} exceeds {cfg.safety.max_vertices_per_tile}",
            warnings,
        )

    total_bytes = 0
    for p in tile_obj_paths:
        if p.exists():
            total_bytes += int(p.stat().st_size)

    if total_bytes > int(cfg.safety.max_obj_bytes_per_tile):
        mb = total_bytes / (1024.0 * 1024.0)
        limit_mb = cfg.safety.max_obj_bytes_per_tile / (1024.0 * 1024.0)
        _warn(f"{tile_name} OBJ size={mb:.2f}MB exceeds {limit_mb:.2f}MB", warnings)


def _export_single_tile(
    cfg: PipelineConfig,
    t: TileSpec,
    y: np.ndarray,
    labels: np.ndarray,
    out_tiles_dir: Path,
) -> TileExportResult:
    tile_warnings: List[str] = []
    bbox_cfg = asdict(cfg.mesh.stabilize_bbox)
    tile_name = f"tile_{t.i}_{t.j}"
    core_y = y[t.x0 : t.x1, t.z0 : t.z1]
    core_labels = labels[t.x0 : t.x1, t.z0 : t.z1]
    core_v = _core_vertex_grid_from_expanded(y, t)

    tile_obj_paths: List[Path] = []
    mesh_vertices_total = 0

    base_obj_path = out_tiles_dir / f"{tile_name}.obj"
    if cfg.outputs.export_obj and cfg.mesh.export_base:
        base_mesh = build_base_volume_mesh_from_vertex_grid(
            core_v,
            bottom_y=cfg.height.bottom_y,
            stabilize_bbox=bbox_cfg,
        )
        write_obj(base_obj_path, base_mesh)
        tile_obj_paths.append(base_obj_path)
        mesh_vertices_total += len(base_mesh.vertices)

    shell_names: List[str] = []
    if cfg.outputs.export_obj and cfg.mesh.export_shells:
        for li, lname in enumerate(cfg.materials.layers):
            m = core_labels == li
            if not np.any(m):
                continue
            shell_mesh = build_surface_shell_mesh(
                core_y,
                m,
                thickness=cfg.mesh.shell_thickness,
                stabilize_bbox=bbox_cfg,
            )
            shell_name = f"{tile_name}__{lname}.obj"
            shell_path = out_tiles_dir / shell_name
            write_obj(shell_path, shell_mesh)
            tile_obj_paths.append(shell_path)
            mesh_vertices_total += len(shell_mesh.vertices)
            shell_names.append(shell_name)

    schematic_name = f"{tile_name}.schematic"
    bo2_name = f"{tile_name}.bo2"
    if cfg.outputs.export_schematic:
        export_tile_schematic(
            path=out_tiles_dir / schematic_name,
            y_int=core_y,
            labels=core_labels,
            layer_names=cfg.materials.layers,
            block_ids=cfg.outputs.minecraft_block_ids,
            bottom_y=cfg.height.bottom_y,
            full_volume=cfg.outputs.schematic_full_volume,
        )

    if cfg.outputs.export_bo2:
        export_tile_bo2(
            path=out_tiles_dir / bo2_name,
            y_int=core_y,
            labels=core_labels,
            layer_names=cfg.materials.layers,
            block_ids=cfg.outputs.minecraft_block_ids,
            include_subsurface=cfg.outputs.bo2_include_subsurface,
            bottom_y=cfg.height.bottom_y,
        )

    _check_mesh_limits(cfg, tile_name, mesh_vertices_total, tile_obj_paths, tile_warnings)

    meta = {
        "tile": {"i": t.i, "j": t.j},
        "world_origin": {"x0": t.x0, "z0": t.z0},
        "core_shape": {"x": int(core_y.shape[0]), "z": int(core_y.shape[1])},
        "height_range": {"min": int(np.min(core_y)), "max": int(np.max(core_y))},
        "recommended_hytale_import": {
            "height": cfg.hytale.default_import_height,
            "base_fill_item_id": cfg.hytale.base_fill_item_id,
            "shell_fill_solid": False,
        },
        "files": {
            "base": base_obj_path.name if (cfg.outputs.export_obj and cfg.mesh.export_base) else None,
            "shells": shell_names,
            "schematic": schematic_name if cfg.outputs.export_schematic else None,
            "bo2": bo2_name if cfg.outputs.export_bo2 else None,
        },
    }
    write_json(out_tiles_dir / f"{tile_name}.meta.json", meta)

    manifest_row = {
        "tile_i": t.i,
        "tile_j": t.j,
        "x0": t.x0,
        "z0": t.z0,
        "x1": t.x1,
        "z1": t.z1,
        "tile_obj": str(base_obj_path) if (cfg.outputs.export_obj and cfg.mesh.export_base) else "",
        "tile_schematic": str(out_tiles_dir / schematic_name) if cfg.outputs.export_schematic else "",
        "tile_bo2": str(out_tiles_dir / bo2_name) if cfg.outputs.export_bo2 else "",
        "meta_json": str(out_tiles_dir / f"{tile_name}.meta.json"),
    }

    return TileExportResult(
        tile_i=t.i,
        tile_j=t.j,
        manifest_row=manifest_row,
        vertex_grid=core_v,
        warnings=tile_warnings,
    )


def _export_tiles(
    cfg: PipelineConfig,
    y: np.ndarray,
    labels: np.ndarray,
    out_tiles_dir: Path,
    warnings: List[str],
) -> tuple[List[Dict[str, object]], Dict[Tuple[int, int], np.ndarray]]:
    tiles = build_tiles(y.shape, tile_size=cfg.tiling.tile_size, overlap=cfg.tiling.overlap)
    if len(tiles) > int(cfg.safety.warn_max_tiles):
        _warn(f"Tile count {len(tiles)} exceeds safety warning threshold {cfg.safety.warn_max_tiles}", warnings)

    _check_tile_coverage(y.shape, tiles)

    requested_workers = int(cfg.runtime.tile_workers)
    if requested_workers < 0:
        raise ValueError("runtime.tile_workers must be >= 0")

    if requested_workers == 0:
        requested_workers = max(1, min(len(tiles), os.cpu_count() or 1))
    else:
        requested_workers = max(1, min(len(tiles), requested_workers))

    run_async = bool(cfg.runtime.async_tile_export and len(tiles) > 1)
    results_by_tile: Dict[Tuple[int, int], TileExportResult] = {}

    if run_async:
        with ThreadPoolExecutor(max_workers=requested_workers) as pool:
            futures = {pool.submit(_export_single_tile, cfg, t, y, labels, out_tiles_dir): (t.i, t.j) for t in tiles}
            for future in as_completed(futures):
                result = future.result()
                results_by_tile[(result.tile_i, result.tile_j)] = result
    else:
        for t in tiles:
            result = _export_single_tile(cfg, t, y, labels, out_tiles_dir)
            results_by_tile[(result.tile_i, result.tile_j)] = result

    manifest_rows: List[Dict[str, object]] = []
    tile_vertex_grids: Dict[Tuple[int, int], np.ndarray] = {}

    # Deterministic output order regardless of async completion timing.
    for key in sorted(results_by_tile):
        result = results_by_tile[key]
        manifest_rows.append(result.manifest_row)
        tile_vertex_grids[key] = result.vertex_grid
        warnings.extend(result.warnings)

    return manifest_rows, tile_vertex_grids


def _cleanup_labels_in_expanded_tiles(cfg: PipelineConfig, labels: np.ndarray) -> tuple[np.ndarray, float]:
    tiles = build_tiles(labels.shape, tile_size=cfg.tiling.tile_size, overlap=cfg.tiling.overlap)
    out = np.full_like(labels, -1, dtype=np.int16)
    speckle_vals: List[float] = []

    for t in tiles:
        ex = labels[t.ex0 : t.ex1, t.ez0 : t.ez1]
        cleaned_ex, stats = cleanup_labels(
            ex,
            majority_radius=cfg.materials.majority_radius,
            min_area=cfg.materials.island_min_area,
        )
        cx, cz = t.core_in_expanded
        out[t.x0 : t.x1, t.z0 : t.z1] = cleaned_ex[cx, cz]
        speckle_vals.append(float(stats["speckle_rate"]))

    if np.any(out < 0):
        raise RuntimeError("Missing tile regions detected after expanded cleanup")

    avg_speckle = float(np.mean(speckle_vals)) if speckle_vals else 0.0
    return out, avg_speckle


def run_pipeline(cfg: PipelineConfig, allow_8bit_override: bool = False) -> Dict[str, object]:
    warnings: List[str] = []

    in_dir, height_raw, height_meta, weights_raw, masks_raw, colormap_raw, anchors, objects = _load_inputs(
        cfg,
        allow_8bit_override=allow_8bit_override,
    )

    shape = _target_shape(height_raw, cfg)
    height = resample_height(height_raw, shape)
    weights = resample_weights(weights_raw, shape)
    masks = resample_masks(masks_raw, shape)
    colormap = resample_colormap(colormap_raw, shape) if colormap_raw is not None else None

    y, fit_stats = fit_height_to_budget(
        height,
        total_height=cfg.height.total_height,
        margin_bottom=cfg.height.margin_bottom,
        margin_top=cfg.height.margin_top,
        p_low=cfg.height.percentile_low,
        p_high=cfg.height.percentile_high,
        gamma=cfg.height.gamma,
    )

    if np.min(y) < 0:
        raise RuntimeError("Negative heights detected after fit")

    hydro = {}
    if cfg.hydrology.enabled:
        river_mask = masks.get(cfg.hydrology.river_mask_name)
        y, hydro = apply_hydrology(
            y,
            fill_sinks=cfg.hydrology.fill_sinks,
            river_threshold_percentile=cfg.hydrology.river_threshold_percentile,
            carve_depth=cfg.hydrology.carve_depth,
            river_mask=river_mask,
        )
        masks["river"] = hydro["river_mask"]

    noise_delta = np.zeros_like(y, dtype=np.float32)
    if cfg.noise.enabled:
        water_mask = masks.get("river", None)
        road_mask = masks.get(cfg.noise.road_mask_name, None)
        y, noise_delta = apply_multiscale_noise(
            y,
            macro_amp=cfg.noise.macro_amplitude,
            macro_wavelength=cfg.noise.macro_wavelength,
            micro_amp=cfg.noise.micro_amplitude,
            micro_wavelength=cfg.noise.micro_wavelength,
            seed=cfg.noise.seed,
            water_mask=water_mask,
            road_mask=road_mask,
            suppress_radius=cfg.noise.suppress_near_water_radius,
        )

    if np.min(y) < 0:
        raise RuntimeError("Negative heights detected after hydrology/noise")

    geom = compute_geom_fields(y)
    labels, _material_masks, de_stats = assign_material_labels(
        y_int=y,
        slope=geom["slope_smooth"],
        weights=weights,
        masks=masks,
        layer_names=cfg.materials.layers,
        default_layer=cfg.materials.default_layer,
        sea_level_y=cfg.height.sea_level_y,
        snowline_y=cfg.materials.snowline_y,
        beach_band_dy=cfg.materials.beach_band_dy,
        cliff_slope_high=cfg.materials.cliff_slope_high,
        cliff_slope_low=cfg.materials.cliff_slope_low,
        colormap=colormap,
        palette_match_enabled=cfg.materials.palette_match.enabled,
    )

    labels, avg_speckle = _cleanup_labels_in_expanded_tiles(cfg, labels)

    out_root = map_output_dir(cfg)
    out_tiles = ensure_dir(out_root / "tiles")
    out_runbook = ensure_dir(out_root / "runbook")
    out_qa = ensure_dir(out_root / "qa")

    manifest_rows, tile_vertex_grids = _export_tiles(cfg, y, labels, out_tiles, warnings)

    tiles = build_tiles(y.shape, tile_size=cfg.tiling.tile_size, overlap=cfg.tiling.overlap)
    seam_map, seam_max = seam_diff_report(y, tiles, tile_vertex_grids=tile_vertex_grids)

    if cfg.qa.write_plots:
        save_height_histogram(y, out_qa / "height_hist.png")
        save_seam_heatmap(seam_map, out_qa / "seam_diff_heatmap.png")

    hstats = height_stats(y)
    assert_height_range(y, cfg.qa.assert_height_range[0], cfg.qa.assert_height_range[1])
    assert_seam_threshold(seam_max, cfg.qa.assert_max_seam_diff)

    coverage = material_coverage(labels, cfg.materials.layers)

    summary = {
        "map_name": cfg.project.map_name,
        "input_dir": str(in_dir),
        "output_dir": str(out_root),
        "height_input": height_meta,
        "height_fit": fit_stats,
        "height_stats": hstats,
        "qa": {
            "seam_max_diff": int(seam_max),
            "speckle_rate": avg_speckle,
            "material_coverage": coverage,
        },
        "hydrology": {
            "enabled": cfg.hydrology.enabled,
            "river_pixels": int(np.sum(masks.get("river", np.zeros_like(y, dtype=bool)))),
        },
        "noise": {
            "enabled": cfg.noise.enabled,
            "delta_min": float(np.min(noise_delta)),
            "delta_max": float(np.max(noise_delta)),
        },
        "palette_match": de_stats,
        "anchors_loaded": 0 if anchors is None else len(anchors),
        "objects": objects,
        "warnings": warnings,
    }

    write_json(out_qa / "summary.json", summary)

    write_tile_manifest(out_runbook / "tile_manifest.csv", manifest_rows)
    write_generated_hytale_runbook(
        out_runbook / "hytale_import_runbook.md",
        map_name=cfg.project.map_name,
        import_height=cfg.hytale.default_import_height,
        base_fill_item_id=cfg.hytale.base_fill_item_id,
        material_item_ids=cfg.hytale.material_item_ids,
    )

    return summary
