import * as THREE from "three";

const particleVertex = /* glsl */ `
  attribute float aSeed;
  attribute float aLayer;
  attribute float aSize;

  uniform float uTime;
  uniform float uActivity;
  uniform float uSpeech;
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
    return 1.0 - smoothstep(0.14, 0.68, abs(uMode - mode));
  }

  void main() {
    vec3 p = position;
    float radius = max(0.001, length(p));
    vec3 direction = p / radius;

    float listening = modeMask(1.0);
    float thinking = modeMask(2.0);
    float speaking = modeMask(3.0);
    float error = modeMask(4.0);

    // Continuous, low-energy circulation. This never stops while the orb is alive.
    float driftA = sin(uTime * 0.72 + p.y * 3.8 + aSeed * 6.28318);
    float driftB = cos(uTime * 0.54 + p.x * 3.1 + aSeed * 4.3);
    vec3 tangent = normalize(vec3(-direction.z, 0.18 + aLayer * 0.04, direction.x));
    p += tangent * driftA * (0.010 + aLayer * 0.002);
    p += normalize(cross(direction, tangent)) * driftB * 0.006;

    // A very small autonomous breath keeps the cloud organic without looking noisy.
    float breath = sin(uTime * 0.42 + aSeed * 2.4) * 0.5 + 0.5;
    p += direction * breath * 0.010;

    // Listening pulls the shell slightly inward and creates a fine surface ripple.
    float listenRipple = sin(radius * 11.0 - uTime * 1.9 + aSeed * 3.0);
    p += direction * listenRipple * 0.018 * listening;
    p *= 1.0 - listening * 0.018;

    // Thinking is organized motion: a slow twist, not random agitation.
    float thinkWave = sin(p.y * 7.5 + uTime * 1.45 + aSeed * 0.8);
    float twist = thinking * (0.12 + uActivity * 0.16) * (p.y + thinkWave * 0.18);
    p.xz = rotate2d(twist) * p.xz;
    p += direction * thinkWave * 0.025 * thinking;

    // Speech is a dedicated envelope. Presented words push packets through the shell.
    float speechPacket = sin(radius * 13.0 - uTime * 4.8 + aSeed * 2.1 + aLayer * 0.8);
    speechPacket = smoothstep(0.05, 0.96, speechPacket * 0.5 + 0.5);
    p += direction * speechPacket * uSpeech * speaking * 0.095;
    p += direction * uSpeech * speaking * 0.022;

    vec3 glitch = vec3(
      sin(uTime * 12.0 + aSeed * 41.0),
      cos(uTime * 10.0 + aSeed * 29.0),
      sin(uTime * 13.0 + aSeed * 37.0)
    );
    p += glitch * error * 0.025;

    vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    float perspective = 82.0 / max(1.0, -mvPosition.z);
    float pointScale = 0.26 + aSize * 0.34 + uActivity * 0.08 + uSpeech * speaking * 0.26;
    gl_PointSize = clamp(pointScale * perspective, 1.25, 10.0);

    float stateEnergy =
      listening * abs(listenRipple) * 0.08 +
      thinking * abs(thinkWave) * 0.16 +
      speaking * speechPacket * uSpeech * 0.58 +
      error * 0.32;

    vEnergy = clamp(0.24 + uActivity * 0.38 + stateEnergy + aSize * 0.12, 0.0, 1.0);
    vSeed = aSeed;
    vLayer = aLayer;
  }
`;

const particleFragment = /* glsl */ `
  precision highp float;

  uniform float uSpeech;
  uniform float uMode;

  varying float vEnergy;
  varying float vSeed;
  varying float vLayer;

  void main() {
    vec2 p = gl_PointCoord - 0.5;
    float d = length(p);
    if (d > 0.5) discard;

    float core = 1.0 - smoothstep(0.04, 0.14, d);
    float body = 1.0 - smoothstep(0.10, 0.29, d);
    float halo = 1.0 - smoothstep(0.20, 0.5, d);

    float alpha = core * 0.78 + body * 0.32 + halo * 0.085;
    alpha *= 0.30 + vEnergy * 0.70;

    vec3 amber = vec3(0.58, 0.39, 0.10);
    vec3 gold = vec3(0.92, 0.69, 0.22);
    vec3 ivory = vec3(0.97, 0.92, 0.77);
    vec3 errorColor = vec3(0.82, 0.28, 0.18);

    float sparkle = smoothstep(0.68, 1.0, vEnergy) * fract(vSeed * 19.17 + vLayer * 0.43);
    float bright = clamp(vEnergy * 0.78 + core * 0.16 + sparkle * 0.18 + uSpeech * 0.08, 0.0, 1.0);
    vec3 color = mix(amber, gold, smoothstep(0.12, 0.70, bright));
    color = mix(color, ivory, smoothstep(0.68, 1.0, bright));

    float error = 1.0 - smoothstep(0.16, 0.66, abs(uMode - 4.0));
    color = mix(color, errorColor, error * 0.62);

    gl_FragColor = vec4(color, alpha);
  }
`;

export type ParticleCloudFrame = {
  time: number;
  activity: number;
  speech: number;
  mode: number;
  dt: number;
};

export class AgentParticleCloud {
  readonly points: THREE.Points;

  private readonly geometry: THREE.BufferGeometry;
  private readonly material: THREE.ShaderMaterial;
  private rotationSpeed = 0.035;

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
        uMode: { value: 0 },
      },
    });

    this.points = new THREE.Points(this.geometry, this.material);
    this.points.frustumCulled = false;
  }

  update(frame: ParticleCloudFrame): void {
    this.material.uniforms.uTime.value = frame.time;
    this.material.uniforms.uActivity.value = frame.activity;
    this.material.uniforms.uSpeech.value = frame.speech;
    this.material.uniforms.uMode.value = frame.mode;

    const thinking = 1 - Math.min(1, Math.abs(frame.mode - 2));
    const speaking = 1 - Math.min(1, Math.abs(frame.mode - 3));
    const targetRotation = 0.028 + thinking * 0.070 + speaking * 0.018;
    this.rotationSpeed += (targetRotation - this.rotationSpeed) * (1 - Math.exp(-3.0 * frame.dt));
    this.points.rotation.y += this.rotationSpeed * frame.dt;
    this.points.rotation.x = Math.sin(frame.time * 0.13) * 0.055;

    const speechScale = 1 + frame.speech * speaking * 0.032;
    this.points.scale.setScalar(speechScale);
  }

  dispose(): void {
    this.geometry.dispose();
    this.material.dispose();
  }
}
