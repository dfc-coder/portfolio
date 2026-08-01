<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import type * as ThreeNamespace from "three";

const canvas = ref<HTMLCanvasElement | null>(null);
let renderer: ThreeNamespace.WebGLRenderer | null = null;
let frame = 0;
let cleanup: (() => void) | null = null;
let disposed = false;

onMounted(async () => {
  const THREE = await import("three");
  if (disposed) return;
  if (!canvas.value) return;

  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, innerWidth / innerHeight, 0.1, 100);
  camera.position.set(0, 0, 8.4);

  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas.value, alpha: true, antialias: true, powerPreference: "high-performance" });
  } catch {
    canvas.value.style.display = "none";
    canvas.value.parentElement?.classList.add("webgl-fallback");
    return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.65));
  renderer.setSize(innerWidth, innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const vertex = /* glsl */ `
    uniform float uTime;
    uniform float uScroll;
    uniform vec2 uPointer;
    varying vec3 vNormal;
    varying vec3 vWorld;
    varying float vWave;

    void main() {
      vec3 p = position;
      float waveA = sin(p.y * 3.6 + uTime * .52 + p.x * 1.2);
      float waveB = sin(p.z * 5.2 - uTime * .34 + p.y * 2.1);
      float waveC = cos((p.x + p.z) * 4.1 + uScroll * 5.0);
      float wave = waveA * .48 + waveB * .3 + waveC * .22;
      float pointerPull = max(0.0, 1.0 - distance(p.xy * .33, uPointer * .5));
      p += normal * (wave * .16 + pointerPull * .08);
      p.x += sin(p.y * 2.0 + uTime * .18) * .055;
      vWave = wave;
      vNormal = normalize(normalMatrix * normal);
      vec4 world = modelMatrix * vec4(p, 1.0);
      vWorld = world.xyz;
      gl_Position = projectionMatrix * viewMatrix * world;
    }
  `;

  const fragment = /* glsl */ `
    uniform float uTime;
    uniform float uScroll;
    varying vec3 vNormal;
    varying vec3 vWorld;
    varying float vWave;

    void main() {
      vec3 viewDir = normalize(cameraPosition - vWorld);
      float fresnel = pow(1.0 - abs(dot(viewDir, normalize(vNormal))), 2.6);
      float bands = sin(vWorld.y * 4.8 + vWorld.x * 1.6 - uTime * .22) * .5 + .5;
      vec3 obsidian = vec3(.035, .04, .045);
      vec3 mineral = vec3(.42, .49, .52);
      vec3 spectral = vec3(.92, .95, .94);
      vec3 ember = vec3(.94, .19, .055);
      vec3 color = mix(obsidian, mineral, smoothstep(-.65, .82, vWave));
      color = mix(color, spectral, fresnel * (.55 + bands * .3));
      color = mix(color, ember, smoothstep(.82, 1.0, fresnel + sin(uScroll * 3.1415) * .08) * .35);
      float alpha = .78 + fresnel * .21;
      gl_FragColor = vec4(color, alpha);
    }
  `;

  const uniforms = {
    uTime: { value: 0 },
    uScroll: { value: 0 },
    uPointer: { value: new THREE.Vector2() },
  };
  const geometry = new THREE.IcosahedronGeometry(1.72, 12);
  const material = new THREE.ShaderMaterial({ vertexShader: vertex, fragmentShader: fragment, uniforms, transparent: true });
  const matter = new THREE.Mesh(geometry, material);
  matter.rotation.set(-0.22, 0.25, -0.08);
  scene.add(matter);

  const wire = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.78, 4),
    new THREE.MeshBasicMaterial({ color: 0x173bdb, wireframe: true, transparent: true, opacity: 0.085 }),
  );
  scene.add(wire);

  const ringGroup = new THREE.Group();
  [2.35, 2.72, 3.08].forEach((radius, index) => {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, 0.006 + index * 0.002, 8, 180),
      new THREE.MeshBasicMaterial({ color: index === 1 ? 0xf04418 : 0x173bdb, transparent: true, opacity: index === 1 ? 0.3 : 0.18 }),
    );
    ring.rotation.set(Math.PI * (0.32 + index * 0.13), Math.PI * (0.08 + index * 0.18), index * 0.32);
    ringGroup.add(ring);
  });
  scene.add(ringGroup);

  const particleGeometry = new THREE.BufferGeometry();
  const points = new Float32Array(760 * 3);
  for (let i = 0; i < 760; i += 1) {
    const radius = 2.4 + Math.random() * 3.2;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    points[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
    points[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
    points[i * 3 + 2] = radius * Math.cos(phi);
  }
  particleGeometry.setAttribute("position", new THREE.BufferAttribute(points, 3));
  const particles = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({ color: 0x11110f, size: 0.011, transparent: true, opacity: 0.24, depthWrite: false }),
  );
  scene.add(particles);

  const pointer = new THREE.Vector2();
  const targetPointer = new THREE.Vector2();
  let scroll = scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight);
  let targetScroll = scroll;
  const clock = new THREE.Clock();

  const onPointer = (event: PointerEvent) => {
    targetPointer.set((event.clientX / innerWidth) * 2 - 1, -(event.clientY / innerHeight) * 2 + 1);
  };
  const onScroll = () => {
    targetScroll = scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight);
  };
  const onResize = () => {
    if (!renderer) return;
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.65));
    renderer.setSize(innerWidth, innerHeight);
  };

  addEventListener("pointermove", onPointer, { passive: true });
  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", onResize);

  const draw = () => {
    const time = clock.getElapsedTime();
    pointer.lerp(targetPointer, reduced ? 1 : 0.035);
    scroll += (targetScroll - scroll) * 0.045;
    uniforms.uTime.value = reduced ? 1.6 : time;
    uniforms.uScroll.value = scroll;
    uniforms.uPointer.value.copy(pointer);
    matter.rotation.y += reduced ? 0 : 0.00135;
    matter.rotation.x = -0.2 + pointer.y * 0.09 + scroll * 0.42;
    matter.position.x = .7 + pointer.x * 0.14 + Math.sin(scroll * Math.PI * 3) * 0.42;
    matter.position.y = pointer.y * 0.11 - scroll * 0.28;
    matter.scale.setScalar(1 + Math.sin(scroll * Math.PI * 2.4) * 0.08);
    wire.rotation.copy(matter.rotation);
    wire.rotation.z -= time * 0.014;
    wire.position.copy(matter.position);
    ringGroup.rotation.y = time * 0.025 + scroll * 1.8;
    ringGroup.rotation.z = -time * 0.013 + pointer.x * 0.08;
    particles.rotation.y = -time * 0.007 + scroll * 0.65;
    particles.rotation.x = pointer.y * 0.06;
    camera.position.x += (pointer.x * 0.16 - camera.position.x) * 0.025;
    camera.position.y += (pointer.y * 0.1 - camera.position.y) * 0.025;
    camera.lookAt(0, 0, 0);
    renderer?.render(scene, camera);
    frame = requestAnimationFrame(draw);
  };
  draw();

  cleanup = () => {
    cancelAnimationFrame(frame);
    removeEventListener("pointermove", onPointer);
    removeEventListener("scroll", onScroll);
    removeEventListener("resize", onResize);
    geometry.dispose();
    material.dispose();
    particleGeometry.dispose();
    (particles.material as ThreeNamespace.Material).dispose();
    wire.geometry.dispose();
    (wire.material as ThreeNamespace.Material).dispose();
    ringGroup.children.forEach((child) => {
      if (child instanceof THREE.Mesh) {
        child.geometry.dispose();
        (child.material as ThreeNamespace.Material).dispose();
      }
    });
    renderer?.dispose();
  };
});

onBeforeUnmount(() => {
  disposed = true;
  cleanup?.();
});
</script>

<template>
  <div class="matter-world" aria-hidden="true">
    <canvas ref="canvas" />
    <div class="matter-halo" />
  </div>
</template>
