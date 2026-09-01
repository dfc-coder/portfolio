import * as THREE from "three";
import type { AgentVisualSignals } from "./agent-visual-controller";

const particleVertex = /* glsl */ `
  attribute float aSeed;
  attribute float aLayer;
  attribute float aSize;

  uniform float uTime;
  uniform float uActivity;
  uniform float uSpeech;
  uniform float uInteraction;
  uniform float uMode;
  uniform float uTone;
  uniform float uThinkingBlend;
  uniform vec2 uPointer;
  uniform float uPointerForce;
  uniform float uPointerVelocity;

  varying float vEnergy;
  varying float vSeed;
  varying float vLayer;
  varying float vThinking;

  const float TAU = 6.28318530718;

  float modeMask(float mode) {
    return 1.0 - smoothstep(0.14, 0.68, abs(uMode - mode));
  }

  float toneMask(float tone) {
    return 1.0 - smoothstep(0.18, 0.72, abs(uTone - tone));
  }

  void main() {
    vec3 sphere = position;

    float listening = modeMask(1.0);
    float thinking = modeMask(2.0);
    float speaking = modeMask(3.0);
    float error = modeMask(4.0);

    float curious = toneMask(1.0);
    float focused = toneMask(2.0);
    float confident = toneMask(3.0);
    float uncertain = toneMask(4.0);

    // THINKING POSE ---------------------------------------------------------
    // Most particles leave the sphere and form three orbital planes above a
    // compact core. The selection is deterministic so the pose is stable.
    float haloParticle = 1.0 - step(0.58, aSeed);
    float orbit = aSeed * TAU * 2.4 + uTime * (1.45 + aLayer * 0.11);

    vec3 haloA = vec3(
      cos(orbit) * 0.82,
      0.98 + sin(orbit * 2.0 + aSeed * 3.0) * 0.075,
      sin(orbit) * 0.34
    );
    vec3 haloB = vec3(
      cos(orbit) * 0.70,
      0.98 + sin(orbit) * 0.31,
      sin(orbit) * 0.24
    );
    vec3 haloC = vec3(
      cos(orbit) * 0.58,
      0.98 + sin(orbit) * 0.27,
      sin(orbit) * 0.46
    );

    vec3 haloTarget = aLayer < 0.5 ? haloA : (aLayer < 1.5 ? haloB : haloC);
    vec3 coreTarget = sphere * (0.58 + aSize * 0.04);
    coreTarget.y -= 0.30;

    vec3 thinkingTarget = mix(coreTarget, haloTarget, haloParticle);
    vec3 p = mix(sphere, thinkingTarget, uThinkingBlend);

    float radius = max(0.001, length(p));
    vec3 direction = p / radius;

    // CONTINUOUS LIFE -------------------------------------------------------
    // Motion never stops, but remains the quietest layer in the hierarchy.
    float driftA = sin(uTime * 0.76 + p.y * 3.4 + aSeed * TAU);
    float driftB = cos(uTime * 0.57 + p.x * 2.8 + aSeed * 4.1);
    vec3 tangent = normalize(vec3(-direction.z, 0.16 + aLayer * 0.035, direction.x));
    p += tangent * driftA * (0.008 + aLayer * 0.0015) * (1.0 - uThinkingBlend * 0.28);
    p += normalize(cross(direction, tangent)) * driftB * 0.005;

    float breath = sin(uTime * 0.45 + aSeed * 2.2) * 0.5 + 0.5;
    p += direction * breath * 0.009 * (1.0 - uThinkingBlend * 0.52);

    // LISTENING / POINTER ATTENTION ----------------------------------------
    // Nearby particles lean toward the pointer. Faster cursor motion leaves a
    // short tangential wake. Curious/listening states amplify this response.
    vec2 toPointer = uPointer - p.xy;
    float pointerDistance = length(toPointer);
    float proximity = exp(-pointerDistance * 2.65) * uPointerForce;
    float attention = 0.34 + listening * 0.92 + curious * 0.16;
    p.xy += toPointer * proximity * attention * 0.092;

    vec2 safeDirection = pointerDistance > 0.0001 ? toPointer / pointerDistance : vec2(0.0, 1.0);
    vec2 wakeDirection = vec2(-safeDirection.y, safeDirection.x);
    p.xy += wakeDirection * proximity * uPointerVelocity * (0.030 + listening * 0.026);

    float listenRipple = sin(radius * 11.0 - uTime * 2.2 + aSeed * 3.0);
    p += direction * listenRipple * 0.025 * listening * (0.55 + uPointerForce * 0.45);
    p *= 1.0 - listening * 0.025;

    // SPEAKING --------------------------------------------------------------
    // The speech envelope is independent from general activity. Each emitted
    // word creates a radial packet, brightens the cloud and biases energy toward
    // the conversation panel on the right.
    float speechPacket = sin(radius * 11.5 - uTime * 7.2 + aSeed * 1.7 + aLayer * 0.74);
    speechPacket = smoothstep(0.12, 0.96, speechPacket * 0.5 + 0.5);
    float speechAmplitude = uSpeech * speaking * (1.0 + confident * 0.14);
    p += direction * speechPacket * speechAmplitude * 0.145;
    p += direction * speechAmplitude * 0.030;
    p.x += speechAmplitude * (0.024 + max(direction.x, 0.0) * 0.030);

    // CLICK / DIRECT ENGAGEMENT -------------------------------------------
    p *= 1.0 - uInteraction * 0.045;
    p += direction * sin(radius * 9.0 - uTime * 5.5) * uInteraction * 0.020;

    // ERROR / UNCERTAIN -----------------------------------------------------
    vec3 glitch = vec3(
      sin(uTime * 11.0 + aSeed * 41.0),
      cos(uTime * 9.0 + aSeed * 29.0),
      sin(uTime * 12.0 + aSeed * 37.0)
    );
    p += glitch * error * uncertain * 0.018;

    vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    float perspective = 82.0 / max(1.0, -mvPosition.z);
    float pointScale =
      0.27 +
      aSize * 0.35 +
      uActivity * 0.09 +
      speechPacket * speechAmplitude * 0.34 +
      uThinkingBlend * haloParticle * 0.08;
    gl_PointSize = clamp(pointScale * perspective, 1.25, 11.5);

    float stateEnergy =
      listening * (abs(listenRipple) * 0.10 + proximity * 0.18) +
      focused * uThinkingBlend * haloParticle * 0.22 +
      speechPacket * speechAmplitude * 0.72 +
      uInteraction * 0.18 +
      error * 0.30;

    vEnergy = clamp(0.23 + uActivity * 0.34 + stateEnergy + aSize * 0.12, 0.0, 1.0);
    vSeed = aSeed;
    vLayer = aLayer;
    vThinking = uThinkingBlend * haloParticle;
  }
`;

const particleFragment = /* glsl */ `
  precision highp float;

  uniform float uSpeech;
  uniform float uMode;
  uniform float uTone;

  varying float vEnergy;
  varying float vSeed;
  varying float vLayer;
  varying float vThinking;

  float toneMask(float tone) {
    return 1.0 - smoothstep(0.18, 0.72, abs(uTone - tone));
  }

  void main() {
    vec2 p = gl_PointCoord - 0.5;
    float d = length(p);
    if (d > 0.5) discard;

    float core = 1.0 - smoothstep(0.035, 0.14, d);
    float body = 1.0 - smoothstep(0.10, 0.29, d);
    float halo = 1.0 - smoothstep(0.20, 0.5, d);

    float alpha = core * 0.80 + body * 0.34 + halo * 0.09;
    alpha *= 0.30 + vEnergy * 0.70;

    vec3 amber = vec3(0.58, 0.39, 0.10);
    vec3 gold = vec3(0.92, 0.69, 0.22);
    vec3 ivory = vec3(0.97, 0.92, 0.77);
    vec3 focusedIvory = vec3(0.94, 0.90, 0.82);
    vec3 errorColor = vec3(0.82, 0.28, 0.18);

    float sparkle = smoothstep(0.68, 1.0, vEnergy) * fract(vSeed * 19.17 + vLayer * 0.43);
    float bright = clamp(vEnergy * 0.80 + core * 0.15 + sparkle * 0.18 + uSpeech * 0.10, 0.0, 1.0);
    vec3 color = mix(amber, gold, smoothstep(0.12, 0.70, bright));
    color = mix(color, ivory, smoothstep(0.66, 1.0, bright));

    float focused = toneMask(2.0);
    float confident = toneMask(3.0);
    color = mix(color, focusedIvory, focused * vThinking * 0.30);
    color += ivory * confident * uSpeech * core * 0.08;

    float error = 1.0 - smoothstep(0.16, 0.66, abs(uMode - 4.0));
    color = mix(color, errorColor, error * 0.62);

    gl_FragColor = vec4(color, alpha);
  }
`;

export class AgentParticleCloud {
  readonly points: THREE.Points;

  private readonly geometry: THREE.BufferGeometry;
  private readonly material: THREE.ShaderMaterial;
  private rotationSpeed = 0.035;
  private baseRotationY = 0;

  constructor() {
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
        shellSelector < 0.72
          ? 0.73 + radialSeed * 0.29
          : 0.16 + Math.cbrt(radialSeed) * 0.68;
      const asymmetry = 1 + Math.sin(angle * 3 + seed * Math.PI * 2) * 0.042;

      positions[index * 3] = Math.cos(angle) * radial * radius * asymmetry;
      positions[index * 3 + 1] = y * radius * 1.08;
      positions[index * 3 + 2] = Math.sin(angle) * radial * radius / asymmetry;
      seeds[index] = seed;
      layers[index] = index % 3;
      sizes[index] = 0.34 + hash(index, 3.73) * 0.66;
    }

    this.geometry = new THREE.BufferGeometry();
    this.geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    this.geometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));
    this.geometry.setAttribute("aLayer", new THREE.BufferAttribute(layers, 1));
    this.geometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    this.geometry.computeBoundingSphere();

    this.material = new THREE.ShaderMaterial({
      vertexShader: particleVertex,
      fragmentShader: particleFragment,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uActivity: { value: 0.1 },
        uSpeech: { value: 0 },
        uInteraction: { value: 0 },
        uMode: { value: 0 },
        uTone: { value: 0 },
        uThinkingBlend: { value: 0 },
        uPointer: { value: new THREE.Vector2() },
        uPointerForce: { value: 0 },
        uPointerVelocity: { value: 0 },
      },
    });

    this.points = new THREE.Points(this.geometry, this.material);
    this.points.frustumCulled = false;
  }

  update(signals: AgentVisualSignals, dt: number): void {
    this.material.uniforms.uTime.value = signals.time;
    this.material.uniforms.uActivity.value = signals.activity;
    this.material.uniforms.uSpeech.value = signals.speech;
    this.material.uniforms.uInteraction.value = signals.interaction;
    this.material.uniforms.uMode.value = signals.mode;
    this.material.uniforms.uTone.value = signals.toneMode;
    this.material.uniforms.uThinkingBlend.value = signals.thinkingBlend;
    this.material.uniforms.uPointer.value.set(signals.pointerX, signals.pointerY);
    this.material.uniforms.uPointerForce.value = signals.pointerForce;
    this.material.uniforms.uPointerVelocity.value = signals.pointerVelocity;

    const thinking = signals.thinkingBlend;
    const speaking = signals.phase === "speaking" ? 1 : 0;
    const targetRotation = 0.030 + thinking * 0.020 + speaking * 0.015;
    this.rotationSpeed += (targetRotation - this.rotationSpeed) * (1 - Math.exp(-3.2 * dt));
    this.baseRotationY += this.rotationSpeed * dt;

    const attention = signals.pointerForce * (signals.phase === "listening" ? 1 : 0.42);
    this.points.rotation.y = this.baseRotationY + signals.pointerX * attention * 0.13;
    this.points.rotation.x =
      Math.sin(signals.time * 0.14) * 0.035 - signals.pointerY * attention * 0.085;
    this.points.rotation.z = signals.pointerX * signals.pointerVelocity * attention * 0.018;

    const speechScale = 1 + signals.speech * speaking * 0.052;
    const interactionScale = 1 - signals.interaction * 0.042;
    this.points.scale.setScalar(speechScale * interactionScale);
  }

  dispose(): void {
    this.geometry.dispose();
    this.material.dispose();
  }
}
