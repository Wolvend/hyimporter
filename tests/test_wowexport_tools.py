from pathlib import Path

import json

from hyimporter.mcp_tools import (
    scan_wowexport_map,
    wowexport_map_export_placements_manifest,
    wowexport_map_models_to_schematic,
)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_scan_and_convert_wowexport_map_models_smoke(tmp_path: Path) -> None:
    export_root = tmp_path / "wow.export"
    map_dir = export_root / "maps" / "testmap"
    out_root = tmp_path / "out"

    # Minimal tile content (the scan tool expects adt_*.obj).
    _write_text(
        map_dir / "adt_1_2.obj",
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n",
    )
    _touch(map_dir / "adt_1_2.mtl")
    _touch(map_dir / "tex_1_2.png")

    # Minimal placed model.
    _write_text(
        export_root / "world" / "mymodel.obj",
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n",
    )

    # wow.export placement CSVs are semicolon-delimited and refer to Windows-style relative paths.
    _write_text(
        map_dir / "adt_1_2_ModelPlacementInformation.csv",
        "\n".join(
            [
                "ModelFile;PositionX;PositionY;PositionZ;RotationX;RotationY;RotationZ;RotationW;ScaleFactor;ModelId;Type;FileDataID;DoodadSetIndexes;DoodadSetNames",
                r"..\..\world\mymodel.obj;0;0;0;0;0;0;;1.0;0;m2;0;0;",
                "",
            ]
        ),
    )

    scan = scan_wowexport_map(map_dir=map_dir, max_tile_details=10, compute_bboxes=True, parse_placements=True)
    assert scan["ok"] is True
    assert scan["tile_count"] == 1
    assert scan["missing"]["tex"] == 0
    assert scan["missing"]["placements_csv"] == 0

    placements = wowexport_map_export_placements_manifest(
        export_root=export_root,
        map_dir=map_dir,
        out_root=out_root,
        max_csv_files=1,
        max_rows_per_csv=10,
        include_missing_models=False,
    )
    assert placements["ok"] is True
    assert placements["csv_files_scanned"] == 1
    assert (out_root / "placements" / "adt_1_2.jsonl").exists()
    assert (out_root / "wowexport_placements_manifest.json").exists()

    first = (out_root / "placements" / "adt_1_2.jsonl").read_text(encoding="utf-8").splitlines()[0]
    rec = json.loads(first)
    assert rec["model"]["rel"] == "world/mymodel.obj"
    assert rec["artifact"]["bo2"] == "models/world/mymodel.bo2"
    assert rec["artifact"]["schematic"] == "models/world/mymodel.schematic"

    summary = wowexport_map_models_to_schematic(
        export_root=export_root,
        map_dir=map_dir,
        out_root=out_root,
        workers=1,
        target_max_dim=16,
        write_bo2=True,
        resume=False,
        max_obj_mb=1.0,
        max_cells=1_000_000,
    )
    assert summary["ok"] == 1
    assert summary["failed"] == 0

    assert (out_root / "models" / "world" / "mymodel.schematic").exists()
    assert (out_root / "models" / "world" / "mymodel.bo2").exists()
    assert (out_root / "wowexport_models_manifest.json").exists()

    manifest = json.loads((out_root / "wowexport_models_manifest.json").read_text(encoding="utf-8"))
    assert manifest["params"]["voxel_scale"] == 0.0  # auto-fit by default
    assert manifest["results"][0]["voxel_scale"] > 0
    assert manifest["results"][0]["voxel_scale_mode"] in ("fit", "fixed")
