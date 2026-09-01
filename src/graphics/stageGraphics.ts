import * as THREE from "three";
import { narrativeRuntime, type NarrativeScene } from "../experiences/narrative-runtime";
import { agentLiquidFragment, agentLiquidVertex } from "./agent-liquid-shader";
import { AgentParticleCloud } from "./agent-particle-cloud";

export type AgentVisualPhase = "idle" | "listening" | "thinking" | "speaking" | "error";

interface AgentSignalState {
  phase: AgentVisualPhase;
  activity: number;
  activityTarget: number;
  speech: number;
  speechTarget: number;
}

const agentSignal: AgentSignalState = {
  phase: "idle",
  activity: 0.10,
  activityTarget: 0.10,
  speech: 0,
  speechTarget: 0,
};

let mountedGraphics: StageGraphics | null = null;

export const setAgentVisualPhase = (phase: AgentVisualPhase): void => {
  agentSignal.phase = phase;
  if (phase !== "speaking") agentSignal.speechTarget = 0;
  mountedGraphics?.wake();
};

export const pulseAgentVisual = (strength = 0.3): void => {
  const impulse = Math.min(1, Math.max(0, strength));
  agentSignal.activityTarget = Math.max(agentSignal.activityTarget, impulse);
  mountedGraphics?.wake();
};

export const pulseAgentSpeech = (strength = 0.6): void => {
  const impulse = Math.min(1, Math.max(0, strength));
  agentSignal.speechTarget = Math.max(agentSignal.speechTarget, impulse);
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
  if (phase === "listening") return 0.14;
  if (phase === "thinking") return 0.28;
  if (phase === "speaking") return 0.14;
  if (phase === "error") return 0.30;
  return 0.10;
};

const phaseMotionRate = (phase: AgentVisualPhase): number => {
  if (phase === "thinking") return 0.54;
  if (phase === "speaking") return 0.34;
  if (phase === "listening") return 0.31;
  if (phase === "error") return 0.42;
  return 0.26;
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
  private readonly agentGeometry = new THREE.PlaneGeometry(2.32, 2.32, 1, 1);
  private readonly agentMaterial: THREE.ShaderMaterial;
  private readonly agentMesh: THREE.Mesh;
  private readonly agentParticles = new AgentParticleCloud();
  private readonly resizeObserver: ResizeObserver;
  private unsubscribeNarrative: (() => void) | null = null;
  private scene: NarrativeScene = "hero";
  private atmosphereIntensity = 1;
  private atmosphereTargetIntensity = 1;
  private atmosphereTurbulence = 0.48;
  private atmosphereTargetTurbulence = 0.48;
  private agentMode = 0;
  private agentTime = 0;
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

    this.agentMaterial = new THREE.ShaderMaterial({
      vertexShader: agentLiquidVertex,
      fragmentShader: agentLiquidFragment,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uActivity: { value: agentSignal.activity },
        uSpeech: { value: 0 },
        uMode: { value: 0 },
        uPointer: { value: this.pointer.clone() },
      },
    });

    this.agentMesh = new THREE.Mesh(this.agentGeometry, this.agentMaterial);
    this.agentMesh.frustumCulled = false;
    this.agentMesh.position.z = -0.34;
    this.agentGroup.add(this.agentMesh);
    this.agentGroup.add(this.agentParticles.points);
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
    this.agentGroup.position.x = desktop ? -1.47 : 0;
    this.agentGroup.position.y = desktop ? -0.02 : 0.18;
    this.agentGroup.scale.setScalar(desktop ? 1.08 : 0.80);
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
    const excessActivity = Math.max(0, agentSignal.activityTarget - baseActivity);
    agentSignal.activityTarget = baseActivity + excessActivity * Math.exp(-7.0 * dt);
    agentSignal.activity = damp(agentSignal.activity, agentSignal.activityTarget, 8.0, dt);

    agentSignal.speechTarget *= Math.exp(-7.2 * dt);
    const speechResponse = agentSignal.speechTarget > agentSignal.speech ? 24.0 : 9.0;
    agentSignal.speech = damp(agentSignal.speech, agentSignal.speechTarget, speechResponse, dt);
    if (agentSignal.phase !== "speaking") agentSignal.speech *= Math.exp(-12.0 * dt);

    this.agentMode = damp(this.agentMode, phaseMode(agentSignal.phase), 3.4, dt);
    this.agentTime += dt * phaseMotionRate(agentSignal.phase);

    this.atmosphereMaterial.uniforms.uPointer.value.copy(this.pointer);
    this.atmosphereMaterial.uniforms.uVelocity.value = this.pointerVelocity;
    this.atmosphereMaterial.uniforms.uTime.value = elapsed;
    this.atmosphereMaterial.uniforms.uIntensity.value = this.atmosphereIntensity;
    this.atmosphereMaterial.uniforms.uTurbulence.value = this.atmosphereTurbulence;

    this.transitionMaterial.uniforms.uTime.value = elapsed;
    this.agentMaterial.uniforms.uTime.value = this.agentTime;
    this.agentMaterial.uniforms.uActivity.value = agentSignal.activity;
    this.agentMaterial.uniforms.uSpeech.value = agentSignal.speech;
    this.agentMaterial.uniforms.uMode.value = this.agentMode;
    this.agentMaterial.uniforms.uPointer.value.copy(this.pointer);

    this.agentParticles.update({
      time: this.agentTime,
      activity: agentSignal.activity,
      speech: agentSignal.speech,
      mode: this.agentMode,
      dt,
    });

    const speaking = agentSignal.phase === "speaking" ? 1 : 0;
    this.agentMesh.scale.setScalar(0.96 + agentSignal.speech * speaking * 0.018);

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
    this.agentParticles.dispose();
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
