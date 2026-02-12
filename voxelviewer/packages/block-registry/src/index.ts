import { readFileSync } from "node:fs";
import YAML from "js-yaml";

export type BlockProfileName = "mc_1_12_legacy" | "mc_1_16_namespaced";

export interface BlockQuery {
  namespacedId?: string;
  legacyId?: number;
  legacyData?: number;
}

export interface BlockResolution {
  canonical: string;
  unknown: boolean;
  source: string;
}

export interface UnknownBlockReportEntry {
  source: string;
  canonical: string;
  occurrences: number;
}

export interface UnknownBlockReport {
  totalUnknown: number;
  entries: UnknownBlockReportEntry[];
}

export interface BlockRegistryOverrides {
  profile?: BlockProfileName;
  overrides?: {
    namespaced?: Record<string, string>;
    legacy?: Record<string, string>;
  };
}

interface ProfileData {
  namespaced: Record<string, string>;
  legacy: Record<string, string>;
}

const PROFILES: Record<BlockProfileName, ProfileData> = {
  mc_1_12_legacy: {
    namespaced: {
      "minecraft:air": "minecraft:air",
      "minecraft:stone": "minecraft:stone",
      "minecraft:dirt": "minecraft:dirt",
      "minecraft:grass_block": "minecraft:grass_block",
      "minecraft:oak_planks": "minecraft:oak_planks"
    },
    legacy: {
      "0:0": "minecraft:air",
      "1:0": "minecraft:stone",
      "2:0": "minecraft:grass_block",
      "3:0": "minecraft:dirt",
      "5:0": "minecraft:oak_planks",
      "5:1": "minecraft:spruce_planks",
      "5:2": "minecraft:birch_planks"
    }
  },
  mc_1_16_namespaced: {
    namespaced: {
      "minecraft:air": "minecraft:air",
      "minecraft:stone": "minecraft:stone",
      "minecraft:dirt": "minecraft:dirt",
      "minecraft:grass_block": "minecraft:grass_block",
      "minecraft:oak_planks": "minecraft:oak_planks",
      "minecraft:oak_log": "minecraft:oak_log"
    },
    legacy: {
      "0:0": "minecraft:air"
    }
  }
};

function legacyKey(id: number, data: number): string {
  return `${id}:${data}`;
}

export class BlockRegistry {
  private readonly profile: BlockProfileName;
  private readonly namespaced: Record<string, string>;
  private readonly legacy: Record<string, string>;

  public constructor(profile: BlockProfileName = "mc_1_12_legacy", overrides?: BlockRegistryOverrides) {
    const mergedProfile = overrides?.profile ?? profile;
    this.profile = mergedProfile;
    const base = PROFILES[mergedProfile];
    this.namespaced = {
      ...base.namespaced,
      ...(overrides?.overrides?.namespaced ?? {})
    };
    this.legacy = {
      ...base.legacy,
      ...(overrides?.overrides?.legacy ?? {})
    };
  }

  public resolve(query: BlockQuery): BlockResolution {
    if (query.namespacedId) {
      const normalized = query.namespacedId.trim().toLowerCase();
      const mapped = this.namespaced[normalized];
      if (mapped) {
        return { canonical: mapped, unknown: false, source: normalized };
      }
      return {
        canonical: `unknown:namespaced:${normalized}`,
        unknown: true,
        source: normalized
      };
    }

    if (Number.isInteger(query.legacyId)) {
      const data = Number.isInteger(query.legacyData) ? (query.legacyData as number) : 0;
      const key = legacyKey(query.legacyId as number, data);
      const mapped = this.legacy[key];
      if (mapped) {
        return { canonical: mapped, unknown: false, source: key };
      }
      return {
        canonical: `unknown:legacy:${key}`,
        unknown: true,
        source: key
      };
    }

    return {
      canonical: "unknown:unresolved",
      unknown: true,
      source: "unresolved"
    };
  }

  public getProfileName(): BlockProfileName {
    return this.profile;
  }
}

export function readOverridesFromYaml(path: string): BlockRegistryOverrides {
  const raw = readFileSync(path, "utf8");
  const parsed = YAML.load(raw);
  if (!parsed || typeof parsed !== "object") {
    return {};
  }
  const obj = parsed as Record<string, unknown>;
  const profile = obj.profile as BlockProfileName | undefined;
  const overridesObj = (obj.overrides ?? {}) as Record<string, unknown>;
  const out: BlockRegistryOverrides = {
    overrides: {
      namespaced: (overridesObj.namespaced ?? {}) as Record<string, string>,
      legacy: (overridesObj.legacy ?? {}) as Record<string, string>
    }
  };
  if (profile) {
    out.profile = profile;
  }
  return out;
}

export function buildUnknownBlockReport(sources: string[], canonicalKeys: string[]): UnknownBlockReport {
  const counts = new Map<string, UnknownBlockReportEntry>();
  for (let i = 0; i < sources.length; i++) {
    const source = sources[i] ?? "unknown";
    const canonical = canonicalKeys[i] ?? "unknown:unresolved";
    const mapKey = `${source}|${canonical}`;
    const existing = counts.get(mapKey);
    if (existing) {
      existing.occurrences += 1;
    } else {
      counts.set(mapKey, { source, canonical, occurrences: 1 });
    }
  }
  const entries = [...counts.values()].sort((a, b) => b.occurrences - a.occurrences || a.source.localeCompare(b.source));
  return {
    totalUnknown: sources.length,
    entries
  };
}
