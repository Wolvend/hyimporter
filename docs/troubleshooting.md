# Troubleshooting

## Terracing from low-bit height
Symptom:
- Stepped terrain plateaus

Fix:
- Export 16-bit height from wow.export
- Apply mild smoothing before final quantization
- Avoid 8-bit intermediate height storage
- Pipeline aborts on 8-bit by default; use `--allow-8bit-height` only as last resort

## Tile seams
Symptom:
- Visible cracks or step differences at tile borders

Fix:
- Use overlap processing (expanded tiles)
- Never perform per-tile normalization
- Verify seam QA report and max border diff = 0

## Voxel confetti
Symptom:
- Tiny random material islands

Fix:
- Keep small material palette
- Use majority filter + connected component cleanup
- Keep dithering OFF by default

## Green cliffs
Symptom:
- Grass on steep cliff walls

Fix:
- Enforce slope cliff gate with hysteresis
- Force rock on stable cliff mask
- Apply snowline override as final gate

## Hytale import scale mismatch
Symptom:
- Imported OBJ is too tall/short

Fix:
- If bbox stabilization is unreliable, set Height manually per tile
- Read expected range and import guidance from tile meta.json

## Flat-looking terrain at 320 high
Symptom:
- Loss of relief or compressed silhouettes

Fix:
- Confirm percentile clamp defaults [1,99]
- Use gamma < 1.0 (default 0.85) to preserve midlands
- Check sea level and snowline thresholds
- Increase macro noise slightly if needed
