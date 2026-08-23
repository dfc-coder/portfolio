import { gsap } from "../motion/gsap";

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const smoother = (value: number) => {
  const x = clamp(value, 0, 1);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const NAVIGATION_COVER_SECONDS = 0.9;
const NAVIGATION_HOLD_SECONDS = 0.02;
const NAVIGATION_REVEAL_SECONDS = 0.98;
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
  vec2 uv = gl_FragCoord.xy / uResolution.xy;
  float aspect = uResolution.x / max(uResolution.y, 1.0);

  vec2 origin = vec2(0.5 + uDirection * 0.012, 0.5);
  vec2 p = (uv - origin) * vec2(aspect, 1.0);
  float radial = length(p);
  float angle = atan(p.y, p.x);
  float time = uTime * 0.045;

  float coarse = fbm3(p * 3.15 + vec2(time, -time * 0.72));
  float detail = fbm3(p * 8.4 - vec2(time * 1.23, time * 0.81));

  float tornLobes =
    sin(angle * 8.0 + coarse * 6.2) * 0.038 +
    sin(angle * 17.0 - detail * 7.0) * 0.018;

  float displacement =
    (coarse - 0.5) * 0.255 +
    (detail - 0.5) * 0.078 +
    tornLobes;

  float maximumRadius = length(vec2(aspect * 0.58, 0.62)) + 0.36;
  float burnRadius = mix(-0.17, maximumRadius, uProgress);
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

  float alpha = material;
  alpha = max(alpha, charBand * 0.88);
  alpha = max(alpha, fleckZone * 0.62);
  alpha = clamp(alpha, 0.0, 1.0);

  gl_FragColor = vec4(color, alpha);
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
    console.error("[section-transition] shader compile failed", gl.getShaderInfoLog(shader));
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
    premultipliedAlpha: true,
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
    console.error("[section-transition] program link failed", gl.getProgramInfoLog(program));
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
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

  let timeline: gsap.core.Timeline | null = null;
  let active = false;
  let currentDirection = 1;
  const transitionState = { progress: 0 };

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
    transitionState.progress = 0;
    canvas.classList.remove("is-active");
    document.documentElement.classList.remove("is-section-transitioning");
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
  };

  const run: NavigationTransition = (commit, direction) => {
    if (active) return;

    active = true;
    currentDirection = direction < 0 ? -1 : 1;
    transitionState.progress = 0;
    resize();
    canvas.classList.add("is-active");
    document.documentElement.classList.add("is-section-transitioning");
    draw(0);

    timeline?.kill();
    timeline = gsap.timeline({
      defaults: { overwrite: true },
      onComplete: finish,
      onInterrupt: finish,
    });

    timeline
      .to(transitionState, {
        progress: 1,
        duration: NAVIGATION_COVER_SECONDS,
        ease: "none",
        onUpdate: () => draw(smoother(transitionState.progress)),
      })
      .add(() => {
        draw(1);
        commit();
      })
      .to({}, { duration: NAVIGATION_HOLD_SECONDS })
      .to(transitionState, {
        progress: 0,
        duration: NAVIGATION_REVEAL_SECONDS,
        ease: "none",
        onUpdate: () => draw(smoother(transitionState.progress)),
      });
  };

  navigationTransition = run;
  addEventListener("resize", resize, { passive: true });
  resize();

  return {
    destroy: () => {
      timeline?.kill();
      timeline = null;
      active = false;
      navigationTransition = null;
      removeEventListener("resize", resize);
      document.documentElement.classList.remove("is-section-transitioning");
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
