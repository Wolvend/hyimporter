from pathlib import Path

import pytest

from hyimporter.mcp_tools import (
    batch_obj_to_schematic,
    list_maps,
    list_obj_exports,
    run_obj_to_schematic,
    validate_map,
    voxelviewer_screenshot_bo2,
)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_list_maps_and_validate_map(tmp_path):
    input_root = tmp_path / "input"
    map_ok = input_root / "ShadowmoonGreenhouse"
    map_bad = input_root / "BrokenMap"

    _touch(map_ok / "height" / "height.png")
    _touch(map_ok / "weights" / "grass.png")
    _touch(map_ok / "color" / "colormap.png")
    _touch(map_bad / "weights" / "dirt.png")

    listing = list_maps(input_root, limit=10)
    assert listing["exists"] is True
    assert listing["total_maps"] == 2
    assert listing["returned_maps"] == 2

    by_name = {entry["map_name"]: entry for entry in listing["maps"]}
    assert by_name["ShadowmoonGreenhouse"]["has_height_png"] is True
    assert by_name["BrokenMap"]["has_height_png"] is False

    ok_result = validate_map(input_root=input_root, map_name="ShadowmoonGreenhouse")
    assert ok_result["ok"] is True
    assert ok_result["errors"] == []

    bad_result = validate_map(input_root=input_root, map_name="BrokenMap")
    assert bad_result["ok"] is False
    assert any("height/height.png" in err for err in bad_result["errors"])


def test_list_obj_exports_limit_and_filter(tmp_path):
    export_root = tmp_path / "wowexport"
    _touch(export_root / "A" / "building.obj")
    _touch(export_root / "A" / "building.mtl")
    _touch(export_root / "B" / "tree.obj")

    limited = list_obj_exports(export_root=export_root, max_results=1)
    assert limited["exists"] is True
    assert limited["returned_count"] == 1
    assert limited["total_matching"] == 2
    assert limited["truncated"] is True

    filtered = list_obj_exports(export_root=export_root, max_results=10, name_filter="tree")
    assert filtered["returned_count"] == 1
    assert filtered["results"][0]["relative_path"].endswith("tree.obj")


def test_run_obj_to_schematic_requires_existing_obj(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_obj_to_schematic(
            obj_path=tmp_path / "missing.obj",
            schematic_path=tmp_path / "out" / "model.schematic",
        )


def test_batch_obj_to_schematic_smoke(tmp_path):
    export_root = tmp_path / "wowexport"
    out_root = tmp_path / "out"
    obj_dir = export_root / "maps" / "test"
    obj_dir.mkdir(parents=True, exist_ok=True)

    (obj_dir / "a.obj").write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
    (obj_dir / "b.obj").write_text("v 0 0 0\nv 2 0 0\nv 0 2 0\nf 1 2 3\n", encoding="utf-8")

    summary = batch_obj_to_schematic(
        export_root=export_root,
        out_root=out_root,
        workers=1,
        voxel_scale=1.0,
        write_bo2=True,
        resume=False,
        max_obj_mb=1.0,
        max_cells=1_000_000,
    )
    assert summary["ok"] == 2
    assert summary["failed"] == 0

    assert (out_root / "maps" / "test" / "a.schematic").exists()
    assert (out_root / "maps" / "test" / "a.bo2").exists()


def test_voxelviewer_screenshot_bo2_dry_run(tmp_path: Path) -> None:
    bo2 = tmp_path / "model.bo2"
    bo2.write_text("[META]\n\n[DATA]\n0,0,0,1\n", encoding="utf-8")
    out = tmp_path / "out.png"

    res = voxelviewer_screenshot_bo2(bo2_path=bo2, png_path=out, dry_run=True)
    assert res["ok"] is True
    assert res["dry_run"] is True
    assert "screenshot_bo2.js" in res["command"]
