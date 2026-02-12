import { gunzipSync } from "node:zlib";
import { canonicalize, type CanonicalObject, type Voxel } from "@voxelviewer/core";
import { BlockRegistry, buildUnknownBlockReport, type UnknownBlockReport } from "@voxelviewer/block-registry";

type NbtValue = unknown;
type NbtObject = Record<string, unknown>;

export interface Diagnostic {
  code: string;
  severity: "warning" | "error";
  message: string;
}

export interface SchematicSniffResult {
  match: boolean;
  confidence: "high" | "medium" | "low";
  reasonCodes: string[];
}

export type SchematicParseMode = "strict" | "salvage" | "strict+salvage";
export type SchematicVariant = "mcedit" | "sponge" | "unknown";

export interface SchematicLoadOptions {
  mode?: SchematicParseMode;
  registry: BlockRegistry;
  sourcePath?: string;
}

export interface SchematicLoadResult {
  format: "schematic";
  variant: SchematicVariant;
  valid: boolean;
  parseMode: "strict" | "salvage";
  canonical?: CanonicalObject;
  metadata: Record<string, string>;
  warnings: Diagnostic[];
  errors: Diagnostic[];
  unknownBlocks: UnknownBlockReport;
}

const TAG_END = 0;
const TAG_BYTE = 1;
const TAG_SHORT = 2;
const TAG_INT = 3;
const TAG_LONG = 4;
const TAG_FLOAT = 5;
const TAG_DOUBLE = 6;
const TAG_BYTE_ARRAY = 7;
const TAG_STRING = 8;
const TAG_LIST = 9;
const TAG_COMPOUND = 10;
const TAG_INT_ARRAY = 11;
const TAG_LONG_ARRAY = 12;

class Cursor {
  public offset = 0;
  public constructor(public readonly view: DataView) {}

  public ensure(size: number): void {
    if (this.offset + size > this.view.byteLength) {
      throw new Error(`NBT_TRUNCATED at offset=${this.offset}`);
    }
  }

  public i8(): number {
    this.ensure(1);
    const v = this.view.getInt8(this.offset);
    this.offset += 1;
    return v;
  }

  public u8(): number {
    this.ensure(1);
    const v = this.view.getUint8(this.offset);
    this.offset += 1;
    return v;
  }

  public i16(): number {
    this.ensure(2);
    const v = this.view.getInt16(this.offset, false);
    this.offset += 2;
    return v;
  }

  public i32(): number {
    this.ensure(4);
    const v = this.view.getInt32(this.offset, false);
    this.offset += 4;
    return v;
  }

  public i64(): bigint {
    this.ensure(8);
    const hi = this.view.getInt32(this.offset, false);
    const lo = this.view.getUint32(this.offset + 4, false);
    this.offset += 8;
    return (BigInt(hi) << 32n) + BigInt(lo);
  }

  public f32(): number {
    this.ensure(4);
    const v = this.view.getFloat32(this.offset, false);
    this.offset += 4;
    return v;
  }

  public f64(): number {
    this.ensure(8);
    const v = this.view.getFloat64(this.offset, false);
    this.offset += 8;
    return v;
  }

  public bytes(n: number): Uint8Array {
    this.ensure(n);
    const out = new Uint8Array(this.view.buffer, this.view.byteOffset + this.offset, n);
    this.offset += n;
    return new Uint8Array(out);
  }
}

function utf8(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("utf8");
}

function readString(c: Cursor): string {
  const len = c.i16();
  if (len < 0) throw new Error("NBT_STRING_NEGATIVE_LENGTH");
  return utf8(c.bytes(len));
}

function readPayload(c: Cursor, tagType: number): NbtValue {
  switch (tagType) {
    case TAG_BYTE:
      return c.i8();
    case TAG_SHORT:
      return c.i16();
    case TAG_INT:
      return c.i32();
    case TAG_LONG:
      return c.i64();
    case TAG_FLOAT:
      return c.f32();
    case TAG_DOUBLE:
      return c.f64();
    case TAG_BYTE_ARRAY: {
      const len = c.i32();
      if (len < 0) throw new Error("NBT_BYTE_ARRAY_NEGATIVE_LENGTH");
      return c.bytes(len);
    }
    case TAG_STRING:
      return readString(c);
    case TAG_LIST: {
      const childType = c.u8();
      const len = c.i32();
      if (len < 0) throw new Error("NBT_LIST_NEGATIVE_LENGTH");
      const out: NbtValue[] = [];
      for (let i = 0; i < len; i++) {
        out.push(readPayload(c, childType));
      }
      return out;
    }
    case TAG_COMPOUND: {
      const out: NbtObject = {};
      while (true) {
        const nextType = c.u8();
        if (nextType === TAG_END) break;
        const key = readString(c);
        out[key] = readPayload(c, nextType);
      }
      return out;
    }
    case TAG_INT_ARRAY: {
      const len = c.i32();
      if (len < 0) throw new Error("NBT_INT_ARRAY_NEGATIVE_LENGTH");
      const out = new Array<number>(len);
      for (let i = 0; i < len; i++) out[i] = c.i32();
      return out;
    }
    case TAG_LONG_ARRAY: {
      const len = c.i32();
      if (len < 0) throw new Error("NBT_LONG_ARRAY_NEGATIVE_LENGTH");
      const out = new Array<bigint>(len);
      for (let i = 0; i < len; i++) out[i] = c.i64();
      return out;
    }
    default:
      throw new Error(`NBT_UNSUPPORTED_TAG_${tagType}`);
  }
}

function parseNbt(input: Uint8Array): { rootName: string; root: NbtObject } {
  const c = new Cursor(new DataView(input.buffer, input.byteOffset, input.byteLength));
  const rootType = c.u8();
  if (rootType !== TAG_COMPOUND) {
    throw new Error(`NBT_ROOT_NOT_COMPOUND_${rootType}`);
  }
  const rootName = readString(c);
  const rootPayload = readPayload(c, TAG_COMPOUND);
  if (!rootPayload || typeof rootPayload !== "object" || Array.isArray(rootPayload)) {
    throw new Error("NBT_ROOT_PAYLOAD_INVALID");
  }
  return { rootName, root: rootPayload as NbtObject };
}

function maybeGunzip(input: Uint8Array): Uint8Array {
  if (input.length >= 2 && input[0] === 0x1f && input[1] === 0x8b) {
    return gunzipSync(input);
  }
  return input;
}

function lowerKeys(obj: NbtObject): Record<string, NbtValue> {
  const out: Record<string, NbtValue> = {};
  for (const [k, v] of Object.entries(obj)) {
    out[k.toLowerCase()] = v;
  }
  return out;
}

function asInt(value: NbtValue | undefined): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === "bigint") return Number(value);
  return undefined;
}

function asString(value: NbtValue | undefined): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asByteArray(value: NbtValue | undefined): Uint8Array | undefined {
  return value instanceof Uint8Array ? value : undefined;
}

function asObject(value: NbtValue | undefined): NbtObject | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value) || value instanceof Uint8Array) return undefined;
  return value as NbtObject;
}

function decodeVarints(
  bytes: Uint8Array,
  expectedCount: number,
  salvage: boolean,
  warnings: Diagnostic[],
  errors: Diagnostic[]
): number[] {
  const out: number[] = [];
  let i = 0;
  while (i < bytes.length && out.length < expectedCount) {
    let num = 0;
    let shift = 0;
    let steps = 0;
    while (true) {
      if (i >= bytes.length) {
        if (salvage) {
          warnings.push({ code: "SCHEM_BLOCKDATA_TRUNCATED", severity: "warning", message: "Truncated varint stream." });
          return out;
        }
        errors.push({ code: "SCHEM_BLOCKDATA_TRUNCATED", severity: "error", message: "Truncated varint stream." });
        return out;
      }
      const b = bytes[i++]!;
      num |= (b & 0x7f) << shift;
      shift += 7;
      steps++;
      if ((b & 0x80) === 0) break;
      if (steps > 5) {
        if (salvage) {
          warnings.push({ code: "SCHEM_BLOCKDATA_VARINT_INVALID", severity: "warning", message: "Invalid varint encountered." });
          break;
        }
        errors.push({ code: "SCHEM_BLOCKDATA_VARINT_INVALID", severity: "error", message: "Invalid varint encountered." });
        return out;
      }
    }
    out.push(num >>> 0);
  }
  if (!salvage && out.length !== expectedCount) {
    errors.push({
      code: "SCHEM_BLOCKDATA_COUNT_MISMATCH",
      severity: "error",
      message: `Decoded ${out.length}, expected ${expectedCount}.`
    });
  }
  return out;
}

function sniffByMagic(input: Uint8Array): boolean {
  if (input.length >= 2 && input[0] === 0x1f && input[1] === 0x8b) return true;
  if (input.length >= 3 && input[0] === TAG_COMPOUND && input[1] === 0x00) return true;
  return false;
}

export function sniffSchematic(input: Uint8Array, pathHint = ""): SchematicSniffResult {
  const ext = pathHint.toLowerCase();
  if (ext.endsWith(".schematic") || ext.endsWith(".schem")) {
    return { match: true, confidence: "high", reasonCodes: ["EXTENSION_MATCH"] };
  }
  if (sniffByMagic(input)) {
    return { match: true, confidence: "medium", reasonCodes: ["NBT_MAGIC_LIKE"] };
  }
  return { match: false, confidence: "low", reasonCodes: ["NO_NBT_HINT"] };
}

function parseSchematic(
  bytes: Uint8Array,
  options: SchematicLoadOptions,
  salvage: boolean
): SchematicLoadResult {
  const warnings: Diagnostic[] = [];
  const errors: Diagnostic[] = [];
  const unknownSources: string[] = [];
  const unknownCanonical: string[] = [];
  let canonical: CanonicalObject | undefined;
  let variant: SchematicVariant = "unknown";
  const metadata: Record<string, string> = {};

  let root: NbtObject;
  try {
    const decoded = maybeGunzip(bytes);
    root = parseNbt(decoded).root;
  } catch (error) {
    errors.push({
      code: "SCHEM_NBT_PARSE_FAILED",
      severity: "error",
      message: `NBT parse failed: ${(error as Error).message}`
    });
    return {
      format: "schematic",
      variant,
      valid: false,
      parseMode: salvage ? "salvage" : "strict",
      metadata,
      warnings,
      errors,
      unknownBlocks: { totalUnknown: 0, entries: [] }
    };
  }

  const lower = lowerKeys(root);
  const width = asInt(lower.width);
  const height = asInt(lower.height);
  const length = asInt(lower.length);
  if (!width || !height || !length || width <= 0 || height <= 0 || length <= 0) {
    errors.push({
      code: "SCHEM_DIMENSIONS_INVALID",
      severity: "error",
      message: "Missing or invalid Width/Height/Length."
    });
  }

  const author = asString(lower.author);
  const description = asString(lower.description);
  if (author) metadata.author = author;
  if (description) metadata.description = description;

  const voxels: Voxel[] = [];
  if (width && height && length && width > 0 && height > 0 && length > 0) {
    const expected = width * height * length;
    const blocks = asByteArray(lower.blocks);
    const data = asByteArray(lower.data);
    const addBlocks = asByteArray(lower.addblocks);
    const palette = asObject(lower.palette);
    const blockData = asByteArray(lower.blockdata);

    if (blocks && data) {
      variant = "mcedit";
      const count = salvage ? Math.min(expected, blocks.length, data.length) : expected;
      if (!salvage && (blocks.length < expected || data.length < expected)) {
        errors.push({
          code: "SCHEM_BLOCK_ARRAY_TRUNCATED",
          severity: "error",
          message: `Blocks/Data arrays too short. blocks=${blocks.length} data=${data.length} expected=${expected}`
        });
      }

      for (let i = 0; i < count; i++) {
        const low = blocks[i] ?? 0;
        const d = data[i] ?? 0;
        const addByte = addBlocks ? (addBlocks[Math.floor(i / 2)] ?? 0) : 0;
        const highNibble = i % 2 === 0 ? addByte & 0x0f : (addByte >> 4) & 0x0f;
        const legacyId = low + (highNibble << 8);
        const resolved = options.registry.resolve({ legacyId, legacyData: d });
        if (resolved.unknown) {
          unknownSources.push(resolved.source);
          unknownCanonical.push(resolved.canonical);
        }
        // Avoid exploding memory/mesh cost by storing explicit "air" voxels.
        // MCEdit schematics encode full volumes; our renderer/canonical format expects sparse voxels.
        if (resolved.canonical !== "air" && !resolved.canonical.endsWith(":air")) {
          const x = i % width;
          const z = Math.floor(i / width) % length;
          const y = Math.floor(i / (width * length));
          voxels.push({ x, y, z, blockKey: resolved.canonical });
        }
      }
      if (salvage && count < expected) {
        warnings.push({
          code: "SCHEM_BLOCK_ARRAY_TRUNCATED",
          severity: "warning",
          message: `Parsed partial MCEdit arrays: ${count}/${expected}.`
        });
      }
    } else if (palette && blockData) {
      variant = "sponge";
      const paletteMap = new Map<number, string>();
      for (const [blockName, paletteValue] of Object.entries(palette)) {
        const idx = asInt(paletteValue);
        if (typeof idx !== "number") continue;
        paletteMap.set(idx, blockName);
      }
      const decoded = decodeVarints(blockData, expected, salvage, warnings, errors);
      const count = salvage ? Math.min(decoded.length, expected) : expected;
      if (!salvage && decoded.length < expected) {
        errors.push({
          code: "SCHEM_BLOCKDATA_TRUNCATED",
          severity: "error",
          message: `Decoded only ${decoded.length}/${expected} palette indices.`
        });
      }
      for (let i = 0; i < count; i++) {
        const paletteIdx = decoded[i] ?? 0;
        const fullName = paletteMap.get(paletteIdx) ?? `unknown:palette:${paletteIdx}`;
        const namespaced = fullName.includes("[") ? fullName.slice(0, fullName.indexOf("[")) : fullName;
        const resolved = options.registry.resolve({ namespacedId: namespaced.toLowerCase() });
        if (resolved.unknown) {
          unknownSources.push(resolved.source);
          unknownCanonical.push(resolved.canonical);
        }
        const x = i % width;
        const z = Math.floor(i / width) % length;
        const y = Math.floor(i / (width * length));
        voxels.push({ x, y, z, blockKey: resolved.canonical });
      }
      if (salvage && count < expected) {
        warnings.push({
          code: "SCHEM_BLOCKDATA_TRUNCATED",
          severity: "warning",
          message: `Parsed partial Sponge blockdata: ${count}/${expected}.`
        });
      }
    } else {
      errors.push({
        code: "SCHEM_LAYOUT_UNSUPPORTED",
        severity: "error",
        message: "Missing (Blocks+Data) and missing (Palette+BlockData)."
      });
    }
  }

  if (voxels.length > 0 && (salvage || errors.length === 0)) {
    try {
      canonical = canonicalize(voxels, {
        sourcePath: options.sourcePath,
        author: metadata.author,
        description: metadata.description
      });
    } catch (error) {
      errors.push({
        code: "SCHEM_CANONICALIZE_FAILED",
        severity: "error",
        message: `Canonicalization failed: ${(error as Error).message}`
      });
    }
  }

  return {
    format: "schematic",
    variant,
    valid: !!canonical && (salvage || errors.length === 0),
    parseMode: salvage ? "salvage" : "strict",
    canonical,
    metadata,
    warnings,
    errors,
    unknownBlocks: buildUnknownBlockReport(unknownSources, unknownCanonical)
  };
}

export function loadSchematic(input: Uint8Array, options: SchematicLoadOptions): SchematicLoadResult {
  const mode = options.mode ?? "strict+salvage";
  if (mode === "strict") {
    return parseSchematic(input, options, false);
  }
  if (mode === "salvage") {
    return parseSchematic(input, options, true);
  }
  const strict = parseSchematic(input, options, false);
  if (strict.valid) return strict;
  const salvage = parseSchematic(input, options, true);
  if (strict.errors.length > 0) {
    salvage.warnings.unshift(
      ...strict.errors.map((e) => ({
        code: `STRICT_FALLBACK_${e.code}`,
        severity: "warning" as const,
        message: e.message
      }))
    );
  }
  return salvage;
}
