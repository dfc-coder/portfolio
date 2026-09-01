// Subtle internal flow for the particle orb. The point cloud is the visible body;
// this layer only supplies continuous circulation, caustics and a restrained glass rim.

export const agentLiquidVertex = /* glsl */ `
  varying vec2 vUv;

  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position.xy * 1.20, position.z, 1.0);
  }
`;

export const agentLiquidFragment = /* glsl */ `
  precision highp float;

  uniform float uTime;
  uniform float uActivity;
  uniform float uSpeech;
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

  float ridge(float value, float power) {
    float r = 1.0 - abs(value * 2.0 - 1.0);
    return pow(clamp(r, 0.0, 1.0), power);
  }

  vec2 rotate2(vec2 p, float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return mat2(c, -s, s, c) * p;
  }

  float modeMask(float mode) {
    return 1.0 - smoothstep(0.14, 0.70, abs(uMode - mode));
  }

  float fluidValue(vec2 p, float t, float warp, float sharpness, float ridgeAmt) {
    vec2 q = rotate2(p * 1.20, sin(t * 0.13) * 0.12);
    float driftA = fbm(q * 1.18 + vec2(t * 0.16, -t * 0.11));
    float driftB = fbm(rotate2(q, 1.37) * 1.34 + vec2(-t * 0.12, t * 0.15));

    q += vec2(driftA - 0.5, driftB - 0.5) * (0.42 + warp * 0.07);
    float body = fbm(q * 1.45 + vec2(driftB * 0.64, driftA * 0.80));
    float ribbons = ridge(sin(q.x * 2.6 + q.y * 2.0 + t * 0.48) * 0.5 + 0.5, sharpness);
    float folds = ridge(fbm(q * 2.15 + vec2(t * 0.04, -t * 0.07)), 0.9 + sharpness * 0.22);

    return clamp(
      body * 0.56 +
      driftA * 0.13 +
      ribbons * (0.15 + ridgeAmt * 0.11) +
      folds * ridgeAmt * 0.18,
      0.0,
      1.0
    );
  }

  void main() {
    vec2 p = (vUv - 0.5) * 2.0;
    float r = length(p);
    float angle = atan(p.y, p.x);

    float listening = modeMask(1.0);
    float thinking = modeMask(2.0);
    float speaking = modeMask(3.0);
    float error = modeMask(4.0);

    // The flow never freezes. State changes alter character, while speech adds energy.
    float speed = 0.36 + listening * 0.05 + thinking * 0.28 + speaking * 0.06;
    float t = uTime * speed;

    vec2 pointer = (uPointer - 0.5) * 2.0;
    pointer.y *= -1.0;
    float pointerInfluence = exp(-length(pointer - p) * 2.6) * listening;

    float limbA = fbm(vec2(cos(angle), sin(angle)) * 2.1 + vec2(t * 0.07, -t * 0.05));
    float contour = 0.71 + (limbA - 0.5) * (0.026 + thinking * 0.014);
    contour += sin(angle * 3.0 + t * 0.42) * 0.005;
    contour += uSpeech * speaking * 0.012;

    float signedDistance = r - contour;
    float inside = 1.0 - smoothstep(-0.014, 0.014, signedDistance);
    if (inside < 0.001 && signedDistance > 0.08) discard;

    float normalizedRadius = clamp(r / max(contour, 0.001), 0.0, 1.0);
    float depth = sqrt(max(1.0 - normalizedRadius * normalizedRadius, 0.0));
    vec2 normal2 = r > 0.0001 ? p / r : vec2(0.0, 1.0);

    float warp = 3.0 + thinking * 0.72 + uSpeech * speaking * 0.28;
    float sharpness = 1.25 + thinking * 0.28;
    float ridgeAmt = 0.48 + thinking * 0.10 + uSpeech * speaking * 0.08;

    float lens = pow(1.0 - depth, 1.45);
    float refractStrength = lens * (0.055 + uSpeech * speaking * 0.018);
    vec2 fluidP = p / max(contour, 0.001);
    fluidP -= normal2 * refractStrength;
    fluidP += (pointer - p) * pointerInfluence * 0.012;

    float value = fluidValue(fluidP, t, warp, sharpness, ridgeAmt);
    float caustic = ridge(
      sin(fluidP.y * 3.2 + sin(fluidP.x * 2.3 - t * 0.72) + t * 0.31) * 0.5 + 0.5,
      3.4
    );

    float chroma = lens * 0.012;
    float redValue = fluidValue(fluidP + normal2 * chroma, t, warp, sharpness, ridgeAmt);
    float blueValue = fluidValue(fluidP - normal2 * chroma, t, warp, sharpness, ridgeAmt);

    vec3 darkAmber = vec3(0.18, 0.105, 0.025);
    vec3 gold = vec3(0.78, 0.48, 0.09);
    vec3 hotGold = vec3(1.0, 0.73, 0.24);
    vec3 ivory = vec3(0.98, 0.91, 0.72);

    vec3 base = mix(darkAmber, gold, smoothstep(0.22, 0.72, value));
    base = mix(base, hotGold, smoothstep(0.66, 0.96, value));
    base.r += (redValue - value) * 0.10;
    base.b += (blueValue - value) * 0.05;
    base = mix(base, ivory, caustic * (0.10 + uSpeech * speaking * 0.10));

    float rim = pow(1.0 - depth, 2.5);
    vec3 shellMid = vec3(0.89, 0.60, 0.16);
    vec3 shellEdge = vec3(1.0, 0.78, 0.28);
    base += shellMid * rim * 0.10;
    base += shellEdge * rim * rim * (0.12 + uSpeech * speaking * 0.09);

    float listeningWave = exp(-abs(fluidP.y - sin(fluidP.x * 3.0 - t * 1.1) * 0.08) * 17.0);
    float speakingWave = exp(-abs(fluidP.y - sin(fluidP.x * 3.6 - t * 0.45) * 0.10) * 15.0);
    base += ivory * listeningWave * listening * 0.025;
    base += ivory * speakingWave * speaking * uSpeech * 0.16;
    base = mix(base, vec3(0.82, 0.22, 0.15), error * 0.38);

    // The liquid is an internal atmosphere, not an opaque ball.
    float alpha = inside * (0.055 + value * 0.075 + caustic * 0.055);
    alpha += rim * inside * 0.055;
    alpha += speaking * uSpeech * inside * 0.035;

    float outerGlow = exp(-max(signedDistance, 0.0) * 42.0) * (1.0 - inside);
    alpha = max(alpha, outerGlow * 0.055);
    base += shellEdge * outerGlow * 0.12;

    gl_FragColor = vec4(clamp(base, 0.0, 1.0), clamp(alpha, 0.0, 0.28));
  }
`;