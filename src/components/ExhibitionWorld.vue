<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import * as THREE from "three";
import { exhibits, narrativeBeats } from "../data/exhibition";
import type { Exhibit } from "../data/exhibition";

const canvas = ref<HTMLCanvasElement | null>(null);
const track = ref<HTMLElement | null>(null);
const ready = ref(false);
const webglAvailable = ref(true);
const activeBeatIndex = ref(0);
const progress = ref(0);
const hoveredIndex = ref<number | null>(null);
const selectedIndex = ref<number | null>(null);
const indexOpen = ref(false);

const activeBeat = computed(() => narrativeBeats[activeBeatIndex.value]);
const hoveredExhibit = computed(() =>
  hoveredIndex.value === null ? null : exhibits[hoveredIndex.value],
);
const selectedExhibit = computed(() =>
  selectedIndex.value === null ? null : exhibits[selectedIndex.value],
);
const progressLabel = computed(() => String(Math.round(progress.value * 100)).padStart(2, "0"));

let cleanupWorld: (() => void) | null = null;

const openExhibit = (index: number) => {
  selectedIndex.value = index;
  indexOpen.value = false;
  document.body.classList.add("dialog-open");
};

const closeExhibit = () => {
  selectedIndex.value = null;
  document.body.classList.remove("dialog-open");
};

const showPrevious = () => {
  if (selectedIndex.value === null) return;
  selectedIndex.value = (selectedIndex.value - 1 + exhibits.length) % exhibits.length;
};

const showNext = () => {
  if (selectedIndex.value === null) return;
  selectedIndex.value = (selectedIndex.value + 1) % exhibits.length;
};

const setBeatFromProgress = (value: number) => {
  let next = 0;
  narrativeBeats.forEach((beat, index) => {
    if (value >= beat.from) next = index;
  });
  if (next !== activeBeatIndex.value) activeBeatIndex.value = next;
};

const wrapText = (
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
  maxLines: number,
) => {
  const words = text.split(" ");
  let line = "";
  let lineIndex = 0;

  for (let index = 0; index < words.length; index += 1) {
    const test = `${line}${words[index]} `;
    if (context.measureText(test).width > maxWidth && line.length > 0) {
      context.fillText(line.trim(), x, y + lineIndex * lineHeight);
      line = `${words[index]} `;
      lineIndex += 1;
      if (lineIndex >= maxLines - 1) break;
    } else {
      line = test;
    }
  }

  if (lineIndex < maxLines) context.fillText(line.trim(), x, y + lineIndex * lineHeight);
};

const createSystemTexture = (exhibit: Exhibit) => {
  const surface = document.createElement("canvas");
  surface.width = 1600;
  surface.height = 1000;
  const context = surface.getContext("2d");
  if (!context) return null;

  context.fillStyle = "#d8d3ca";
  context.fillRect(0, 0, surface.width, surface.height);
  context.strokeStyle = "rgba(24, 23, 21, .18)";
  context.lineWidth = 1;

  for (let x = 0; x <= surface.width; x += 80) {
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, surface.height);
    context.stroke();
  }
  for (let y = 0; y <= surface.height; y += 80) {
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(surface.width, y);
    context.stroke();
  }

  context.strokeStyle = "#171614";
  context.lineWidth = 3;
  context.strokeRect(40, 40, surface.width - 80, surface.height - 80);

  context.fillStyle = "#171614";
  context.font = "500 34px Arial, sans-serif";
  context.fillText(`${exhibit.id} / ${exhibit.discipline.toUpperCase()}`, 82, 112);

  context.font = "700 112px Arial, sans-serif";
  wrapText(context, exhibit.title.toUpperCase(), 78, 255, 1060, 108, 3);

  context.font = "400 31px Arial, sans-serif";
  wrapText(context, exhibit.summary, 82, 610, 770, 43, 4);

  const nodes = exhibit.technologies.slice(0, 5);
  const nodeY = 840;
  const startX = 84;
  const gap = 280;
  nodes.forEach((node, index) => {
    const x = startX + index * gap;
    context.fillStyle = index === 0 ? "#171614" : "#f1eee8";
    context.strokeStyle = "#171614";
    context.lineWidth = 2;
    context.fillRect(x, nodeY, 220, 66);
    context.strokeRect(x, nodeY, 220, 66);
    context.fillStyle = index === 0 ? "#f1eee8" : "#171614";
    context.font = "500 21px Arial, sans-serif";
    context.fillText(node.toUpperCase().slice(0, 18), x + 17, nodeY + 41);
    if (index < nodes.length - 1) {
      context.strokeStyle = "#171614";
      context.beginPath();
      context.moveTo(x + 220, nodeY + 33);
      context.lineTo(x + gap, nodeY + 33);
      context.stroke();
    }
  });

  const texture = new THREE.CanvasTexture(surface);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  texture.needsUpdate = true;
  return texture;
};

const createWordTexture = (word: string) => {
  const surface = document.createElement("canvas");
  surface.width = 2048;
  surface.height = 512;
  const context = surface.getContext("2d");
  if (!context) return null;
  context.clearRect(0, 0, surface.width, surface.height);
  context.fillStyle = "#ede9e0";
  context.font = "700 360px Arial, sans-serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(word, surface.width / 2, surface.height / 2 + 18);
  const texture = new THREE.CanvasTexture(surface);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;
  return texture;
};

onMounted(async () => {
  await nextTick();
  if (!canvas.value || !track.value) return;

  gsap.registerPlugin(ScrollTrigger);
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x11100e);
  scene.fog = new THREE.Fog(0x11100e, 10, 34);

  const camera = new THREE.PerspectiveCamera(43, innerWidth / innerHeight, 0.08, 140);
  camera.position.set(0, 1.7, 7);

  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas: canvas.value,
      antialias: innerWidth > 720,
      alpha: false,
      powerPreference: "high-performance",
    });
  } catch {
    webglAvailable.value = false;
    ready.value = true;
    return;
  }

  renderer.setPixelRatio(Math.min(devicePixelRatio, innerWidth < 720 ? 1.15 : 1.55));
  renderer.setSize(innerWidth, innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;

  const root = new THREE.Group();
  scene.add(root);

  const architecturalMaterial = new THREE.MeshStandardMaterial({
    color: 0x393630,
    roughness: 0.9,
    metalness: 0.04,
  });
  const floorMaterial = new THREE.MeshStandardMaterial({
    color: 0x1b1a18,
    roughness: 0.48,
    metalness: 0.18,
  });
  const frameMaterial = new THREE.MeshStandardMaterial({
    color: 0x161513,
    roughness: 0.52,
    metalness: 0.12,
  });
  const paleMaterial = new THREE.MeshStandardMaterial({
    color: 0xbcb6aa,
    roughness: 0.82,
    metalness: 0.03,
  });

  const floor = new THREE.Mesh(new THREE.BoxGeometry(10.4, 0.12, 112), floorMaterial);
  floor.position.set(0, -0.08, -45);
  root.add(floor);

  const leftWall = new THREE.Mesh(new THREE.BoxGeometry(0.25, 5.9, 112), architecturalMaterial);
  leftWall.position.set(-5.12, 2.82, -45);
  root.add(leftWall);
  const rightWall = leftWall.clone();
  rightWall.position.x = 5.12;
  root.add(rightWall);

  const ceiling = new THREE.Mesh(new THREE.BoxGeometry(10.4, 0.18, 112), architecturalMaterial);
  ceiling.position.set(0, 5.72, -45);
  root.add(ceiling);

  const portalMaterial = new THREE.MeshStandardMaterial({
    color: 0x777168,
    roughness: 0.78,
    metalness: 0.12,
  });
  const columnGeometry = new THREE.BoxGeometry(0.18, 5.7, 0.22);
  const beamGeometry = new THREE.BoxGeometry(10.15, 0.18, 0.22);
  for (let index = 0; index < 20; index += 1) {
    const z = 4 - index * 5.1;
    const left = new THREE.Mesh(columnGeometry, portalMaterial);
    left.position.set(-4.86, 2.77, z);
    const right = left.clone();
    right.position.x = 4.86;
    const top = new THREE.Mesh(beamGeometry, portalMaterial);
    top.position.set(0, 5.48, z);
    root.add(left, right, top);
  }

  const ambient = new THREE.HemisphereLight(0xe8e0d2, 0x161410, 1.35);
  scene.add(ambient);
  const keyLight = new THREE.DirectionalLight(0xf6eee1, 2.7);
  keyLight.position.set(-4, 8, 8);
  scene.add(keyLight);

  const roomLights: THREE.PointLight[] = [];
  [-8, -30, -54, -78, -94].forEach((z, index) => {
    const light = new THREE.PointLight(index % 2 === 0 ? 0xe3d6c5 : 0xc7b6a1, 9.5, 25, 2.2);
    light.position.set(index % 2 === 0 ? -2.2 : 2.2, 4.7, z);
    roomLights.push(light);
    scene.add(light);
  });

  const dustGeometry = new THREE.BufferGeometry();
  const dustCount = innerWidth < 720 ? 620 : 1100;
  const dustPositions = new Float32Array(dustCount * 3);
  for (let index = 0; index < dustCount; index += 1) {
    dustPositions[index * 3] = (Math.random() - 0.5) * 9.4;
    dustPositions[index * 3 + 1] = Math.random() * 5.3;
    dustPositions[index * 3 + 2] = 7 - Math.random() * 108;
  }
  dustGeometry.setAttribute("position", new THREE.BufferAttribute(dustPositions, 3));
  const dustMaterial = new THREE.PointsMaterial({
    color: 0xd6cfc1,
    size: 0.016,
    transparent: true,
    opacity: 0.22,
    depthWrite: false,
  });
  const dust = new THREE.Points(dustGeometry, dustMaterial);
  root.add(dust);

  type FrameState = {
    group: THREE.Group;
    mesh: THREE.Mesh;
    index: number;
    baseY: number;
    baseRotationZ: number;
    imageMaterial?: THREE.ShaderMaterial;
  };

  const frameStates: FrameState[] = [];
  const interactiveMeshes: THREE.Mesh[] = [];
  const loadedTextures: THREE.Texture[] = [];
  const textureLoader = new THREE.TextureLoader();

  const imageVertex = `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `;
  const imageFragment = `
    uniform sampler2D uMap;
    uniform float uHover;
    varying vec2 vUv;
    void main() {
      vec4 source = texture2D(uMap, vUv);
      float gray = dot(source.rgb, vec3(0.299, 0.587, 0.114));
      vec3 warm = vec3(gray * 1.03, gray, gray * .94);
      warm = mix(warm, vec3(.93, .89, .82), uHover * .11);
      gl_FragColor = vec4(warm, source.a);
    }
  `;

  const placeholder = new THREE.DataTexture(
    new Uint8Array([176, 171, 161, 255]),
    1,
    1,
    THREE.RGBAFormat,
  );
  placeholder.colorSpace = THREE.SRGBColorSpace;
  placeholder.needsUpdate = true;
  loadedTextures.push(placeholder);

  exhibits.forEach((exhibit, index) => {
    const side = index % 2 === 0 ? -1 : 1;
    const baseY = 1.72 + ((index % 3) - 1) * 0.13;
    const z = -10.5 - index * 5.25;
    const group = new THREE.Group();
    group.position.set(side * 4.88, baseY, z);
    group.rotation.y = side < 0 ? Math.PI / 2 : -Math.PI / 2;
    group.rotation.z = ((index % 4) - 1.5) * 0.008;

    const surround = new THREE.Mesh(new THREE.BoxGeometry(3.26, 2.18, 0.14), frameMaterial);
    surround.position.z = -0.04;
    group.add(surround);

    const backing = new THREE.Mesh(new THREE.PlaneGeometry(3.02, 1.94), paleMaterial);
    backing.position.z = 0.035;
    group.add(backing);

    let imageMaterial: THREE.ShaderMaterial | undefined;
    let artworkMaterial: THREE.Material;

    if (exhibit.image) {
      imageMaterial = new THREE.ShaderMaterial({
        vertexShader: imageVertex,
        fragmentShader: imageFragment,
        uniforms: {
          uMap: { value: placeholder },
          uHover: { value: 0 },
        },
      });
      artworkMaterial = imageMaterial;
      textureLoader.load(
        exhibit.image,
        (texture) => {
          texture.colorSpace = THREE.SRGBColorSpace;
          texture.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);
          texture.wrapS = THREE.ClampToEdgeWrapping;
          texture.wrapT = THREE.ClampToEdgeWrapping;
          loadedTextures.push(texture);
          if (imageMaterial) imageMaterial.uniforms.uMap.value = texture;
        },
        undefined,
        () => undefined,
      );
    } else {
      const texture = createSystemTexture(exhibit);
      if (texture) loadedTextures.push(texture);
      artworkMaterial = new THREE.MeshBasicMaterial({ map: texture ?? null, color: 0xffffff });
    }

    const artwork = new THREE.Mesh(new THREE.PlaneGeometry(2.92, 1.84), artworkMaterial);
    artwork.position.z = 0.055;
    artwork.userData.exhibitIndex = index;
    artwork.userData.interactive = true;
    group.add(artwork);

    root.add(group);
    frameStates.push({
      group,
      mesh: artwork,
      index,
      baseY,
      baseRotationZ: group.rotation.z,
      imageMaterial,
    });
    interactiveMeshes.push(artwork);
  });

  const words = [
    { text: "SYSTEMS", x: 0.8, y: 3.35, z: -22, scale: 8.3, rotation: -0.04 },
    { text: "MATTER", x: -0.9, y: 2.9, z: -51, scale: 7.5, rotation: 0.035 },
    { text: "SIGNAL", x: 1.1, y: 3.3, z: -76, scale: 7.8, rotation: -0.02 },
  ];
  words.forEach((item) => {
    const texture = createWordTexture(item.text);
    if (!texture) return;
    loadedTextures.push(texture);
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      opacity: 0.13,
      depthWrite: false,
      blending: THREE.NormalBlending,
    });
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(item.scale, item.scale * 0.25), material);
    plane.position.set(item.x, item.y, item.z);
    plane.rotation.z = item.rotation;
    root.add(plane);
  });

  const workshop = new THREE.Group();
  workshop.position.set(0, 0, -89);
  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(1.75, 1.95, 0.32, 48), paleMaterial);
  plinth.position.y = 0.16;
  workshop.add(plinth);
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(1.08, 0.19, 18, 80, Math.PI * 1.55),
    new THREE.MeshStandardMaterial({ color: 0x23211e, roughness: 0.38, metalness: 0.55 }),
  );
  ring.position.y = 1.42;
  ring.rotation.set(Math.PI / 2.15, 0.18, -0.35);
  workshop.add(ring);
  const core = new THREE.Mesh(
    new THREE.CylinderGeometry(0.34, 0.34, 2.4, 32),
    new THREE.MeshStandardMaterial({ color: 0xa49c90, roughness: 0.7, metalness: 0.18 }),
  );
  core.position.y = 1.35;
  core.rotation.z = Math.PI / 2;
  workshop.add(core);
  root.add(workshop);

  const buildCameraPath = () => {
    const mobile = innerWidth < 720;
    const amplitude = mobile ? 0.78 : 1.55;
    return new THREE.CatmullRomCurve3(
      [
        new THREE.Vector3(0, 1.68, 7),
        new THREE.Vector3(0.15, 1.7, -2),
        new THREE.Vector3(amplitude, 1.74, -14),
        new THREE.Vector3(-amplitude * 0.82, 1.67, -29),
        new THREE.Vector3(amplitude * 0.95, 1.78, -44),
        new THREE.Vector3(-amplitude, 1.7, -61),
        new THREE.Vector3(amplitude * 0.7, 1.76, -77),
        new THREE.Vector3(0, 1.82, -92),
        new THREE.Vector3(0, 1.86, -99),
      ],
      false,
      "catmullrom",
      0.42,
    );
  };

  let cameraPath = buildCameraPath();
  const currentLook = new THREE.Vector3(0, 1.7, 0);
  const pointer = new THREE.Vector2(3, 3);
  const raycaster = new THREE.Raycaster();
  let targetProgress = 0;
  let currentProgress = 0;
  let hovered = -1;
  let animationFrame = 0;
  let disposed = false;
  const clock = new THREE.Clock();

  const focusAnchors = [
    { progress: 0.1, target: new THREE.Vector3(0, 2.2, -7), radius: 0.07 },
    { progress: 0.34, target: new THREE.Vector3(-3.8, 1.8, -31), radius: 0.045 },
    { progress: 0.57, target: new THREE.Vector3(3.8, 1.8, -54), radius: 0.05 },
    { progress: 0.78, target: new THREE.Vector3(-3.7, 1.8, -78), radius: 0.05 },
    { progress: 0.94, target: new THREE.Vector3(0, 1.4, -90), radius: 0.08 },
  ];

  const updatePointer = (event: PointerEvent) => {
    if (!canvas.value) return;
    const bounds = canvas.value.getBoundingClientRect();
    pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
    pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
  };

  const updateHover = () => {
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(interactiveMeshes, false);
    const next = hits.length > 0 ? Number(hits[0].object.userData.exhibitIndex) : -1;
    if (next === hovered) return;
    hovered = next;
    hoveredIndex.value = hovered >= 0 ? hovered : null;
    if (canvas.value) canvas.value.style.cursor = hovered >= 0 ? "pointer" : "default";
  };

  const selectFromPointer = () => {
    updateHover();
    if (hovered >= 0) openExhibit(hovered);
  };

  const handleKey = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      if (selectedIndex.value !== null) closeExhibit();
      else indexOpen.value = false;
    }
    if (selectedIndex.value !== null && event.key === "ArrowLeft") showPrevious();
    if (selectedIndex.value !== null && event.key === "ArrowRight") showNext();
  };

  const handleResize = () => {
    camera.aspect = innerWidth / innerHeight;
    camera.fov = innerWidth < 720 ? 52 : 43;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(devicePixelRatio, innerWidth < 720 ? 1.15 : 1.55));
    renderer.setSize(innerWidth, innerHeight);
    cameraPath = buildCameraPath();
    ScrollTrigger.refresh();
  };

  const scrollState = { value: 0 };
  const scrollTween = gsap.to(scrollState, {
    value: 1,
    ease: "none",
    onUpdate: () => {
      targetProgress = scrollState.value;
      progress.value = scrollState.value;
      setBeatFromProgress(scrollState.value);
    },
    scrollTrigger: {
      trigger: track.value,
      start: "top top",
      end: "bottom bottom",
      scrub: reducedMotion ? 0 : 1.15,
      invalidateOnRefresh: true,
    },
  });

  addEventListener("pointermove", updatePointer, { passive: true });
  addEventListener("keydown", handleKey);
  addEventListener("resize", handleResize);
  canvas.value.addEventListener("click", selectFromPointer);

  const draw = () => {
    if (disposed) return;
    const elapsed = clock.getElapsedTime();
    currentProgress += (targetProgress - currentProgress) * (reducedMotion ? 1 : 0.055);

    const position = cameraPath.getPointAt(Math.min(1, Math.max(0, currentProgress)));
    const tangent = cameraPath.getTangentAt(Math.min(0.999, currentProgress + 0.002)).normalize();
    const target = position.clone().add(tangent.multiplyScalar(7.5));
    target.y = 1.72;

    focusAnchors.forEach((anchor) => {
      const distance = Math.abs(currentProgress - anchor.progress);
      const weight = Math.max(0, 1 - distance / anchor.radius);
      const eased = weight * weight * (3 - 2 * weight);
      target.lerp(anchor.target, eased * 0.68);
    });

    camera.position.copy(position);
    currentLook.lerp(target, reducedMotion ? 1 : 0.075);
    camera.lookAt(currentLook);
    camera.rotation.z += Math.sin(currentProgress * Math.PI * 4) * 0.006;

    updateHover();

    frameStates.forEach((state) => {
      const isHovered = state.index === hovered;
      const lift = reducedMotion ? 0 : Math.sin(elapsed * 0.48 + state.index * 0.71) * 0.017;
      state.group.position.y = state.baseY + lift;
      state.group.rotation.z = state.baseRotationZ + (reducedMotion ? 0 : Math.sin(elapsed * 0.25 + state.index) * 0.0025);
      const targetScale = isHovered ? 1.035 : 1;
      const scale = THREE.MathUtils.lerp(state.group.scale.x, targetScale, 0.08);
      state.group.scale.setScalar(scale);
      if (state.imageMaterial) {
        state.imageMaterial.uniforms.uHover.value = THREE.MathUtils.lerp(
          Number(state.imageMaterial.uniforms.uHover.value),
          isHovered ? 1 : 0,
          0.08,
        );
      }
    });

    if (!reducedMotion) {
      dust.rotation.y = elapsed * 0.0025;
      workshop.rotation.y = Math.sin(elapsed * 0.24) * 0.055;
      roomLights.forEach((light, index) => {
        light.intensity = 9.1 + Math.sin(elapsed * 0.38 + index * 1.8) * 0.5;
      });
    }

    renderer.render(scene, camera);
    animationFrame = requestAnimationFrame(draw);
  };

  ready.value = true;
  requestAnimationFrame(() => ScrollTrigger.refresh());
  draw();

  cleanupWorld = () => {
    disposed = true;
    cancelAnimationFrame(animationFrame);
    scrollTween.kill();
    removeEventListener("pointermove", updatePointer);
    removeEventListener("keydown", handleKey);
    removeEventListener("resize", handleResize);
    canvas.value?.removeEventListener("click", selectFromPointer);
    scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh) && !(object instanceof THREE.Points)) return;
      object.geometry.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((material) => material.dispose());
    });
    loadedTextures.forEach((texture) => texture.dispose());
    renderer.dispose();
  };
});

onBeforeUnmount(() => {
  cleanupWorld?.();
  document.body.classList.remove("dialog-open");
});
</script>

<template>
  <div class="experience-shell">
    <a class="skip-link" href="#archive-index" @click="indexOpen = true">Skip the 3D route</a>

    <canvas ref="canvas" class="exhibition-canvas" aria-hidden="true" />
    <div class="cinematic-grain" aria-hidden="true" />
    <div class="cinematic-vignette" aria-hidden="true" />

    <div v-if="!ready" class="experience-loader" aria-live="polite">
      <span>DC / EXHIBITION</span>
      <i />
      <p>BUILDING THE SPACE</p>
    </div>

    <header class="museum-ui">
      <a class="museum-mark" href="#top" aria-label="Return to the exhibition entrance">
        <strong>DC</strong>
        <span>DIGITAL EXHIBITION<br />BUENOS AIRES · 2026</span>
      </a>
      <div class="route-progress" aria-label="Exhibition progress">
        <span>{{ progressLabel }}</span>
        <i><b :style="{ transform: `scaleX(${progress})` }" /></i>
        <span>100</span>
      </div>
      <button class="index-toggle" type="button" :aria-expanded="indexOpen" @click="indexOpen = !indexOpen">
        {{ indexOpen ? "CLOSE" : "INDEX" }}
      </button>
    </header>

    <Transition name="narrative" mode="out-in">
      <article :key="activeBeat.id" :class="['narrative-caption', `is-${activeBeat.position}`]">
        <span>{{ activeBeat.eyebrow }}</span>
        <h1 v-if="activeBeat.id === 'threshold'">
          <i v-for="line in activeBeat.title.split('\n')" :key="line">{{ line }}</i>
        </h1>
        <h2 v-else>
          <i v-for="line in activeBeat.title.split('\n')" :key="line">{{ line }}</i>
        </h2>
        <p>{{ activeBeat.body }}</p>
      </article>
    </Transition>

    <div v-if="hoveredExhibit" class="object-caption" aria-hidden="true">
      <span>{{ hoveredExhibit.id }} / {{ hoveredExhibit.discipline }}</span>
      <strong>{{ hoveredExhibit.title }}</strong>
      <small>OPEN EXHIBIT ↗</small>
    </div>

    <div v-if="progress < 0.08" class="scroll-instruction" aria-hidden="true">
      <span>SCROLL TO MOVE</span>
      <i />
    </div>

    <Transition name="contact-reveal">
      <nav v-if="activeBeat.id === 'exit'" class="contact-dock" aria-label="Contact links">
        <a href="mailto:diegocanomera@gmail.com">EMAIL ↗</a>
        <a href="https://github.com/dfc-coder" target="_blank" rel="noreferrer">GITHUB ↗</a>
        <a href="https://linkedin.com/in/software-engineer-diegocano" target="_blank" rel="noreferrer">LINKEDIN ↗</a>
      </nav>
    </Transition>

    <aside id="archive-index" :class="['archive-index', { 'is-open': indexOpen }]" aria-label="Exhibition index">
      <div class="archive-index-head">
        <span>ARCHIVE / {{ String(exhibits.length).padStart(2, "0") }} WORKS</span>
        <button type="button" @click="indexOpen = false">CLOSE ×</button>
      </div>
      <ol>
        <li v-for="(exhibit, index) in exhibits" :key="exhibit.id">
          <button type="button" @click="openExhibit(index)">
            <span>{{ exhibit.id }}</span>
            <strong>{{ exhibit.title }}</strong>
            <small>{{ exhibit.discipline }}</small>
            <i>↗</i>
          </button>
        </li>
      </ol>
    </aside>

    <main id="top" ref="track" class="exhibition-track">
      <div class="sr-only">
        <h1>Diego Cano — digital exhibition</h1>
        <p>
          An immersive portfolio spanning software engineering, artificial intelligence, electronics, IoT,
          industrial design, 3D printing and visual direction. Use the index to access every work without WebGL.
        </p>
      </div>
    </main>

    <div v-if="!webglAvailable" class="webgl-fallback" role="status">
      <span>3D RENDERING IS NOT AVAILABLE</span>
      <h2>The archive remains fully accessible.</h2>
      <button type="button" @click="indexOpen = true">OPEN THE INDEX</button>
    </div>

    <Teleport to="body">
      <Transition name="dossier">
        <div v-if="selectedExhibit" class="exhibit-dossier" role="dialog" aria-modal="true" :aria-label="selectedExhibit.title">
          <button class="dossier-backdrop" type="button" aria-label="Close exhibit" @click="closeExhibit" />
          <article>
            <header>
              <span>{{ selectedExhibit.id }} / {{ selectedExhibit.discipline }}</span>
              <button type="button" autofocus @click="closeExhibit">CLOSE ×</button>
            </header>
            <div class="dossier-media">
              <img v-if="selectedExhibit.image" :src="selectedExhibit.image" :alt="selectedExhibit.title" />
              <div v-else class="system-plate" aria-hidden="true">
                <span>{{ selectedExhibit.id }}</span>
                <i v-for="technology in selectedExhibit.technologies" :key="technology">{{ technology }}</i>
              </div>
            </div>
            <div class="dossier-copy">
              <span>{{ selectedExhibit.year }}</span>
              <h2>{{ selectedExhibit.title }}</h2>
              <p>{{ selectedExhibit.summary }}</p>
              <dl>
                <div>
                  <dt>ROLE</dt>
                  <dd>{{ selectedExhibit.role }}</dd>
                </div>
                <div>
                  <dt>LANGUAGE</dt>
                  <dd>
                    <span v-for="technology in selectedExhibit.technologies" :key="technology">{{ technology }}</span>
                  </dd>
                </div>
              </dl>
            </div>
            <footer>
              <button type="button" @click="showPrevious">← PREVIOUS</button>
              <span>{{ selectedExhibit.id }} — {{ String(exhibits.length).padStart(2, "0") }}</span>
              <button type="button" @click="showNext">NEXT →</button>
            </footer>
          </article>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
