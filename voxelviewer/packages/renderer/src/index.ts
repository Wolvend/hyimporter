import { createHash } from "node:crypto";
import { PNG } from "pngjs";
import {
  Matrix4,
  PerspectiveCamera,
  Vector3
} from "three";
import type { CanonicalObject } from "@voxelviewer/core";

export interface GreedyQuad {
  axis: 0 | 1 | 2;
  dir: 1 | -1;
  x: number;
  y: number;
  z: number;
  w: number;
  h: number;
  blockKey: string;
  transparent: boolean;
}

export interface ThumbnailOptions {
  width?: number;
  height?: number;
  background?: { r: number; g: number; b: number; a?: number };
  yawDeg?: number;
  pitchDeg?: number;
  fovDeg?: number;
}

export function blockIsTransparent(blockKey: string): boolean {
  const k = blockKey.toLowerCase();
  return (
    k.includes("glass") ||
    k.includes("water") ||
    k.includes("leaves") ||
    k.includes("ice")
  );
}

function stableHash32(input: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export function blockColor(blockKey: string): { r: number; g: number; b: number } {
  if (blockKey.startsWith("unknown:")) {
    return { r: 210, g: 80, b: 160 };
  }
  const h = stableHash32(blockKey);
  const r = 48 + ((h >>> 16) & 0x7f);
  const g = 48 + ((h >>> 8) & 0x7f);
  const b = 48 + (h & 0x7f);
  return { r, g, b };
}

function voxelMap(canonical: CanonicalObject): Map<string, string> {
  const map = new Map<string, string>();
  for (const v of canonical.voxels) {
    map.set(`${v.x},${v.y},${v.z}`, v.blockKey);
  }
  return map;
}

function getVoxel(map: Map<string, string>, x: number, y: number, z: number, dx: number, dy: number, dz: number): string | undefined {
  if (x < 0 || y < 0 || z < 0 || x >= dx || y >= dy || z >= dz) {
    return undefined;
  }
  return map.get(`${x},${y},${z}`);
}

function cellEquals(a: MaskCell | null, b: MaskCell | null): boolean {
  if (!a || !b) return false;
  return a.blockKey === b.blockKey && a.dir === b.dir && a.transparent === b.transparent;
}

interface MaskCell {
  blockKey: string;
  dir: 1 | -1;
  transparent: boolean;
}

export function greedyMesh(canonical: CanonicalObject): GreedyQuad[] {
  const bounds = canonical.boundsNormalized;
  const dims: [number, number, number] = [bounds.dx, bounds.dy, bounds.dz];
  const vox = voxelMap(canonical);
  const quads: GreedyQuad[] = [];

  for (let d = 0 as 0 | 1 | 2; d < 3; d = (d + 1) as 0 | 1 | 2) {
    const u = ((d + 1) % 3) as 0 | 1 | 2;
    const v = ((d + 2) % 3) as 0 | 1 | 2;
    const x = [0, 0, 0] as [number, number, number];
    const q = [0, 0, 0] as [number, number, number];
    q[d] = 1;
    const mask = new Array<MaskCell | null>(dims[u] * dims[v]);

    for (x[d] = -1; x[d] < dims[d]; x[d]++) {
      let n = 0;
      for (x[v] = 0; x[v] < dims[v]; x[v]++) {
        for (x[u] = 0; x[u] < dims[u]; x[u]++) {
          const a = getVoxel(vox, x[0], x[1], x[2], dims[0], dims[1], dims[2]);
          const b = getVoxel(vox, x[0] + q[0], x[1] + q[1], x[2] + q[2], dims[0], dims[1], dims[2]);
          if (a === b) {
            mask[n++] = null;
          } else if (a && (!b || a !== b)) {
            mask[n++] = {
              blockKey: a,
              dir: 1,
              transparent: blockIsTransparent(a)
            };
          } else if (b) {
            mask[n++] = {
              blockKey: b,
              dir: -1,
              transparent: blockIsTransparent(b)
            };
          } else {
            mask[n++] = null;
          }
        }
      }

      n = 0;
      for (let j = 0; j < dims[v]; j++) {
        for (let i = 0; i < dims[u]; i++) {
          const cell = mask[n];
          if (!cell) {
            n++;
            continue;
          }

          let w = 1;
          while (i + w < dims[u] && cellEquals(mask[n + w], cell)) {
            w++;
          }

          let h = 1;
          outer: for (; j + h < dims[v]; h++) {
            for (let k = 0; k < w; k++) {
              if (!cellEquals(mask[n + k + h * dims[u]], cell)) {
                break outer;
              }
            }
          }

          const origin = [0, 0, 0] as [number, number, number];
          origin[u] = i;
          origin[v] = j;
          origin[d] = cell.dir === 1 ? x[d] + 1 : x[d];

          quads.push({
            axis: d,
            dir: cell.dir,
            x: origin[0],
            y: origin[1],
            z: origin[2],
            w,
            h,
            blockKey: cell.blockKey,
            transparent: cell.transparent
          });

          for (let l = 0; l < h; l++) {
            for (let k = 0; k < w; k++) {
              mask[n + k + l * dims[u]] = null;
            }
          }

          i += w - 1;
          n += w;
        }
      }
    }
  }

  quads.sort((a, b) => {
    if (a.axis !== b.axis) return a.axis - b.axis;
    if (a.dir !== b.dir) return a.dir - b.dir;
    if (a.z !== b.z) return a.z - b.z;
    if (a.y !== b.y) return a.y - b.y;
    if (a.x !== b.x) return a.x - b.x;
    return a.blockKey.localeCompare(b.blockKey);
  });

  return quads;
}

interface Face2D {
  p: [Vector3, Vector3, Vector3, Vector3];
  depth: number;
  color: { r: number; g: number; b: number };
  transparent: boolean;
}

function quadToVertices(q: GreedyQuad): [Vector3, Vector3, Vector3, Vector3] {
  const p = [q.x, q.y, q.z];
  const u = [0, 0, 0];
  const v = [0, 0, 0];
  const axisU = ((q.axis + 1) % 3) as 0 | 1 | 2;
  const axisV = ((q.axis + 2) % 3) as 0 | 1 | 2;
  u[axisU] = q.w;
  v[axisV] = q.h;

  const a = new Vector3(p[0], p[1], p[2]);
  const b = new Vector3(p[0] + u[0], p[1] + u[1], p[2] + u[2]);
  const c = new Vector3(p[0] + u[0] + v[0], p[1] + u[1] + v[1], p[2] + u[2] + v[2]);
  const d = new Vector3(p[0] + v[0], p[1] + v[1], p[2] + v[2]);

  if (q.dir === 1) return [a, b, c, d];
  return [a, d, c, b];
}

function drawTriangle(
  pixels: Uint8Array,
  width: number,
  height: number,
  p0: Vector3,
  p1: Vector3,
  p2: Vector3,
  color: { r: number; g: number; b: number },
  alpha = 255
): void {
  const minX = Math.max(0, Math.floor(Math.min(p0.x, p1.x, p2.x)));
  const maxX = Math.min(width - 1, Math.ceil(Math.max(p0.x, p1.x, p2.x)));
  const minY = Math.max(0, Math.floor(Math.min(p0.y, p1.y, p2.y)));
  const maxY = Math.min(height - 1, Math.ceil(Math.max(p0.y, p1.y, p2.y)));

  const edge = (ax: number, ay: number, bx: number, by: number, cx: number, cy: number): number =>
    (cx - ax) * (by - ay) - (cy - ay) * (bx - ax);

  const area = edge(p0.x, p0.y, p1.x, p1.y, p2.x, p2.y);
  if (area === 0) return;

  for (let y = minY; y <= maxY; y++) {
    for (let x = minX; x <= maxX; x++) {
      const px = x + 0.5;
      const py = y + 0.5;
      const w0 = edge(p1.x, p1.y, p2.x, p2.y, px, py);
      const w1 = edge(p2.x, p2.y, p0.x, p0.y, px, py);
      const w2 = edge(p0.x, p0.y, p1.x, p1.y, px, py);
      const inside = area > 0 ? w0 >= 0 && w1 >= 0 && w2 >= 0 : w0 <= 0 && w1 <= 0 && w2 <= 0;
      if (!inside) continue;
      const idx = (y * width + x) * 4;
      pixels[idx] = color.r;
      pixels[idx + 1] = color.g;
      pixels[idx + 2] = color.b;
      pixels[idx + 3] = alpha;
    }
  }
}

function toScreen(v: Vector3, width: number, height: number): Vector3 {
  return new Vector3(
    (v.x * 0.5 + 0.5) * (width - 1),
    (1 - (v.y * 0.5 + 0.5)) * (height - 1),
    v.z
  );
}

function applyBrightness(color: { r: number; g: number; b: number }, factor: number): { r: number; g: number; b: number } {
  return {
    r: Math.max(0, Math.min(255, Math.round(color.r * factor))),
    g: Math.max(0, Math.min(255, Math.round(color.g * factor))),
    b: Math.max(0, Math.min(255, Math.round(color.b * factor)))
  };
}

export function renderThumbnailPng(canonical: CanonicalObject, options: ThumbnailOptions = {}): Buffer {
  const width = options.width ?? 256;
  const height = options.height ?? 256;
  const bg = options.background ?? { r: 238, g: 241, b: 246, a: 255 };

  const pixels = new Uint8Array(width * height * 4);
  for (let i = 0; i < width * height; i++) {
    const idx = i * 4;
    pixels[idx] = bg.r;
    pixels[idx + 1] = bg.g;
    pixels[idx + 2] = bg.b;
    pixels[idx + 3] = bg.a ?? 255;
  }

  const quads = greedyMesh(canonical);
  if (quads.length === 0) {
    const png = new PNG({ width, height });
    png.data = Buffer.from(pixels);
    return PNG.sync.write(png);
  }

  const dims = canonical.boundsNormalized;
  const center = new Vector3(dims.dx / 2, dims.dy / 2, dims.dz / 2);
  const maxDim = Math.max(dims.dx, dims.dy, dims.dz);
  const yaw = ((options.yawDeg ?? 45) * Math.PI) / 180;
  const pitch = ((options.pitchDeg ?? 35.26438968) * Math.PI) / 180;
  const fov = options.fovDeg ?? 35;
  const radius = maxDim * 2.8 + 6;

  const camera = new PerspectiveCamera(fov, width / height, 0.1, 10000);
  const dir = new Vector3(
    Math.cos(pitch) * Math.cos(yaw),
    Math.sin(pitch),
    Math.cos(pitch) * Math.sin(yaw)
  ).normalize();
  camera.position.copy(center.clone().addScaledVector(dir, radius));
  camera.up.set(0, 1, 0);
  camera.lookAt(center);
  camera.updateMatrixWorld(true);
  camera.updateProjectionMatrix();

  const worldToCamera = new Matrix4().copy(camera.matrixWorldInverse);
  const faces: Face2D[] = [];
  for (const quad of quads) {
    const worldVerts = quadToVertices(quad);
    const projected = worldVerts.map((v) => v.clone().project(camera));
    const depth = worldVerts.reduce((sum, p) => sum + p.clone().applyMatrix4(worldToCamera).z, 0) / 4;
    const base = blockColor(quad.blockKey);
    let light = 1;
    if (quad.axis === 1) light = 1.12; // top brighter
    if (quad.axis === 0) light = 0.92;
    if (quad.axis === 2) light = 0.82;
    faces.push({
      p: [
        toScreen(projected[0]!, width, height),
        toScreen(projected[1]!, width, height),
        toScreen(projected[2]!, width, height),
        toScreen(projected[3]!, width, height)
      ],
      depth,
      color: applyBrightness(base, light),
      transparent: quad.transparent
    });
  }

  faces.sort((a, b) => a.depth - b.depth);
  for (const face of faces) {
    drawTriangle(pixels, width, height, face.p[0], face.p[1], face.p[2], face.color, face.transparent ? 180 : 255);
    drawTriangle(pixels, width, height, face.p[0], face.p[2], face.p[3], face.color, face.transparent ? 180 : 255);
  }

  const png = new PNG({ width, height });
  png.data = Buffer.from(pixels);
  return PNG.sync.write(png);
}

export function renderErrorThumbnailPng(
  errorCode: string,
  options: Pick<ThumbnailOptions, "width" | "height"> = {}
): Buffer {
  const width = options.width ?? 256;
  const height = options.height ?? 256;
  const pixels = new Uint8Array(width * height * 4);

  for (let i = 0; i < width * height; i++) {
    const idx = i * 4;
    pixels[idx] = 120;
    pixels[idx + 1] = 16;
    pixels[idx + 2] = 24;
    pixels[idx + 3] = 255;
  }

  const margin = Math.floor(width * 0.2);
  for (let i = margin; i < width - margin; i++) {
    const y1 = Math.floor((i - margin) * (height - 2 * margin) / (width - 2 * margin)) + margin;
    const y2 = height - y1 - 1;
    const idx1 = (y1 * width + i) * 4;
    const idx2 = (y2 * width + i) * 4;
    pixels[idx1] = 255;
    pixels[idx1 + 1] = 255;
    pixels[idx1 + 2] = 255;
    pixels[idx1 + 3] = 255;
    pixels[idx2] = 255;
    pixels[idx2 + 1] = 255;
    pixels[idx2 + 2] = 255;
    pixels[idx2 + 3] = 255;
  }

  const hash = stableHash32(errorCode);
  const stripeY = Math.floor(height * 0.86);
  for (let x = 0; x < width; x++) {
    const idx = (stripeY * width + x) * 4;
    pixels[idx] = (hash >>> 16) & 0xff;
    pixels[idx + 1] = (hash >>> 8) & 0xff;
    pixels[idx + 2] = hash & 0xff;
    pixels[idx + 3] = 255;
  }

  const png = new PNG({ width, height });
  png.data = Buffer.from(pixels);
  return PNG.sync.write(png);
}

export function meshCacheKey(canonicalSha256: string, rendererVersion: string, blockProfile: string): string {
  return createHash("sha256")
    .update(`mesh|${canonicalSha256}|${rendererVersion}|${blockProfile}`)
    .digest("hex");
}

export function thumbCacheKey(meshKey: string, thumbConfig: string, rendererVersion: string): string {
  return createHash("sha256")
    .update(`thumb|${meshKey}|${thumbConfig}|${rendererVersion}`)
    .digest("hex");
}
