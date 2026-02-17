# HyImporter Agent Instructions

This repo contains HyImporter, a reproducible terrain pipeline that converts export inputs (currently focused on WoW via `wow.export`) into seam-safe OBJ tiles (and optional `.schematic`/`.bo2`) for Hytale workflows.

## Guardrails
- Keep changes small and reviewable. Avoid drive-by refactors.
- Do not commit generated artifacts:
  - `out/`
  - `*.log`
  - local `config.yaml`
- Treat changes to protocol/tool boundaries as safety-critical:
  - CLI contracts (`scripts/*.sh`, `python -m hyimporter.*`)
  - MCP tool schemas and argument semantics

## Local Verification
Recommended test loop:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=src python -m pytest -q
```

If tests require large external assets (maps/exports), prefer adding a small unit test or a deterministic fixture instead of relying on local data.

## Notes
- Prefer deterministic outputs (stable ordering, fixed seeds) so diffs and regressions are easy to spot.
- Avoid opening network listeners or widening bind addresses without explicit approval.
