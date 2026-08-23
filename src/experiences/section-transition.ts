import { gsap } from "../motion/gsap";

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const NAVIGATION_SECONDS = 1.42;
const COMMIT_PROGRESS = 0.13;
const MAX_TRANSITION_PIXELS = 1_250_000;

type NavigationCommit = () => void;
type NavigationTransition = (commit: NavigationCommit, direction: number) => void;

let navigationTransition: NavigationTransition | null = null;

const vertexShader = `
attribute vec2 aPosition;

void main() {
  gl_Position = vec4(aPosition, 0.0, 1.0);
}
`;

/**
 * Single-pass centre-out burn transition.
 *
 * The previous implementation had two separate motions: cover the current
 * section completely, reset the radial front, then reveal the destination.
 * On this dark portfolio that read as a hard cut to black followed by a second
 * animation. Here progress is monotonic for the whole transition. A dark paper
 * veil settles in during the first part, navigation commits under that veil,
 * and the same burnt aperture keeps expanding from the centre to the edges.
 */
const fragmentShader = `
precision mediump float;

uniform vec2 uResolution;
uniform float uProgress;
uniform float uDirection;
uniform float uTime;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);

  return mix(
    mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
    u.y
  );
}

float fbm(vec2 p) {
  float value = 0.0;
  value += noise(p) * 0.50;
  p = mat2(0.80, -0.60, 0.60, 0.80) * p * 2.02 + vec2(5.2, 1.7);
  value += noise(p) * 0.27;
  p = mat2(0.80, -0.60, 0.60, 0.80) * p * 2.03 + vec2(2.9, 7.4);
  value += noise(p) * 0.15;
  p = mat2(0.80, -0.60, 0.60, 0.80) * p * 2.01 + vec2(8.1, 3.6);
  value += noise(p) * 0.08;
  return value;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution.xy;
  float aspect = uResolution.x / max(uResolution.y, 1.0);
  vec2 p = (uv - 0.5) * vec2(aspect, 1.0);

  float maximumRadius = length(vec2(aspect * 0.5, 0.5));
  float radial = length(p) / max(maximumRadius, 0.0001);
  float angle = atan(p.y, p.x);
  float t = clamp(uProgress, 0.0, 1.0);

  // The material field is intentionally almost static. The frontier should
  // consume a fixed paper texture rather than wobble like liquid as it grows.
  float drift = uTime * 0.004 * uDirection;
  vec2 base = p * 3.0;
  float warpX = fbm(base * 0.92 + vec2(drift, -drift * 0.45));
  float warpY = fbm(base * 0.92 + vec2(6.4 - drift * 0.30, 2.8 + drift * 0.22));
  vec2 warped = base + (vec2(warpX, warpY) - 0.5) * 1.30;

  float macroNoise = fbm(warped * 0.72 + vec2(1.7, 4.1));
  float mediumNoise = fbm(warped * 1.72 + vec2(7.3, 2.2));
  float fineNoise = noise(warped * 5.8 + vec2(4.9, 8.6));

  float lobes =
    sin(angle * 5.0 + macroNoise * 5.0) * 0.034 +
    sin(angle * 11.0 - mediumNoise * 5.7) * 0.018 +
    sin(angle * 23.0 + fineNoise * 3.4) * 0.006;

  // Keep irregularity stable for most of the travel. Previously its amplitude
  // grew and collapsed with progress, which made the outline visibly pulse.
  float irregularityIn = smoothstep(0.015, 0.10, t);
  float irregularity = irregularityIn * (
    (macroNoise - 0.5) * 0.148 +
    (mediumNoise - 0.5) * 0.068 +
    (fineNoise - 0.5) * 0.022 +
    lobes
  );

  // One frontier for the entire navigation. No midpoint reset.
  float frontier = mix(-0.055, 1.085, t);
  float signedDistance = radial - frontier - irregularity;

  float feather = 0.012;
  float holeMask = 1.0 - smoothstep(-feather, feather, signedDistance);

  // The veil fades in smoothly before the DOM navigation commit. It never
  // becomes perfectly opaque, avoiding the one-frame black slab visible in the
  // previous version. The expanding hole then reveals the destination beneath.
  float veil = smoothstep(0.0, 0.115, t) * 0.965;
  float coreAlpha = (1.0 - holeMask) * veil;

  float edgeDistance = abs(signedDistance);
  float edgeLife =
    smoothstep(0.012, 0.075, t) *
    (1.0 - smoothstep(0.94, 1.0, t));

  float charBand = (1.0 - smoothstep(0.009, 0.052, edgeDistance)) * edgeLife;
  float emberBand = (1.0 - smoothstep(0.003, 0.024, edgeDistance)) * edgeLife;
  float hotLine = (1.0 - smoothstep(0.000, 0.008, edgeDistance)) * edgeLife;

  float flecks = noise(warped * 8.5 + vec2(2.4, 6.8));
  float charVariation = 0.78 + flecks * 0.22;
  float emberVariation = 0.70 + mediumNoise * 0.30;

  vec3 soot = vec3(0.014, 0.012, 0.011);
  vec3 charBrown = vec3(0.165, 0.050, 0.022);
  vec3 ember = vec3(0.78, 0.205, 0.070);
  vec3 hotCopper = vec3(1.00, 0.515, 0.175);

  vec3 color = soot;
  color = mix(color, charBrown, charBand * 0.84 * charVariation);
  color = mix(color, ember, emberBand * 0.82 * emberVariation);
  color = mix(color, hotCopper, hotLine * 0.36);

  float edgeAlpha = max(charBand * 0.64, emberBand * 0.80);
  float alpha = max(coreAlpha, edgeAlpha);

  gl_FragColor = vec4(color, clamp(alpha, 0.0, 1.0));
}
`;

const compileShader = (
  gl: WebGLRenderingContext,
  type: number,
  source: string,
) => {
  const shader = gl.createShader(type);
  if (!shader) return null;

  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error(
      "[section-transition] shader compile failed",
      gl.getShaderInfoLog(shader),
    );
    gl.deleteShader(shader);
    return null;
  }

  return shader;
};

export const mountSectionTransition = (_portfolio: HTMLElement) => {
  document.querySelector(".ref-navigation-transition")?.remove();

  const canvas = document.createElement("canvas");
  canvas.className = "ref-navigation-transition";
  canvas.setAttribute("aria-hidden", "true");
  document.body.append(canvas);

  const gl = canvas.getContext("webgl", {
    alpha: true,
    antialias: false,
    depth: false,
    stencil: false,
    premultipliedAlpha: false,
    powerPreference: "high-performance",
  });

  if (!gl) {
    canvas.remove();
    navigationTransition = null;
    return null;
  }

  const vertex = compileShader(gl, gl.VERTEX_SHADER, vertexShader);
  const fragment = compileShader(gl, gl.FRAGMENT_SHADER, fragmentShader);
  const program = vertex && fragment ? gl.createProgram() : null;

  if (!vertex || !fragment || !program) {
    vertex && gl.deleteShader(vertex);
    fragment && gl.deleteShader(fragment);
    canvas.remove();
    navigationTransition = null;
    return null;
  }

  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error(
      "[section-transition] program link failed",
      gl.getProgramInfoLog(program),
    );
    gl.deleteProgram(program);
    canvas.remove();
    navigationTransition = null;
    return null;
  }

  const positionLocation = gl.getAttribLocation(program, "aPosition");
  const resolutionLocation = gl.getUniformLocation(program, "uResolution");
  const progressLocation = gl.getUniformLocation(program, "uProgress");
  const directionLocation = gl.getUniformLocation(program, "uDirection");
  const timeLocation = gl.getUniformLocation(program, "uTime");
  const buffer = gl.createBuffer();

  if (!buffer || positionLocation < 0) {
    buffer && gl.deleteBuffer(buffer);
    gl.deleteProgram(program);
    canvas.remove();
    navigationTransition = null;
    return null;
  }

  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
    gl.STATIC_DRAW,
  );
  gl.useProgram(program);
  gl.enableVertexAttribArray(positionLocation);
  gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

  let timeline: ReturnType<typeof gsap.timeline> | null = null;
  let active = false;
  let currentDirection = 1;
  const state = { progress: 0 };

  const resize = () => {
    const cssWidth = Math.max(1, innerWidth);
    const cssHeight = Math.max(1, innerHeight);
    const pixelBudgetScale = Math.sqrt(
      MAX_TRANSITION_PIXELS / (cssWidth * cssHeight),
    );
    const scale = Math.min(devicePixelRatio || 1, pixelBudgetScale, 1);
    const width = Math.max(1, Math.round(cssWidth * scale));
    const height = Math.max(1, Math.round(cssHeight * scale));

    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }

    gl.viewport(0, 0, width, height);
  };

  const draw = (progress: number) => {
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(program);
    gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
    gl.uniform1f(progressLocation, clamp(progress, 0, 1));
    gl.uniform1f(directionLocation, currentDirection);
    gl.uniform1f(timeLocation, performance.now() * 0.001);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
  };

  const finish = () => {
    active = false;
    state.progress = 0;
    canvas.classList.remove("is-active");
    document.documentElement.classList.remove("is-section-transitioning");
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
  };

  const run: NavigationTransition = (commit, direction) => {
    if (active) return;

    active = true;
    currentDirection = direction < 0 ? -1 : 1;
    state.progress = 0;
    resize();
    canvas.classList.add("is-active");
    document.documentElement.classList.add("is-section-transitioning");
    draw(0);

    let committed = false;
    timeline?.kill();
    timeline = gsap.timeline({
      defaults: { overwrite: true },
      onComplete: finish,
      onInterrupt: finish,
    });

    timeline.to(state, {
      progress: 1,
      duration: NAVIGATION_SECONDS,
      ease: "sine.inOut",
      onUpdate: () => {
        if (!committed && state.progress >= COMMIT_PROGRESS) {
          committed = true;
          commit();
        }
        draw(state.progress);
      },
    });
  };

  navigationTransition = run;
  addEventListener("resize", resize, { passive: true });
  resize();

  return {
    destroy: () => {
      timeline?.kill();
      timeline = null;
      navigationTransition = null;
      removeEventListener("resize", resize);
      finish();
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      canvas.remove();
    },
  };
};

export const transitionSectionNavigation = (
  commit: NavigationCommit,
  direction = 1,
) => {
  if (
    !navigationTransition ||
    matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    commit();
    return;
  }

  navigationTransition(commit, direction);
};
