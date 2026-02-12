import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

interface Quad {
  axis: 0 | 1 | 2;
  dir: 1 | -1;
  x: number;
  y: number;
  z: number;
  w: number;
  h: number;
  blockKey: string;
}

interface MeshData {
  quads: Quad[];
}

interface Props {
  meshData: MeshData | null;
}

function colorForBlock(blockKey: string): THREE.Color {
  let h = 0x811c9dc5;
  for (let i = 0; i < blockKey.length; i++) {
    h ^= blockKey.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  const r = 0.2 + (((h >>> 16) & 0x7f) / 255);
  const g = 0.2 + (((h >>> 8) & 0x7f) / 255);
  const b = 0.2 + ((h & 0x7f) / 255);
  return new THREE.Color(r, g, b);
}

function quadVertices(q: Quad): [THREE.Vector3, THREE.Vector3, THREE.Vector3, THREE.Vector3] {
  const p = [q.x, q.y, q.z];
  const u = [0, 0, 0];
  const v = [0, 0, 0];
  const axisU = ((q.axis + 1) % 3) as 0 | 1 | 2;
  const axisV = ((q.axis + 2) % 3) as 0 | 1 | 2;
  u[axisU] = q.w;
  v[axisV] = q.h;
  const a = new THREE.Vector3(p[0], p[1], p[2]);
  const b = new THREE.Vector3(p[0] + u[0], p[1] + u[1], p[2] + u[2]);
  const c = new THREE.Vector3(p[0] + u[0] + v[0], p[1] + u[1] + v[1], p[2] + u[2] + v[2]);
  const d = new THREE.Vector3(p[0] + v[0], p[1] + v[1], p[2] + v[2]);
  if (q.dir === 1) return [a, b, c, d];
  return [a, d, c, b];
}

function buildGeometry(meshData: MeshData): THREE.BufferGeometry {
  const positions: number[] = [];
  const colors: number[] = [];
  for (const q of meshData.quads) {
    const [a, b, c, d] = quadVertices(q);
    const color = colorForBlock(q.blockKey);
    const triangles = [
      [a, b, c],
      [a, c, d]
    ];
    for (const tri of triangles) {
      for (const p of tri) {
        positions.push(p.x, p.y, p.z);
        colors.push(color.r, color.g, color.b);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.computeVertexNormals();
  return geometry;
}

export function VoxelViewport({ meshData }: Props): JSX.Element {
  const hostRef = useRef<HTMLDivElement>(null);
  const geometry = useMemo(() => (meshData ? buildGeometry(meshData) : null), [meshData]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const width = Math.max(100, host.clientWidth);
    const height = Math.max(100, host.clientHeight);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xe8eef6);

    const camera = new THREE.PerspectiveCamera(65, width / height, 0.1, 5000);
    camera.position.set(30, 20, 30);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    host.innerHTML = "";
    host.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.45));
    const light = new THREE.DirectionalLight(0xffffff, 0.85);
    light.position.set(60, 90, 30);
    scene.add(light);

    let mesh: THREE.Mesh | null = null;
    if (geometry) {
      const material = new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide });
      mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);
    }

    const keys = new Set<string>();
    let dragging = false;
    const yawPitch = { yaw: -0.8, pitch: -0.35 };
    const target = new THREE.Vector3(0, 0, 0);

    const onKeyDown = (e: KeyboardEvent) => keys.add(e.code);
    const onKeyUp = (e: KeyboardEvent) => keys.delete(e.code);
    const onMouseDown = () => (dragging = true);
    const onMouseUp = () => (dragging = false);
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging) return;
      yawPitch.yaw -= e.movementX * 0.003;
      yawPitch.pitch = Math.max(-1.4, Math.min(1.4, yawPitch.pitch - e.movementY * 0.003));
    };
    const onResize = () => {
      const w = Math.max(100, host.clientWidth);
      const h = Math.max(100, host.clientHeight);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    renderer.domElement.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mouseup", onMouseUp);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("resize", onResize);

    let running = true;
    const clock = new THREE.Clock();

    const tick = () => {
      if (!running) return;
      const dt = Math.min(0.05, clock.getDelta());
      const speed = keys.has("ShiftLeft") ? 30 : 12;
      const forward = new THREE.Vector3(
        Math.cos(yawPitch.pitch) * Math.cos(yawPitch.yaw),
        Math.sin(yawPitch.pitch),
        Math.cos(yawPitch.pitch) * Math.sin(yawPitch.yaw)
      ).normalize();
      const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();
      const up = new THREE.Vector3(0, 1, 0);

      if (keys.has("KeyW")) camera.position.addScaledVector(forward, speed * dt);
      if (keys.has("KeyS")) camera.position.addScaledVector(forward, -speed * dt);
      if (keys.has("KeyA")) camera.position.addScaledVector(right, -speed * dt);
      if (keys.has("KeyD")) camera.position.addScaledVector(right, speed * dt);
      if (keys.has("KeyQ")) camera.position.addScaledVector(up, speed * dt);
      if (keys.has("KeyE")) camera.position.addScaledVector(up, -speed * dt);

      target.copy(camera.position).add(forward);
      camera.lookAt(target);
      renderer.render(scene, camera);
      requestAnimationFrame(tick);
    };
    tick();

    return () => {
      running = false;
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("mouseup", onMouseUp);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("resize", onResize);
      renderer.domElement.removeEventListener("mousedown", onMouseDown);
      if (mesh) {
        (mesh.material as THREE.Material).dispose();
      }
      geometry?.dispose();
      renderer.dispose();
      host.innerHTML = "";
    };
  }, [geometry]);

  return <div className="viewport-host" ref={hostRef} />;
}

