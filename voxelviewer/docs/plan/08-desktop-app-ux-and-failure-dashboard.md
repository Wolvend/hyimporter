# Desktop App UX and Failure Dashboard Plan

## App Stack

- Electron main process for window lifecycle and safe file/DB access.
- React renderer process for UI.
- Three.js viewport for object visualization.

## Layout

- Left pane:
  - searchable object list with thumbnails,
  - filter controls.
- Main pane:
  - interactive 3D viewport with fly controls.
- Right pane:
  - metadata, palette summary, unknown block list, parse diagnostics.

## Required Filters

- Format (`bo2`, `hytale`).
- Dimensions (`dx`, `dy`, `dz` ranges).
- Block count range.
- Valid/invalid toggle.
- Unknown block count threshold.
- Tag text search (`author`, `description`, raw tags).

## Viewer Controls

- WASD + mouse look fly mode.
- Speed modifier keys.
- Reset camera and fit-to-object actions.
- Wireframe/debug overlays optional.

## Failure Dashboard

- Dedicated table for invalid objects and warning-heavy objects.
- Sort by:
  - error type,
  - warning count,
  - unknown block count,
  - file path.
- Click row to open metadata + raw ingestion report.

## Export Actions

- Export normalized object as debug JSON voxel list.
- Optional export to `.schem` in later milestone.
- Export includes canonical hash and normalization metadata.

## Responsiveness Constraints

- List virtualization for large catalogs.
- Mesh generation for selected object only in viewport.
- Keep parse/index actions off UI thread.

