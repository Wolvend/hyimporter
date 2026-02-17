from __future__ import annotations

from .mcp_tools import (
    batch_obj_to_schematic,
    list_maps,
    list_obj_exports,
    list_wowexport_maps,
    run_obj_to_schematic,
    run_world_build,
    scan_wowexport_map,
    validate_map,
    voxelviewer_screenshot_bo2,
    wowexport_map_export_placements_manifest,
    wowexport_map_models_to_schematic,
)


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency: mcp. Install requirements first (pip install -r requirements.txt)."
        ) from exc

    mcp = FastMCP("hyimporter")

    @mcp.tool()
    def hyimporter_list_maps(input_root: str = "/mnt/c/hyimporter/input", limit: int = 100) -> dict:
        """List candidate wow.export map folders and readiness signals."""
        return list_maps(input_root=input_root, limit=limit)

    @mcp.tool()
    def hyimporter_validate_map(map_name: str, input_root: str = "/mnt/c/hyimporter/input") -> dict:
        """Validate required map inputs before running a build."""
        return validate_map(input_root=input_root, map_name=map_name)

    @mcp.tool()
    def hyimporter_build_world(
        config_path: str,
        allow_8bit_height: bool = False,
        sync_tiles: bool = False,
        tile_workers: int | None = None,
    ) -> dict:
        """Run hyimporter world build and return summary paths/stats."""
        return run_world_build(
            config_path=config_path,
            allow_8bit_height=allow_8bit_height,
            sync_tiles=sync_tiles,
            tile_workers=tile_workers,
        )

    @mcp.tool()
    def hyimporter_obj_to_schematic(
        obj_path: str,
        schematic_path: str,
        bo2_path: str = "",
        block_id: int = 1,
        padding: int = 1,
        voxel_scale: float = 1.0,
        wireframe: bool = False,
    ) -> dict:
        """Convert OBJ mesh into schematic/BO2 via hyimporter voxelization utility."""
        return run_obj_to_schematic(
            obj_path=obj_path,
            schematic_path=schematic_path,
            bo2_path=bo2_path,
            block_id=block_id,
            padding=padding,
            voxel_scale=voxel_scale,
            wireframe=wireframe,
        )

    @mcp.tool()
    def hyimporter_list_wow_export_objs(
        export_root: str, max_results: int = 200, name_filter: str = ""
    ) -> dict:
        """Scan a wow.export output tree for OBJ files."""
        return list_obj_exports(export_root=export_root, max_results=max_results, name_filter=name_filter)

    @mcp.tool()
    def hyimporter_list_wow_export_maps(export_root: str, limit: int = 100) -> dict:
        """List wow.export map packages (export_root/maps/*)."""
        return list_wowexport_maps(export_root=export_root, limit=limit)

    @mcp.tool()
    def hyimporter_scan_wow_export_map(
        map_dir: str,
        max_tile_details: int = 100,
        compute_bboxes: bool = True,
        parse_placements: bool = True,
        max_placement_rows_per_file: int = 0,
    ) -> dict:
        """Scan a wow.export map folder for tile OBJ/MTL/texture/csv consistency and basic stats."""
        return scan_wowexport_map(
            map_dir=map_dir,
            max_tile_details=max_tile_details,
            compute_bboxes=compute_bboxes,
            parse_placements=parse_placements,
            max_placement_rows_per_file=max_placement_rows_per_file,
        )

    @mcp.tool()
    def hyimporter_wow_export_map_export_placements_manifest(
        export_root: str,
        map_dir: str,
        out_root: str,
        name_filter: str = "",
        max_csv_files: int = 0,
        max_rows_per_csv: int = 0,
        include_missing_models: bool = False,
    ) -> dict:
        """Export map placement CSV rows to per-tile JSONL + manifest under out_root."""
        return wowexport_map_export_placements_manifest(
            export_root=export_root,
            map_dir=map_dir,
            out_root=out_root,
            name_filter=name_filter,
            max_csv_files=max_csv_files,
            max_rows_per_csv=max_rows_per_csv,
            include_missing_models=include_missing_models,
        )

    @mcp.tool()
    def hyimporter_wow_export_map_models_to_schematic(
        export_root: str,
        map_dir: str,
        out_root: str,
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
    ) -> dict:
        """Convert unique placed-object OBJs referenced by a map into .schematic/.bo2 outputs."""
        return wowexport_map_models_to_schematic(
            export_root=export_root,
            map_dir=map_dir,
            out_root=out_root,
            name_filter=name_filter,
            max_models=max_models,
            workers=workers,
            block_id=block_id,
            padding=padding,
            voxel_scale=voxel_scale,
            target_max_dim=target_max_dim,
            wireframe=wireframe,
            write_bo2=write_bo2,
            resume=resume,
            max_obj_mb=max_obj_mb,
            max_cells=max_cells,
        )

    @mcp.tool()
    def hyimporter_voxelviewer_screenshot_bo2(
        bo2_path: str,
        png_path: str,
        zoom: int = 10,
        yaw: int = 270,
        width: int = 1365,
        height: int = 768,
        timeout_seconds: int = 180,
        dry_run: bool = False,
    ) -> dict:
        """Render a .bo2 file via tools/voxelviewer and write a PNG screenshot."""
        return voxelviewer_screenshot_bo2(
            bo2_path=bo2_path,
            png_path=png_path,
            zoom=zoom,
            yaw=yaw,
            width=width,
            height=height,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
        )

    @mcp.tool()
    def hyimporter_batch_obj_to_schematic(
        export_root: str,
        out_root: str,
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
    ) -> dict:
        """Batch convert every .obj under export_root into .schematic/.bo2 under out_root."""
        return batch_obj_to_schematic(
            export_root=export_root,
            out_root=out_root,
            name_filter=name_filter,
            max_files=max_files,
            workers=workers,
            block_id=block_id,
            padding=padding,
            voxel_scale=voxel_scale,
            wireframe=wireframe,
            write_bo2=write_bo2,
            resume=resume,
            max_obj_mb=max_obj_mb,
            max_cells=max_cells,
        )

    return mcp


def main() -> None:
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
