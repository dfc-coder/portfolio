import * as THREE from "three";
import { narrativeRuntime, type NarrativeScene } from "../experiences/narrative-runtime";

export type AgentVisualPhase = "idle" | "listening" | "thinking" | "speaking" | "error";

interface AgentSignalState {
  phase: AgentVisualPhase;
  activity: number;
  activityTarget: number;
}

const agentSignal: AgentSignalState = {
  phase: "idle",
  activity: 0.14,
  activityTarget: 0.14,
};

let mountedGraphics: StageGraphics | null = null;

export const setAgentVisualPhase = (phase: AgentVisualPhase): void => {
  agentSignal.phase = phase;
  mountedGraphics?.wake();
};

export const pulseAgentVisual = (strength = 0.3): void => {
  const impulse = Math.min(1, Math.max(0, strength));
  agentSignal.activityTarget = Math.min(1, agentSignal.activityTarget + impulse);
  mountedGraphics?.wake();
};

export const setStageTransition = (
  progress: number,
  direction: number,
  active = true,
): void => {
  mountedGraphics?.setTransition(progress, direction, active);
};

const fullscreenVertex = /* glsl */ `
  varying vec2 vUv;

  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const atmosphereFragment = /* glsl */ `
  precision highp float;

  uniform vec2 uResolution;
  uniform vec2 uPointer;
  uniform float uTime;
  uniform float uVelocity;
  uniform float uIntensity;
  uniform float uTurbulence;
  varying vec2 vUv;

  float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);

    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));

    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
  }

  float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    mat2 rotate = mat2(0.80, -0.60, 0.60, 0.80);

    for (int i = 0; i < 4; i++) {
      value += noise(p) * amplitude;
      p = rotate * p * 2.02 + 7.13;
      amplitude *= 0.5;
    }

    return value;
  }

  void main() {
    vec2 uv = vUv;
    vec2 p = uv - 0.5;
    float aspect = uResolution.x / max(1.0, uResolution.y);
    p.x *= aspect;

    vec2 pointer = uPointer - 0.5;
    pointer.x *= aspect;

    float distanceToPointer = length(p - pointer);
    float slowTime = uTime * 0.018;
    float field = fbm(p * (1.95 + uTurbulence * 0.45) + vec2(slowTime, -slowTime * 0.82));
    float detail = fbm(p * (4.8 + uTurbulence * 1.2) - vec2(uTime * 0.010, uTime * 0.012));

    float impulse = sin(distanceToPointer * 24.0 - uTime * 1.35);
    impulse *= exp(-distanceToPointer * 5.6);
    impulse *= min(1.0, uVelocity * 1.8);

    float halo = exp(-distanceToPointer * 4.0) * (0.018 + uVelocity * 0.052);
    float tonal = 0.014 + field * 0.043 + detail * 0.012 + halo + impulse * 0.010;
    tonal *= uIntensity;

    vec3 ink = vec3(0.035, 0.034, 0.031);
    vec3 paper = vec3(0.92, 0.89, 0.83);
    vec3 warm = vec3(0.40, 0.32, 0.18);
    vec3 color = mix(ink, paper, clamp(tonal, 0.0, 0.14));
    color += warm * max(0.0, detail - 0.72) * 0.018 * uIntensity;

    float vignette = smoothstep(0.98, 0.24, length((uv - 0.5) * vec2(0.9, 1.1)));
    color *= mix(0.78, 1.0, vignette);

    gl_FragColor = vec4(color, 0.94);
  }
`;

const transitionFragment = /* glsl */ `
  precision highp float;

  uniform vec2 uResolution;
  uniform float uProgress;
  uniform float uDirection;
  uniform float uTime;
  varying vec2 vUv;

  float hash21(vec2 p) {
    p = fract(p * vec2(127.1, 311.7));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(hash21(i), hash21(i + vec2(1.0, 0.0)), u.x),
      mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), u.x),
      u.y
    );
  }

  float fbm3(vec2 p) {
    float value = 0.0;
    value += noise(p) * 0.56;
    p = mat2(0.80, -0.60, 0.60, 0.80) * p * 2.03 + vec2(9.7, 5.1);
    value += noise(p) * 0.28;
    p = mat2(0.80, -0.60, 0.60, 0.80) * p * 2.01 + vec2(4.3, 11.9);
    value += noise(p) * 0.16;
    return value;
  }

  void main() {
    vec2 uv = vUv;
    float aspect = uResolution.x / max(uResolution.y, 1.0);
    vec2 origin = vec2(0.5 + uDirection * 0.025, 0.5);
    vec2 p = (uv - origin) * vec2(aspect, 1.0);
    float radial = length(p);
    float angle = atan(p.y, p.x);
    float time = uTime * 0.045;

    float coarse = fbm3(p * 3.15 + vec2(time, -time * 0.72));
    float detail = fbm3(p * 8.4 - vec2(time * 1.23, time * 0.81));
    float lobes =
      sin(angle * 8.0 + coarse * 6.2) * 0.038 +
      sin(angle * 17.0 - detail * 7.0) * 0.018;

    float displacement =
      (coarse - 0.5) * 0.255 +
      (detail - 0.5) * 0.078 +
      lobes;

    float maximumRadius = length(vec2(aspect * 0.58, 0.62)) + 0.36;
    float burnRadius = mix(-0.17, maximumRadius, clamp(uProgress, 0.0, 1.0));
    float sd = radial - burnRadius - displacement;
    float edgeWidth = mix(0.052, 0.030, uProgress);
    float material = 1.0 - smoothstep(-edgeWidth, edgeWidth, sd);

    float edgeDistance = abs(sd);
    float charBand = 1.0 - smoothstep(0.022, 0.105, edgeDistance);
    float emberBand = 1.0 - smoothstep(0.0, 0.021, edgeDistance);
    float hotLine = 1.0 - smoothstep(0.0, 0.007, edgeDistance);

    float fleckNoise = noise(
      p * 34.0 + vec2(uTime * 0.13, -uTime * 0.09) + coarse * 4.0
    );
    float fleckZone =
      (1.0 - smoothstep(0.035, 0.155, edgeDistance)) *
      smoothstep(0.60, 0.88, fleckNoise);

    vec3 soot = vec3(0.014, 0.013, 0.012);
    vec3 charBrown = vec3(0.105, 0.048, 0.018);
    vec3 ember = vec3(0.79, 0.225, 0.045);
    vec3 hotPaper = vec3(0.92, 0.61, 0.30);

    vec3 color = soot;
    color = mix(color, charBrown, charBand * 0.88);
    color = mix(color, ember, emberBand * (0.70 + detail * 0.24));
    color = mix(color, hotPaper, hotLine * 0.42);
    color = mix(color, ember, fleckZone * 0.44);

    float alpha = max(material, charBand * 0.88);
    alpha = max(alpha, fleckZone * 0.62);
    gl_FragColor = vec4(color, clamp(alpha, 0.0, 1.0));
  }
`;

const agentVertex = /* glsl */ `
  attribute float aSeed;
  attribute float aLayer;
  attribute float aSize;

  uniform float uTime;
  uniform float uActivity;
  uniform float uMode;

  varying float vEnergy;
  varying float vSeed;
  varying float vLayer;

  mat2 rotate2d(float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return mat2(c, -s, s, c);
  }

  float modeMask(float mode) {
    return 1.0 - smoothstep(0.12, 0.62, abs(uMode - mode));
  }

  void main() {
    vec3 p = position;
    float radius = max(0.001, length(p));
    vec3 direction = p / radius;

    float idle = modeMask(0.0);
    float listening = modeMask(1.0);
    float thinking = modeMask(2.0);
    float speaking = modeMask(3.0);
    float error = modeMask(4.0);

    float breath = sin(uTime * 0.72 + aSeed * 6.28318 + aLayer * 1.7) * 0.5 + 0.5;
    p += direction * (0.010 + breath * 0.026) * (0.48 + uActivity * 0.92);

    float driftPhase = uTime * (0.22 + aLayer * 0.045) + aSeed * 9.0;
    p.x += sin(driftPhase + p.y * 2.8) * 0.018 * (idle + listening * 0.45);
    p.y += cos(driftPhase * 0.82 + p.x * 2.1) * 0.016 * (idle + listening * 0.35);

    float listenRipple = sin(radius * 11.0 - uTime * 2.8 + aSeed * 4.0);
    p += direction * listenRipple * 0.030 * listening * (0.35 + uActivity);
    p.z *= 1.0 - listening * 0.13;

    float thinkingWave = sin((p.y + aSeed * 0.46) * 8.0 + uTime * 2.15);
    float twist = thinking * (0.22 + uActivity * 0.72) * (p.y * 1.28 + thinkingWave * 0.24);
    p.xz = rotate2d(twist) * p.xz;
    p += direction * thinkingWave * 0.052 * thinking * (0.42 + uActivity * 0.72);

    float packet = sin(radius * 15.0 - uTime * 5.2 + aLayer * 1.9 + aSeed * 1.4) * 0.5 + 0.5;
    packet = smoothstep(0.46, 0.98, packet);
    p += direction * packet * (0.034 + uActivity * 0.095) * speaking;

    vec3 glitch = vec3(
      sin(uTime * 15.0 + aSeed * 43.0),
      cos(uTime * 13.0 + aSeed * 31.0),
      sin(uTime * 17.0 + aSeed * 37.0)
    );
    p += glitch * 0.040 * error * (0.38 + uActivity * 0.76);

    vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    float perspective = 82.0 / max(1.0, -mvPosition.z);
    float pointScale = 0.25 + aSize * 0.31 + uActivity * 0.17 + speaking * packet * 0.13;
    gl_PointSize = clamp(pointScale * perspective, 1.35, 11.0);

    float stateEnergy =
      listening * abs(listenRipple) * 0.12 +
      thinking * abs(thinkingWave) * 0.24 +
      speaking * packet * 0.36 +
      error * 0.34;

    vEnergy = clamp(0.24 + uActivity * 0.62 + stateEnergy + aSize * 0.10, 0.0, 1.0);
    vSeed = aSeed;
    vLayer = aLayer;
  }
`;

const agentFragment = /* glsl */ `
  precision highp float;

  uniform float uActivity;
  uniform float uMode;

  varying float vEnergy;
  varying float vSeed;
  varying float vLayer;

  void main() {
    vec2 p = gl_PointCoord - 0.5;
    float d = length(p);
    if (d > 0.5) discard;

    float core = 1.0 - smoothstep(0.055, 0.16, d);
    float body = 1.0 - smoothstep(0.12, 0.31, d);
    float halo = 1.0 - smoothstep(0.22, 0.5, d);

    float alpha = core * 0.72 + body * 0.34 + halo * 0.10;
    alpha *= (0.28 + vEnergy * 0.72) * (0.76 + uActivity * 0.20);

    vec3 bronze = vec3(0.48, 0.39, 0.20);
    vec3 paper = vec3(0.95, 0.91, 0.78);
    vec3 copper = vec3(0.78, 0.34, 0.20);

    float sparkle = smoothstep(0.72, 1.0, vEnergy) * fract(vSeed * 17.13 + vLayer * 0.37);
    float brightness = clamp(vEnergy * 0.78 + core * 0.16 + sparkle * 0.14, 0.0, 1.0);
    vec3 color = mix(bronze, paper, brightness);

    float error = 1.0 - smoothstep(0.12, 0.62, abs(uMode - 4.0));
    color = mix(color, copper, error * 0.62);

    gl_FragColor = vec4(color, alpha);
  }
`;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const damp = (current: number, target: number, response: number, dt: number) =>
  current + (target - current) * (1 - Math.exp(-response * dt));

const atmosphereForScene = (scene: NarrativeScene) => {
  switch (scene) {
    case "hero":
      return { intensity: 1.0, turbulence: 0.48 };
    case "career":
      return { intensity: 0.82, turbulence: 0.30 };
    case "systems":
      return { intensity: 0.88, turbulence: 0.38 };
    case "gallery":
      return { intensity: 0.72, turbulence: 0.24 };
    case "agent":
      return { intensity: 0.96, turbulence: 0.50 };
    default:
      return { intensity: 0.78, turbulence: 0.28 };
  }
};

const phaseMode = (phase: AgentVisualPhase): number => {
  if (phase === "listening") return 1;
  if (phase === "thinking") return 2;
  if (phase === "speaking") return 3;
  if (phase === "error") return 4;
  return 0;
};

const phaseActivity = (phase: AgentVisualPhase): number => {
  if (phase === "listening") return 0.34;
  if (phase === "thinking") return 0.76;
  if (phase === "speaking") return 0.62;
  if (phase === "error") return 0.92;
  return 0.14;
};

const createRing = (radius: number, tiltX: number, tiltY: number, opacity: number) => {
  const points: THREE.Vector3[] = [];
  const segments = 128;
  for (let index = 0; index < segments; index += 1) {
    const angle = (index / segments) * Math.PI * 2;
    points.push(new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, 0));
  }

  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({
    color: 0xcdb675,
    transparent: true,
    opacity,
    depthWrite: false,
  });
  const line = new THREE.LineLoop(geometry, material);
  line.rotation.x = tiltX;
  line.rotation.y = tiltY;
  return line;
};

class StageGraphics {
  private readonly stage: HTMLElement;
  private readonly canvas: HTMLCanvasElement;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly fullscreenGeometry = new THREE.PlaneGeometry(2, 2);
  private readonly atmosphereScene = new THREE.Scene();
  private readonly atmosphereCamera = new THREE.Camera();
  private readonly atmosphereMaterial: THREE.ShaderMaterial;
  private readonly transitionScene = new THREE.Scene();
  private readonly transitionCamera = new THREE.Camera();
  private readonly transitionMaterial: THREE.ShaderMaterial;
  private readonly agentScene = new THREE.Scene();
  private readonly agentCamera = new THREE.PerspectiveCamera(42, 1, 0.1, 30);
  private readonly agentGroup = new THREE.Group();
  private readonly agentGeometry: THREE.BufferGeometry;
  private readonly agentMaterial: THREE.ShaderMaterial;
  private readonly rings: THREE.LineLoop[];
  private readonly nodes: THREE.Mesh[] = [];
  private readonly nodeGeometry = new THREE.SphereGeometry(0.035, 8, 8);
  private readonly resizeObserver: ResizeObserver;
  private unsubscribeNarrative: (() => void) | null = null;
  private scene: NarrativeScene = "hero";
  private atmosphereIntensity = 1;
  private atmosphereTargetIntensity = 1;
  private atmosphereTurbulence = 0.48;
  private atmosphereTargetTurbulence = 0.48;
  private transitionActive = false;
  private pointer = new THREE.Vector2(0.72, 0.34);
  private pointerTarget = new THREE.Vector2(0.72, 0.34);
  private pointerVelocity = 0;
  private pointerVelocityTarget = 0;
  private lastPointer = new THREE.Vector2(0.72, 0.34);
  private lastPointerTime = performance.now();
  private pointerHotUntil = 0;
  private frame = 0;
  private timer = 0;
  private lastRenderTime = performance.now();
  private startTime = performance.now();
  private destroyed = false;

  constructor(stage: HTMLElement) {
    this.stage = stage;
    this.canvas = document.createElement("canvas");
    this.canvas.className = "ref-stage-graphics";
    this.canvas.setAttribute("aria-hidden", "true");
    stage.prepend(this.canvas);

    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      alpha: true,
      antialias: false,
      powerPreference: "high-performance",
    });
    this.renderer.autoClear = false;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.setClearColor(0x000000, 0);

    this.atmosphereMaterial = new THREE.ShaderMaterial({
      vertexShader: fullscreenVertex,
      fragmentShader: atmosphereFragment,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      uniforms: {
        uResolution: { value: new THREE.Vector2(1, 1) },
        uPointer: { value: this.pointer.clone() },
        uTime: { value: 0 },
        uVelocity: { value: 0 },
        uIntensity: { value: 1 },
        uTurbulence: { value: 0.48 },
      },
    });
    this.atmosphereScene.add(new THREE.Mesh(this.fullscreenGeometry, this.atmosphereMaterial));

    this.transitionMaterial = new THREE.ShaderMaterial({
      vertexShader: fullscreenVertex,
      fragmentShader: transitionFragment,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      uniforms: {
        uResolution: { value: new THREE.Vector2(1, 1) },
        uProgress: { value: 0 },
        uDirection: { value: 1 },
        uTime: { value: 0 },
      },
    });
    this.transitionScene.add(new THREE.Mesh(this.fullscreenGeometry, this.transitionMaterial));

    const pointCount = 4096;
    const positions = new Float32Array(pointCount * 3);
    const seeds = new Float32Array(pointCount);
    const layers = new Float32Array(pointCount);
    const sizes = new Float32Array(pointCount);
    const goldenAngle = 2.399963229728653;
    const fract = (value: number) => value - Math.floor(value);
    const hash = (index: number, salt: number) =>
      fract(Math.sin((index + 1) * (12.9898 + salt * 17.233)) * 43758.5453);

    for (let index = 0; index < pointCount; index += 1) {
      const t = (index + 0.5) / pointCount;
      const y = 1 - t * 2;
      const radial = Math.sqrt(Math.max(0, 1 - y * y));
      const angle = index * goldenAngle;
      const seed = hash(index, 0.31);
      const shellSelector = hash(index, 1.17);
      const radialSeed = hash(index, 2.41);
      const radius =
        shellSelector < 0.68
          ? 0.72 + radialSeed * 0.30
          : 0.18 + Math.cbrt(radialSeed) * 0.66;
      const asymmetry = 1 + Math.sin(angle * 3 + seed * Math.PI * 2) * 0.055;

      positions[index * 3] = Math.cos(angle) * radial * radius * asymmetry;
      positions[index * 3 + 1] = y * radius * 1.10;
      positions[index * 3 + 2] = Math.sin(angle) * radial * radius / asymmetry;
      seeds[index] = seed;
      layers[index] = index % 3;
      sizes[index] = 0.34 + hash(index, 3.73) * 0.66;
    }

    this.agentGeometry = new THREE.BufferGeometry();
    this.agentGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    this.agentGeometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));
    this.agentGeometry.setAttribute("aLayer", new THREE.BufferAttribute(layers, 1));
    this.agentGeometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    this.agentGeometry.computeBoundingSphere();

    this.agentMaterial = new THREE.ShaderMaterial({
      vertexShader: agentVertex,
      fragmentShader: agentFragment,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uActivity: { value: agentSignal.activity },
        uMode: { value: 0 },
      },
    });
    this.agentGroup.add(new THREE.Points(this.agentGeometry, this.agentMaterial));

    this.rings = [
      createRing(1.28, 0.42, 0.14, 0.17),
      createRing(1.48, -0.62, 0.32, 0.10),
      createRing(1.08, 0.18, -0.72, 0.14),
    ];
    this.rings.forEach((ring) => this.agentGroup.add(ring));

    const nodePositions = [
      new THREE.Vector3(1.42, 0.22, 0.16),
      new THREE.Vector3(-1.18, 0.76, -0.22),
      new THREE.Vector3(0.54, -1.22, 0.32),
      new THREE.Vector3(-0.82, -0.92, 0.46),
    ];
    nodePositions.forEach((position, index) => {
      const material = new THREE.MeshBasicMaterial({
        color: index === 0 ? 0xf2eddc : 0xcdb675,
        transparent: true,
        opacity: 0.58,
      });
      const node = new THREE.Mesh(this.nodeGeometry, material);
      node.position.copy(position);
      this.nodes.push(node);
      this.agentGroup.add(node);
    });

    this.agentGroup.visible = false;
    this.agentScene.add(this.agentGroup);
    this.agentCamera.position.set(0, 0, 6.2);

    this.resizeObserver = new ResizeObserver(this.resize);
    this.resizeObserver.observe(stage);
    this.resize();

    addEventListener("pointermove", this.onPointerMove, { passive: true });
    document.addEventListener("visibilitychange", this.onVisibility);

    this.unsubscribeNarrative = narrativeRuntime.subscribe((state) => {
      this.scene = state.scene;
      const atmosphere = atmosphereForScene(state.scene);
      this.atmosphereTargetIntensity = atmosphere.intensity;
      this.atmosphereTargetTurbulence = atmosphere.turbulence;
      this.agentGroup.visible = state.scene === "agent";
      this.wake();
    });

    this.schedule(0);
  }

  setTransition(progress: number, direction: number, active: boolean): void {
    this.transitionActive = active;
    this.transitionMaterial.uniforms.uProgress.value = clamp01(progress);
    this.transitionMaterial.uniforms.uDirection.value = direction < 0 ? -1 : 1;
    this.canvas.classList.toggle("is-transitioning", active);
    this.stage.classList.toggle("has-webgl-transition", active);
    this.wake();
  }

  wake(): void {
    if (this.destroyed || document.hidden || this.frame || this.timer) return;
    this.schedule(0);
  }

  private targetFps(): number {
    if (this.transitionActive || this.scene === "agent") return 60;
    if (performance.now() < this.pointerHotUntil) return 36;
    return 24;
  }

  private schedule(delay?: number): void {
    if (this.destroyed || document.hidden || this.frame || this.timer) return;
    const wait = delay ?? 1000 / this.targetFps();
    this.timer = window.setTimeout(() => {
      this.timer = 0;
      this.frame = requestAnimationFrame(this.render);
    }, wait);
  }

  private resize = (): void => {
    const rect = this.stage.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return;

    const dprCap = rect.width < 720 ? 1 : 1.25;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, dprCap));
    this.renderer.setSize(rect.width, rect.height, false);
    this.atmosphereMaterial.uniforms.uResolution.value.set(rect.width, rect.height);
    this.transitionMaterial.uniforms.uResolution.value.set(rect.width, rect.height);
    this.agentCamera.aspect = rect.width / rect.height;
    this.agentCamera.updateProjectionMatrix();

    const desktop = rect.width >= 900;
    this.agentGroup.position.x = desktop ? -1.42 : 0;
    this.agentGroup.position.y = desktop ? -0.05 : 0.22;
    this.agentGroup.scale.setScalar(desktop ? 1.0 : 0.82);
    this.wake();
  };

  private onPointerMove = (event: PointerEvent): void => {
    const rect = this.stage.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const x = clamp01((event.clientX - rect.left) / rect.width);
    const y = 1 - clamp01((event.clientY - rect.top) / rect.height);
    this.pointerTarget.set(x, y);

    const now = performance.now();
    const elapsed = Math.max(16, now - this.lastPointerTime);
    const distance = this.pointerTarget.distanceTo(this.lastPointer);
    this.pointerVelocityTarget = Math.min(1, (distance / elapsed) * 1800);
    this.lastPointer.copy(this.pointerTarget);
    this.lastPointerTime = now;
    this.pointerHotUntil = now + 700;
    this.wake();
  };

  private onVisibility = (): void => {
    if (document.hidden) {
      if (this.frame) cancelAnimationFrame(this.frame);
      if (this.timer) clearTimeout(this.timer);
      this.frame = 0;
      this.timer = 0;
      return;
    }

    this.lastRenderTime = performance.now();
    this.wake();
  };

  private render = (now: number): void => {
    this.frame = 0;
    if (this.destroyed || document.hidden) return;

    const dt = Math.min(0.05, Math.max(0.001, (now - this.lastRenderTime) / 1000));
    this.lastRenderTime = now;
    const elapsed = (now - this.startTime) / 1000;

    this.pointer.lerp(this.pointerTarget, 1 - Math.exp(-7.5 * dt));
    this.pointerVelocity = damp(this.pointerVelocity, this.pointerVelocityTarget, 10, dt);
    this.pointerVelocityTarget *= Math.exp(-7.5 * dt);
    this.atmosphereIntensity = damp(
      this.atmosphereIntensity,
      this.atmosphereTargetIntensity,
      3.2,
      dt,
    );
    this.atmosphereTurbulence = damp(
      this.atmosphereTurbulence,
      this.atmosphereTargetTurbulence,
      2.8,
      dt,
    );

    const baseActivity = phaseActivity(agentSignal.phase);
    agentSignal.activityTarget = Math.max(baseActivity, agentSignal.activityTarget * Math.exp(-2.4 * dt));
    agentSignal.activity = damp(agentSignal.activity, agentSignal.activityTarget, 5.0, dt);

    this.atmosphereMaterial.uniforms.uPointer.value.copy(this.pointer);
    this.atmosphereMaterial.uniforms.uVelocity.value = this.pointerVelocity;
    this.atmosphereMaterial.uniforms.uTime.value = elapsed;
    this.atmosphereMaterial.uniforms.uIntensity.value = this.atmosphereIntensity;
    this.atmosphereMaterial.uniforms.uTurbulence.value = this.atmosphereTurbulence;

    this.transitionMaterial.uniforms.uTime.value = elapsed;
    this.agentMaterial.uniforms.uTime.value = elapsed;
    this.agentMaterial.uniforms.uActivity.value = agentSignal.activity;
    this.agentMaterial.uniforms.uMode.value = phaseMode(agentSignal.phase);

    if (this.agentGroup.visible) {
      const rotationSpeed =
        agentSignal.phase === "thinking"
          ? 0.20
          : agentSignal.phase === "speaking"
            ? 0.12
            : agentSignal.phase === "error"
              ? 0.18
              : 0.055;
      this.agentGroup.rotation.y += rotationSpeed * dt;
      this.agentGroup.rotation.x = Math.sin(elapsed * 0.18) * 0.085;
      this.agentGroup.rotation.z = Math.sin(elapsed * 0.11) * 0.025;
      this.rings[0].rotation.z += (0.06 + agentSignal.activity * 0.07) * dt;
      this.rings[1].rotation.z -= (0.045 + agentSignal.activity * 0.045) * dt;
      this.rings[2].rotation.z += (0.08 + agentSignal.activity * 0.075) * dt;
      this.nodes.forEach((node, index) => {
        const scale =
          0.78 +
          Math.sin(elapsed * (0.82 + index * 0.10) + index) * 0.12 +
          agentSignal.activity * 0.20;
        node.scale.setScalar(scale);
      });
    }

    this.renderer.clear();
    this.renderer.render(this.atmosphereScene, this.atmosphereCamera);
    if (this.agentGroup.visible) {
      this.renderer.clearDepth();
      this.renderer.render(this.agentScene, this.agentCamera);
    }
    if (this.transitionActive) {
      this.renderer.clearDepth();
      this.renderer.render(this.transitionScene, this.transitionCamera);
    }

    this.schedule();
  };

  destroy(): void {
    this.destroyed = true;
    if (this.frame) cancelAnimationFrame(this.frame);
    if (this.timer) clearTimeout(this.timer);
    this.resizeObserver.disconnect();
    this.unsubscribeNarrative?.();
    removeEventListener("pointermove", this.onPointerMove);
    document.removeEventListener("visibilitychange", this.onVisibility);

    this.fullscreenGeometry.dispose();
    this.atmosphereMaterial.dispose();
    this.transitionMaterial.dispose();
    this.agentGeometry.dispose();
    this.agentMaterial.dispose();
    this.rings.forEach((ring) => {
      ring.geometry.dispose();
      (ring.material as THREE.Material).dispose();
    });
    this.nodes.forEach((node) => (node.material as THREE.Material).dispose());
    this.nodeGeometry.dispose();
    this.renderer.dispose();
    this.canvas.remove();
    this.stage.classList.remove("has-webgl-transition");
  }
}

export const mountStageGraphics = (): (() => void) => {
  const stage = document.querySelector<HTMLElement>(".ref-stage");
  if (!stage) return () => undefined;

  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) return () => undefined;

  mountedGraphics?.destroy();
  mountedGraphics = new StageGraphics(stage);

  return () => {
    mountedGraphics?.destroy();
    mountedGraphics = null;
  };
};
