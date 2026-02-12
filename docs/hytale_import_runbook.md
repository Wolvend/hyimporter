# Hytale OBJ Import Runbook

This runbook is Windows/Hytale-side.

## Recommended: Use Async Schematic Import For Large Worlds
Hytale's in-game OBJ import/converter is currently very synchronous and can freeze/hang on big tiles.

If you installed either of these mods, prefer them for tiled terrain:
- `cc.invic_SchematicLoader` (supports `.schematic` and `.schem`, pastes in async batches)
- `thirtyvirus_SchematicImporter` (supports `.schem` and `.litematic`, includes block mapping UI/config)

HyImporter already outputs `.schematic` tiles, so **SchematicLoader is the fastest path** to async paste today.

### Async SchematicLoader workflow (best current option)
1. Ensure your world has the mod data dir:
   - `C:\\Users\\<you>\\AppData\\Roaming\\Hytale\\UserData\\Saves\\<WorldName>\\mods\\cc.invic_SchematicLoader\\schematics\\`
2. Copy HyImporter tiles:
   - From: `C:\\hyimporter\\out\\<map_name>\\tiles\\*.schematic`
   - To: `...\\cc.invic_SchematicLoader\\schematics\\`
   - Or run:
     - `powershell -ExecutionPolicy Bypass -File scripts/sync_to_hytale_schematicloader.ps1 -MapName <map_name> -WorldName <WorldName>`
     - From WSL: `bash scripts/sync_to_hytale_schematicloader.sh <map_name> /mnt/c/hyimporter/out <WorldName>`
3. Restart the world/server (the mod registers file-specific `/schem load <file>` commands at startup).
4. In game:
   - `/schem list`
   - `/schem load <tile_0_0.schematic>`
   - Move to the intended paste origin for that tile (use `runbook/tile_manifest.csv`).
   - `/schem paste`

Notes:
- This mod pastes in async batches (so it stays responsive), but it pastes relative to the player position.
- Keep `outputs.schematic_full_volume: false` (surface-only) for sane import sizes.

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
