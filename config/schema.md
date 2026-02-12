# Config Schema

Top-level keys:
- project.map_name: string
- paths.input_root: absolute path to wow.export packages
- paths.output_root: absolute path to output root
- input.allow_8bit_height: bool safety override for 8-bit heightmaps
- height.*: vertical fitting and sea controls
- hydrology.*: sink fill, flow accumulation, river carve controls
- noise.*: macro and micro terrain noise
- materials.*: semantic layer and cleanup controls
- resample.target_resolution: optional integer square resolution
- tiling.tile_size: tile core size
- tiling.overlap: expanded border for seam-safe processing
- outputs.*: target export formats (.obj, .schematic, .bo2) and block ID mapping
- runtime.async_tile_export: enable parallel tile export (deterministic output order)
- runtime.tile_workers: worker count for async export (0 = auto)
- mesh.*: OBJ export controls
- qa.*: assertions and plot outputs
- safety.*: non-fatal tile size/vertex warnings
- hytale.*: import metadata and material->item mapping

Required input package layout:
- <input_root>/<map_name>/height/height.png
- <input_root>/<map_name>/weights/*.png (optional)
- <input_root>/<map_name>/weightmaps/*.png (optional alias)
- <input_root>/<map_name>/masks/*.png (optional)
- <input_root>/<map_name>/color/colormap.png (optional)
- <input_root>/<map_name>/anchors/landmarks.csv (optional)
- <input_root>/<map_name>/objects/*.json|csv (optional)
- <input_root>/<map_name>/placements/*.json|csv (optional)

Notes:
- Height PNG should be 16-bit if possible to avoid terracing.
- 8-bit height input aborts by default unless CLI override is provided.
- Weights are expected in [0, 1] or [0, 255]; pipeline renormalizes per pixel.
- Masks are binary-ish images; non-zero becomes True.
- No per-tile normalization is used. All height fitting is global.
- Path defaults are OS-aware and can be overridden with env vars:
  - HYIMPORTER_BASE_DIR
  - HYIMPORTER_INPUT_ROOT
  - HYIMPORTER_OUTPUT_ROOT
