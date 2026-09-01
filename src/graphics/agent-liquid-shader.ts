// Refractive liquid presence for the agent scene.
// Spatial model is independently implemented in GLSL after studying the public
// MIT-licensed Liquid Orb Editor by LerSent001. The important ideas retained are
// a continuously advected fluid field, a deformed analytic limb, refraction near
// the boundary, chromatic separation, caustic ribbons and a glass shell.

export const agentLiquidVertex = /* glsl */ `
  uniform float uActivity;
  uniform float uMode;
  varying vec2 vUv;

  void main() {
    vUv = uv;
    float speaking = 1.0 - smoothstep(0.18, 0.72, abs(uMode - 3.0));
    float speechEnergy = speaking * smoothstep(0.16, 0.72, uActivity);
    float breath = 1.0 + speechEnergy * 0.055;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position.xy * breath, position.z, 1.0);
  }
`;

export const agentLiquidFragment = /* glsl */ `
  precision highp float;

  uniform float uTime;
  uniform float uActivity;
  uniform float uMode;
  uniform vec2 uPointer;
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
    float amp = 0.52;
    mat2 turn = mat2(0.80, -0.60, 0.60, 0.80);

    for (int i = 0; i < 4; i++) {
      value += noise(p) * amp;
      p = turn * p * 2.03 + vec2(4.7, 8.3);
      amp *= 0.5;
    }

    return value;
  }

  float ridge(float v, float sharpness) {
    float r = 1.0 - abs(v * 2.0 - 1.0);
    return pow(clamp(r, 0.0, 1.0), sharpness);
  }

  vec2 rotate2(vec2 p, float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return mat2(c, -s, s, c) * p;
  }

  float modeMask(float mode) {
    return 1.0 - smoothstep(0.14, 0.70, abs(uMode - mode));
  }

  vec3 palette4(float t) {
    vec3 a = vec3(0.106, 0.063, 0.169);
    vec3 b = vec3(0.439, 0.337, 0.659);
    vec3 c = vec3(0.749, 0.647, 0.961);
    vec3 d = vec3(0.945, 0.910, 1.000);

    float x = clamp(t, 0.0, 1.0) * 3.0;
    if (x < 1.0) return mix(a, b, smoothstep(0.0, 1.0, x));
    if (x < 2.0) return mix(b, c, smoothstep(0.0, 1.0, x - 1.0));
    return mix(c, d, smoothstep(0.0, 1.0, x - 2.0));
  }

  float fluidValue(vec2 p, float t, float warp, float sharpness, float ridgeAmt) {
    vec2 q = rotate2(p * 1.32, 0.08 * sin(t * 0.17));

    float driftA = fbm(q * 1.16 + vec2(t * 0.052, -t * 0.078));
    float driftB = fbm(rotate2(q, 1.21) * 1.34 + vec2(-t * 0.064, t * 0.041));

    q += vec2(driftA - 0.5, driftB - 0.5) * (0.34 + warp * 0.105);

    float body = fbm(q * 1.42 + vec2(driftB * 0.82, driftA * 0.66));

    float ribbonPhase =
      q.y * (2.2 + warp * 0.11) +
      sin(q.x * 1.72 - t * 0.19) * 0.92 +
      sin((q.x + q.y) * 1.08 + t * 0.13) * 0.46;

    float ribbon = pow(
      clamp(1.0 - abs(sin(ribbonPhase)), 0.0, 1.0),
      0.82 + sharpness * 0.23
    );

    float fold = ridge(fbm(q * 2.05 + vec2(2.8, -t * 0.037)), 0.90 + sharpness * 0.32);

    return clamp(
      body * 0.50 +
      driftA * 0.16 +
      ribbon * (0.20 + ridgeAmt * 0.20) +
      fold * ridgeAmt * 0.18,
      0.0,
      1.0
    );
  }

  void main() {
    vec2 p = (vUv - 0.5) * 2.0;
    float r = length(p);
    float angle = atan(p.y, p.x);

    float idle = modeMask(0.0);
    float listening = modeMask(1.0);
    float thinking = modeMask(2.0);
    float speaking = modeMask(3.0);
    float error = modeMask(4.0);
    float speechEnergy = speaking * smoothstep(0.16, 0.72, uActivity);

    // Speaking no longer advances an autonomous animation at a high rate.
    // The visible energy is driven by the speech envelope instead.
    float speed =
      0.42 +
      listening * 0.08 +
      thinking * 0.42 +
      speaking * 0.02 +
      error * 0.18;
    float t = uTime * speed;

    vec2 pointer = (uPointer - 0.5) * 2.0;
    pointer.y *= -1.0;
    float pointerInfluence = exp(-length(pointer - p) * 2.25) * listening;

    vec2 direction = vec2(cos(angle), sin(angle));
    float limbA = fbm(direction * 1.55 + vec2(t * 0.055, -t * 0.040));
    float limbB = fbm(direction * 3.10 + vec2(-t * 0.031, t * 0.047));
    float deform = 0.048 + thinking * 0.028 + speaking * 0.008 + uActivity * 0.008;
    float contour =
      0.735 +
      (limbA - 0.5) * deform +
      (limbB - 0.5) * deform * 0.34 +
      sin(angle * 2.0 + t * 0.23) * 0.006;

    // Coherent speech deformation: each presented word expands the whole shell
    // and adds a low-frequency lobe instead of injecting more procedural noise.
    contour += speechEnergy * 0.035;
    contour += speechEnergy * sin(angle * 2.0 + 0.7) * 0.012;
    contour += pointerInfluence * 0.012;

    float signedDistance = r - contour;
    float edgeSoft = 0.012;
    float inside = 1.0 - smoothstep(-edgeSoft, edgeSoft, signedDistance);

    if (inside < 0.001 && signedDistance > 0.075) discard;

    float normalizedRadius = clamp(r / max(contour, 0.001), 0.0, 1.0);
    float depth = sqrt(max(1.0 - normalizedRadius * normalizedRadius, 0.0));
    vec2 normal2 = r > 0.0001 ? p / r : vec2(0.0, 1.0);

    float warp = 3.50 + listening * 0.18 + thinking * 0.68 + speechEnergy * 0.18;
    float sharpness = 2.70 + thinking * 0.36 + speechEnergy * 0.10;
    float ridgeAmt = 0.58 + thinking * 0.08 + speechEnergy * 0.08;

    float lens = pow(1.0 - depth, 1.35);
    float refractStrength = lens * (0.15 + speechEnergy * 0.065);
    vec2 fluidP = p / max(contour, 0.001);
    fluidP -= normal2 * refractStrength;
    fluidP += (pointer - p) * pointerInfluence * 0.018;

    float value = fluidValue(fluidP, t, warp, sharpness, ridgeAmt);

    float causticPhase =
      fluidP.y * (2.20 + warp * 0.11) +
      sin(fluidP.x * 1.72 - t * 0.19) * 0.92 +
      sin((fluidP.x + fluidP.y) * 1.08 + t * 0.13) * 0.46;
    float caustic = pow(clamp(1.0 - abs(sin(causticPhase)), 0.0, 1.0), 3.1);

    float chroma = lens * (0.030 + speechEnergy * 0.018);
    float redValue = fluidValue(fluidP + normal2 * chroma, t, warp, sharpness, ridgeAmt);
    float blueValue = fluidValue(fluidP - normal2 * chroma, t, warp, sharpness, ridgeAmt);

    vec3 base = palette4(value);
    vec3 redSample = palette4(redValue);
    vec3 blueSample = palette4(blueValue);
    vec3 color = vec3(redSample.r, base.g, blueSample.b);

    color = mix(color, vec3(0.945, 0.910, 1.0), caustic * (0.18 + ridgeAmt * 0.16));
    color *= 0.70 + depth * 0.30;

    float rim = pow(1.0 - depth, 2.4);
    float lightA = pow(max(dot(normal2, normalize(vec2(-0.62, 0.78))), 0.0), 10.0) * rim;
    float lightB = pow(max(dot(normal2, normalize(vec2(0.78, -0.62))), 0.0), 12.0) * rim;

    vec3 shellMid = vec3(0.851, 0.780, 1.000);
    vec3 shellEdge = vec3(0.710, 0.604, 0.910);
    vec3 shellInner = vec3(0.965, 0.941, 1.000);

    color = mix(color, shellMid, rim * (0.18 + speechEnergy * 0.12));
    color += shellInner * lightA * (0.22 + speechEnergy * 0.24);
    color += shellEdge * lightB * (0.16 + speechEnergy * 0.16);

    float listeningWave = exp(-abs(fluidP.y - sin(fluidP.x * 3.2 - t * 1.2) * 0.08) * 18.0);
    float speakingWave = exp(-abs(fluidP.y - sin(fluidP.x * 3.4) * 0.10) * 13.0);
    color += shellInner * listeningWave * listening * 0.045;
    color += shellInner * speakingWave * speechEnergy * 0.34;

    color = mix(color, vec3(0.88, 0.20, 0.16), error * (0.20 + caustic * 0.14));

    float outside = smoothstep(0.0, 0.055, max(signedDistance, 0.0));
    float glow = exp(-max(signedDistance, 0.0) * 38.0) * (1.0 - outside);
    vec3 glowColor = vec3(0.69, 0.55, 1.0);

    float alpha = inside * (0.74 + rim * 0.18 + speechEnergy * 0.08);
    alpha = max(alpha, glow * (0.13 + speechEnergy * 0.12));
    color += glowColor * glow * (0.08 + speechEnergy * 0.18);

    gl_FragColor = vec4(clamp(color, 0.0, 1.0), clamp(alpha, 0.0, 1.0));
  }
`;