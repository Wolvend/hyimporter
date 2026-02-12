# Renderer, Mesher, and Thumbnail Plan

## Scope

- Three.js rendering primitives for both CLI thumbnails and desktop viewport.
- Greedy meshing for opaque blocks and optional transparent pass.
- Deterministic thumbnail generation.

## Meshing

- Input: normalized voxel volume.
- Partition voxels into:
  - opaque set,
  - transparent/alpha set.
- Greedy mesh opaque set by axis-aligned face merging.
- Transparent blocks in separate mesh/material group (optional first milestone).

## Determinism Controls

- Sort voxel input before meshing using canonical order from `core`.
- Stable material assignment by canonical block key hash.
- Fixed floating-point math paths where possible.
- Fixed renderer settings:
  - antialias off for thumbnails,
  - fixed tone mapping,
  - fixed background color.

## Thumbnail Rendering

- Fixed output size default: `256x256`.
- Camera: consistent isometric perspective.
- Fit strategy:
  - compute normalized bounds center,
  - derive camera distance from max dimension and fixed FOV,
  - apply fixed yaw/pitch constants.

- Debug mode:
  - optional additional projections `front`, `top`, `side`.

## Cache Keys

- `meshCacheKey = sha256 + mesherVersion + blockProfileVersion`.
- `thumbCacheKey = meshCacheKey + thumbnailRendererVersion + thumbConfig`.

## CLI Thumbnail Failure Mode

- On render failure, generate deterministic error thumbnail:
  - solid background,
  - centered error glyph/text code,
  - error code embedded in metadata.

