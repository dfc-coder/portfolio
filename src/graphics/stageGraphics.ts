import * as THREE from "three";
import { agentLiquidFragment, agentLiquidVertex } from "./agent-liquid-shader";
import { AgentParticleCloud } from "./agent-particle-cloud";
import {
  agentVisualNeedsFrame,
  bindAgentVisualWake,
  setAgentPointer,
  updateAgentVisual,
} from "./agent-visual-controller";

let mountedGraphics: StageGraphics | null = null;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const damp = (current: number, target: number, response: number, dt: number) =>
  current + (target - current) * (1 - Math.exp(-response * dt));

class StageGraphics {
  private readonly stage: HTMLElement;
  private readonly canvas: HTMLCanvasElement;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly agentScene = new THREE.Scene();
  private readonly agentCamera = new THREE.PerspectiveCamera(42, 1, 0.1, 30);
  private readonly agentGroup = new THREE.Group();
  private readonly agentGeometry = new THREE.PlaneGeometry(2.32, 2.32, 1, 1);
  private readonly agentMaterial: THREE.ShaderMaterial;
  private readonly agentMesh: THREE.Mesh;
  private readonly agentParticles = new AgentParticleCloud();
  private readonly resizeObserver: ResizeObserver;

  private pointer = new THREE.Vector2(0.72, 0.34);
  private pointerTarget = new THREE.Vector2(0.72, 0.34);
  private pointerVelocity = 0;
  private pointerVelocityTarget = 0;
  private lastPointer = new THREE.Vector2(0.72, 0.34);
  private lastPointerTime = performance.now();
  private agentScreenCenter = new THREE.Vector2(0.28, 0.50);
  private stageRect: DOMRectReadOnly | null = null;
  private frame = 0;
  private lastRenderTime = performance.now();
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
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.setClearColor(0x000000, 0);

    this.agentMaterial = new THREE.ShaderMaterial({
      vertexShader: agentLiquidVertex,
      fragmentShader: agentLiquidFragment,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uActivity: { value: 0.10 },
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
    this.agentScene.add(this.agentGroup);
    this.agentCamera.position.set(0, 0, 6.2);

    this.resizeObserver = new ResizeObserver(this.resize);
    this.resizeObserver.observe(stage);
    this.resize();

    addEventListener("pointermove", this.onPointerMove, { passive: true });
    document.addEventListener("visibilitychange", this.onVisibility);
    bindAgentVisualWake(this.wake);
    this.wake();
  }

  wake = (): void => {
    if (this.destroyed || document.hidden || this.frame) return;
    this.frame = requestAnimationFrame(this.render);
  };

  private pointerNeedsFrame(): boolean {
    return (
      this.pointer.distanceToSquared(this.pointerTarget) > 0.000001 ||
      this.pointerVelocity > 0.002 ||
      this.pointerVelocityTarget > 0.002
    );
  }

  private resize = (): void => {
    const rect = this.stage.getBoundingClientRect();
    this.stageRect = rect;
    if (rect.width < 2 || rect.height < 2) return;

    const dprCap = rect.width < 720 ? 1 : 1.25;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, dprCap));
    this.renderer.setSize(rect.width, rect.height, false);
    this.agentCamera.aspect = rect.width / rect.height;
    this.agentCamera.updateProjectionMatrix();

    const desktop = rect.width >= 900;
    this.agentGroup.position.x = desktop ? -1.47 : 0;
    this.agentGroup.position.y = desktop ? -0.02 : 0.18;
    this.agentGroup.scale.setScalar(desktop ? 1.08 : 0.80);
    this.agentScreenCenter.set(desktop ? 0.28 : 0.50, desktop ? 0.50 : 0.40);
    this.wake();
  };

  private onPointerMove = (event: PointerEvent): void => {
    const rect = this.stageRect;
    if (!rect?.width || !rect.height) return;

    const x = clamp01((event.clientX - rect.left) / rect.width);
    const y = 1 - clamp01((event.clientY - rect.top) / rect.height);
    this.pointerTarget.set(x, y);

    const now = performance.now();
    const elapsed = Math.max(16, now - this.lastPointerTime);
    const distance = this.pointerTarget.distanceTo(this.lastPointer);
    this.pointerVelocityTarget = Math.min(1, (distance / elapsed) * 1800);
    this.lastPointer.copy(this.pointerTarget);
    this.lastPointerTime = now;

    const distanceToOrb = this.pointerTarget.distanceTo(this.agentScreenCenter);
    const force = Math.exp(-distanceToOrb * 4.4);
    const localX = Math.max(-1, Math.min(1, (x - this.agentScreenCenter.x) * 3.5));
    const localY = Math.max(-1, Math.min(1, (y - this.agentScreenCenter.y) * 3.5));
    setAgentPointer(localX, localY, this.pointerVelocityTarget, force);
  };

  private onVisibility = (): void => {
    if (document.hidden) {
      if (this.frame) cancelAnimationFrame(this.frame);
      this.frame = 0;
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

    this.pointer.lerp(this.pointerTarget, 1 - Math.exp(-7.5 * dt));
    this.pointerVelocity = damp(this.pointerVelocity, this.pointerVelocityTarget, 10, dt);
    this.pointerVelocityTarget *= Math.exp(-7.5 * dt);

    const signals = updateAgentVisual(dt);

    this.agentMaterial.uniforms.uTime.value = signals.time;
    this.agentMaterial.uniforms.uActivity.value = signals.activity;
    this.agentMaterial.uniforms.uSpeech.value = signals.speech;
    this.agentMaterial.uniforms.uMode.value = signals.mode;
    this.agentMaterial.uniforms.uPointer.value.copy(this.pointer);

    this.agentParticles.update(signals, dt);

    const speaking = signals.phase === "speaking" ? 1 : 0;
    const fluidScale =
      0.96 -
      signals.thinkingBlend * 0.16 +
      signals.speech * speaking * 0.035 -
      signals.interaction * 0.025;
    this.agentMesh.scale.setScalar(fluidScale);
    this.agentMesh.position.y = -signals.thinkingBlend * 0.22;

    this.renderer.render(this.agentScene, this.agentCamera);

    if (agentVisualNeedsFrame() || this.pointerNeedsFrame()) {
      this.wake();
    }
  };

  destroy(): void {
    this.destroyed = true;
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
    bindAgentVisualWake(null);
    this.resizeObserver.disconnect();
    removeEventListener("pointermove", this.onPointerMove);
    document.removeEventListener("visibilitychange", this.onVisibility);

    this.agentGeometry.dispose();
    this.agentMaterial.dispose();
    this.agentParticles.dispose();
    this.renderer.dispose();
    this.canvas.remove();
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
