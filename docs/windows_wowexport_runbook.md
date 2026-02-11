# Windows wow.export Runbook

This runbook is Windows-only.

## 1) Install wow.export (Windows GUI)
1. Download the Windows build of wow.export from its official release page.
2. Unzip/install it on Windows.
3. Launch wow.export.

## 2) Set WoW install path
In wow.export settings, set the WoW installation directory.
Example:
- D:\World of Warcraft\_retail_

Use your actual install path.

## 3) Select map or zone
1. Open the Zones / overhead map viewer in wow.export.
2. Select the map package to export.

## 4) Export required data
Export the following from wow.export:
- Heightmap(s) (prefer 16-bit height output)
- Terrain layer alpha maps / weightmaps (if available)
- Optional colormap / zone texture reference

Set destination exactly to:
- C:\hyimporter\input\<map_name>\

This path is critical because WSL reads the same files at:
- /mnt/c/hyimporter/input/<map_name>/

## 5) Package structure convention
Keep all exports in one package with these subfolders:
- height/
- weights/
- masks/
- color/
- anchors/

Minimum required file:
- height/height.png

## Per-tile height exports
If wow.export emits per-tile heights instead of one stitched heightmap:
1. Keep them under height/tiles/.
2. Option A: stitch externally into height/height.png before running pipeline.
3. Option B: keep tile files; modify the pipeline input adapter to read tiled height sources.

The default pipeline expects height/height.png.
