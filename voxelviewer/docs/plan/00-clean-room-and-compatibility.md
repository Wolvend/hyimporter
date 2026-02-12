# Clean-Room and Compatibility Policy

## Clean-Room Rules

- The new implementation is authored from scratch in this repo.
- `SchematicWebViewer` may be used only for behavior-level validation and public documentation review.
- No direct code copy, no translation of source files, no copy-paste of internal algorithms.
- Any behavior borrowed from public specs must be documented with source attribution.

## Allowed References

- TerrainControl/OpenTerrainGenerator public BO2 spec and public reader behavior as reference.
- Publicly documented format behavior from Hytale-related prefab examples/spec docs.
- Public API docs for SQLite, Electron, React, Three.js.

## Attribution Requirements

- Add `THIRD_PARTY_REFERENCES.md` at implementation time.
- Include TerrainControl/OpenTerrainGenerator source links and license notices.
- Cite spec files and commit hashes used as references.

## Compatibility-Validation Use of `SchematicWebViewer`

- Use as a black-box reference to compare output characteristics:
- Expected camera framing style for object thumbnails.
- General responsiveness patterns in object viewing.
- High-level interaction affordances (search, inspect, orbit/fly style).

## Explicit Non-Goals

- No dependency on `SchematicWebViewer` runtime modules.
- No importing code from that project into the monorepo.
- No attempt to preserve implementation internals; only user-visible behavior parity where relevant.

## Audit Checklist

- Every implemented module includes a brief "source of truth" comment in docs.
- PR checklist includes "clean-room verified" item.
- CI includes license notice validation for external references.
