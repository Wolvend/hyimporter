# Hytale OBJ Import Runbook

This runbook is Windows/Hytale-side.

## 1) Copy generated OBJ tiles into import location
From WSL outputs:
- /mnt/c/hyimporter/out/<map_name>/tiles/
- Base terrain filenames: tile_<i>_<j>.obj
- Surface shell filenames: tile_<i>_<j>__<material>.obj

On Windows, copy or link to your Hytale import models path (or server imports/models folder if applicable).

## 2) Open Hytale Creative Tools
Navigate:
- Creative Tools -> World -> Import OBJ

For each OBJ:
1. Browse to the file.
2. Set Height in blocks.
   - Default target: 320
   - If scaling mismatch happens, use per-tile recommended height from tile meta.json
3. Set Fill Block Pattern (Item ID).
4. For surface shell OBJs, set Fill solid OFF.
5. Import to clipboard.
6. Paste at target coordinates.

## 3) Placement order
Recommended:
1. Import all base volume OBJs first (stone fill).
2. Import material shell OBJs (grass, dirt, rock, sand, snow, etc.).

## 4) Tile positioning
Use:
- runbook/tile_manifest.csv

Columns include tile_i, tile_j, and world placement x0, z0.
Paste each tile at the listed origin to avoid seams.

## 5) If dummy bbox stabilization fails
If Hytale ignores the intended bounding box stabilization:
- Disable bbox stabilization in config and rebuild
- Or keep it enabled but set Height manually per tile using meta.json guidance
