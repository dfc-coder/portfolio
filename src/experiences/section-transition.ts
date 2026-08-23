import { gsap } from "../motion/gsap";

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const NAVIGATION_COVER_SECONDS = 0.74;
const NAVIGATION_HOLD_SECONDS = 0.025;
const NAVIGATION_REVEAL_SECONDS = 0.82;
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
 * Organic transition derived from the same masking idea used by
 * akella/webGLImageTransitions demo1: progress drives a threshold while noise
 * distorts only the moving frontier. The reference moves that threshold along
 * X; here the threshold is radial, so both cover and reveal travel from the
 * centre toward the viewport edges.
 *
 * uPhase = 0: opaque material grows centre -> outside, covering the old scene.
 * uPhase = 1: a transparent opening grows centre -> outside, revealing the new
 *             scene underneath.
 */
const fragmentShader = `
precision mediump float;

uniform vec2 uResolution;
uniform float uProgress;
uniform float uPhase;
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
  value += noise(p) * 0.55;
  p = mat2(0.80, -0.60, 0.60, 0.80) * p * 2.03 + vec2(7.1, 3.7);
  value += noise(p) * 0.29;
  p = mat2(0.80, -0.60, 0.60, 0.80) * p * 2.01 + vec2(4.3, 9.2);
  value += noise(p) * 0.16;
  return value;
}

float parabola(float x) {
  return 4.0 * x * (1.0 - x);
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution.xy;
  float aspect = uResolution.x / max(uResolution.y, 1.0);

  // Aspect-correct radial coordinates: circles remain circular on wide screens.
  vec2 p = (uv - 0.5) * vec2(aspect, 1.0);
  float maximumRadius = length(vec2(aspect * 0.5, 0.5));
  float radial = length(p) / max(maximumRadius, 0.0001);
  float angle = atan(p.y, p.x);

  // The direction only changes the organic drift. Navigation never becomes a
  // left/right wipe: the spatial transition is always centre -> outside.
  float drift = uTime * 0.055 * uDirection;
  float coarse = fbm(p * 4.25 + vec2(drift, -drift * 0.72));
  float detail = fbm(p * 10.8 - vec2(drift * 0.63, drift * 0.41));

  // Like the reference shader, roughness is strongest mid-transition and
  // collapses at both endpoints so progress 0 and 1 are deterministic.
  float activeWidth = parabola(uProgress);
  float lobes =
    sin(angle * 9.0 + coarse * 5.4) * 0.033 +
    sin(angle * 19.0 - detail * 6.7) * 0.014;
  float displacement = activeWidth * (
    (coarse - 0.5) * 0.205 +
    (detail - 0.5) * 0.082 +
    lobes
  );

  // Start safely before the centre and finish beyond every viewport corner.
  // This guarantees no stale pixels before/after the navigation commit.
  float frontier = mix(-0.105, 1.105, uProgress);
  float signedDistance = radial - frontier - displacement;
  float feather = mix(0.013, 0.006, activeWidth);
  float grownMask = 1.0 - smoothstep(-feather, feather, signedDistance);

  // Cover: material grows outward. Reveal: the same noisy radial front becomes
  // a transparent aperture, also growing outward, exposing the destination.
  float alpha = mix(grownMask, 1.0 - grownMask, uPhase);

  // Keep the transition material neutral. The visual character must come from
  // the torn/noisy boundary, not from a fire/ember colour treatment.
  vec3 material = vec3(0.020, 0.019, 0.018);
  gl_FragColor = vec4(material, clamp(alpha, 0.0, 1.0));
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
  const phaseLocation = gl.getUniformLocation(program, "uPhase");
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
  const state = { progress: 0, phase: 0 };

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

  const draw = (progress: number, phase: number) => {
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(program);
    gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
    gl.uniform1f(progressLocation, clamp(progress, 0, 1));
    gl.uniform1f(phaseLocation, clamp(phase, 0, 1));
    gl.uniform1f(directionLocation, currentDirection);
    gl.uniform1f(timeLocation, performance.now() * 0.001);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
  };

  const finish = () => {
    active = false;
    state.progress = 0;
    state.phase = 0;
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
    state.phase = 0;
    resize();
    canvas.classList.add("is-active");
    document.documentElement.classList.add("is-section-transitioning");
    draw(0, 0);

    timeline?.kill();
    timeline = gsap.timeline({
      defaults: { overwrite: true },
      onComplete: finish,
      onInterrupt: finish,
    });

    timeline
      .to(state, {
        progress: 1,
        duration: NAVIGATION_COVER_SECONDS,
        ease: "power2.out",
        onUpdate: () => draw(state.progress, 0),
      })
      .add(() => {
        // The old section is fully hidden here. Commit synchronously, then keep
        // a fully opaque frame before beginning the centre-out reveal.
        draw(1, 0);
        commit();
        state.progress = 0;
        state.phase = 1;
        draw(0, 1);
      })
      .to({}, { duration: NAVIGATION_HOLD_SECONDS })
      .to(state, {
        progress: 1,
        duration: NAVIGATION_REVEAL_SECONDS,
        ease: "power2.out",
        onUpdate: () => draw(state.progress, 1),
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
