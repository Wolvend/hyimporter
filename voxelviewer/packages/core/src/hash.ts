import { createHash } from "node:crypto";
import { Buffer } from "node:buffer";
import type { CanonicalHashResult, CanonicalObject, Voxel } from "./types.js";
import { sortCanonicalVoxels } from "./canonical.js";

function encodeString(target: number[], value: string): void {
  const utf8 = Buffer.from(value, "utf8");
  writeU32LE(target, utf8.length);
  for (const byte of utf8) {
    target.push(byte);
  }
}

function writeU32LE(target: number[], value: number): void {
  target.push(value & 0xff, (value >>> 8) & 0xff, (value >>> 16) & 0xff, (value >>> 24) & 0xff);
}

function writeI32LE(target: number[], value: number): void {
  const u = value >>> 0;
  writeU32LE(target, u);
}

function encodeVoxel(target: number[], voxel: Voxel): void {
  writeI32LE(target, voxel.x);
  writeI32LE(target, voxel.y);
  writeI32LE(target, voxel.z);
  encodeString(target, voxel.blockKey);
}

export function encodeCanonicalBytes(object: CanonicalObject): Uint8Array {
  const bytes: number[] = [];

  // Magic VV01
  bytes.push(0x56, 0x56, 0x30, 0x31);
  // Endianness marker (little-endian)
  bytes.push(0x01);

  const metadataEntries = Object.entries(object.metadata)
    .filter(([, value]) => value !== undefined)
    .map(([key, value]) => [key, JSON.stringify(value)] as const)
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));

  writeU32LE(bytes, metadataEntries.length);
  for (const [key, value] of metadataEntries) {
    encodeString(bytes, key);
    encodeString(bytes, value);
  }

  const sortedVoxels = sortCanonicalVoxels(object.voxels);
  writeU32LE(bytes, sortedVoxels.length);
  for (const voxel of sortedVoxels) {
    encodeVoxel(bytes, voxel);
  }

  return Uint8Array.from(bytes);
}

export function hashCanonicalObject(object: CanonicalObject): CanonicalHashResult {
  const canonicalBytes = encodeCanonicalBytes(object);
  const sha256 = createHash("sha256").update(canonicalBytes).digest("hex");
  return { sha256, canonicalBytes };
}

