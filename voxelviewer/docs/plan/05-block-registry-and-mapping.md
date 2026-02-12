# Block Registry and Mapping Plan

## Purpose

- Normalize multiple block identifier styles into canonical `blockKey`.
- Preserve unknown blocks without losing geometry.

## Supported Inputs

- Legacy numeric + data:
  - `id: number`
  - `data: number`
- Namespaced modern IDs:
  - `minecraft:stone`
  - `minecraft:oak_log[axis=y]` (state string support planned)

## Profiles

- Built-in profile `mc_1_12_legacy`.
- Built-in profile `mc_1_16_namespaced`.
- Future profiles can be added via JSON/YAML descriptors.

## Override Resolution Order

1. User YAML override file(s).
2. Project-level profile mapping.
3. Built-in profile defaults.
4. Unknown fallback key.

## Unknown Block Handling

- Unknown blocks are assigned placeholder `blockKey`:
  - `unknown:legacy:<id>:<data>`
  - `unknown:namespaced:<value>`
- Object record stores unknown count and detailed list.
- Renderer assigns deterministic placeholder color by hash of unknown key.

## Unknown Blocks Report Shape

```ts
interface UnknownBlockReport {
  totalUnknown: number;
  entries: Array<{
    source: string;
    canonical: string;
    occurrences: number;
  }>;
}
```

## Config File Format (YAML)

```yaml
profile: mc_1_12_legacy
overrides:
  legacy:
    "5:2": "minecraft:birch_planks"
  namespaced:
    "mod:block_x": "minecraft:stone"
```

