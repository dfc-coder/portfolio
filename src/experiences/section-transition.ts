const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const smoother = (value: number) => {
  const x = clamp(value, 0, 1);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const NAVIGATION_COVER_MS = 1120;
const NAVIGATION_HOLD_MS = 100;
const NAVIGATION_REVEAL_MS = 1180;

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
uniform float uCoverage;
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
  float amplitude = 0.5;
  mat2 rotation = mat2(0.80, -0.60, 0.60, 0.80);

  for (int octave = 0; octave < 5; octave++) {
    value += amplitude * noise(p);
    p = rotation * p * 2.04 + vec2(11.8, 7.3);
    amplitude *= 0.5;
  }

  return value;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution.xy;
  float aspect = uResolution.x / max(uResolution.y, 1.0);

  // AnimMasters-style material nucleus: one expanding organic mass rather
  // than a directional wipe. Direction only offsets the seed imperceptibly.
  vec2 origin = vec2(0.5 + uDirection * 0.018, 0.5);
  vec2 p = (uv - origin) * vec2(aspect, 1.0);
  float radial = length(p);
  float angle = atan(p.y, p.x);

  float slowTime = uTime * 0.055;
  float coarse = fbm(p * 2.75 + vec2(slowTime, -slowTime * 0.72));
  float medium = fbm(p * 6.80 - vec2(slowTime * 1.34, slowTime * 0.91));
  float fine = fbm(p * 15.5 + vec2(-slowTime * 1.9, slowTime * 1.3));

  float lobes =
    sin(angle * 7.0 + coarse * 5.8) * 0.035 +
    sin(angle * 13.0 - medium * 7.2) * 0.022 +
    sin(angle * 29.0 + fine * 5.0) * 0.010;

  float displacement =
    (coarse - 0.5) * 0.245 +
    (medium - 0.5) * 0.092 +
    (fine - 0.5) * 0.026 +
    lobes;

  float maximumRadius = length(vec2(aspect * 0.58, 0.62)) + 0.42;
  float materialRadius = mix(-0.16, maximumRadius, uCoverage);
  float signedDistance = radial - materialRadius - displacement;

  // A solid paper core with a broad torn cobalt rim recreates the reference:
  // thick material, irregular chunks and detached fragments instead of fire.
  float core = 1.0 - smoothstep(-0.018, 0.026, signedDistance);
  float rim = 1.0 - smoothstep(0.025, 0.135, abs(signedDistance));
  float innerPaper = 1.0 - smoothstep(-0.105, -0.026, signedDistance);

  float fragmentNoise = noise(
    p * 43.0 +
    vec2(uTime * 0.18, -uTime * 0.13) +
    medium * 5.0
  );
  float fragmentZone =
    smoothstep(0.018, 0.12, signedDistance) *
    (1.0 - smoothstep(0.12, 0.22, signedDistance));
  float fragments =
    fragmentZone *
    smoothstep(0.56, 0.88, fragmentNoise + (coarse - 0.5) * 0.18);

  vec3 paper = vec3(0.956, 0.949, 0.932);
  vec3 cobalt = vec3(0.055, 0.075, 0.92);
  vec3 deepCobalt = vec3(0.025, 0.035, 0.42);

  float tornMix = clamp(rim * 1.08 + fragments * 0.72, 0.0, 1.0);
  vec3 edgeColor = mix(deepCobalt, cobalt, 0.62 + medium * 0.38);
  vec3 color = mix(edgeColor, paper, innerPaper);
  color = mix(color, cobalt, fragments * 0.68);

  float pixelGrain = noise(gl_FragCoord.xy * 0.16 + uTime * 2.7) - 0.5;
  color += pixelGrain * 0.010;

  float alpha = max(core, rim * 0.96);
  alpha = max(alpha, fragments * 0.84);
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
    gl.deleteShader(shader);
    return null;
  }

  return shader;
};

export const mountSectionTransition = (portfolio: HTMLElement) => {
  portfolio.querySelector(".ref-navigation-transition")?.remove();

  const canvas = document.createElement("canvas");
  canvas.className = "ref-navigation-transition";
  canvas.setAttribute("aria-hidden", "true");
  portfolio.append(canvas);

  const gl = canvas.getContext("webgl", {
    alpha: true,
    antialias: false,
    depth: false,
    stencil: false,
    premultipliedAlpha: true,
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
    gl.deleteProgram(program);
    canvas.remove();
    navigationTransition = null;
    return null;
  }

  const positionLocation = gl.getAttribLocation(program, "aPosition");
  const resolutionLocation = gl.getUniformLocation(program, "uResolution");
  const coverageLocation = gl.getUniformLocation(program, "uCoverage");
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

  let frame = 0;
  let active = false;

  const resize = () => {
    const dpr = Math.min(devicePixelRatio || 1, 1.5);
    const width = Math.max(1, Math.round(innerWidth * dpr));
    const height = Math.max(1, Math.round(innerHeight * dpr));

    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }

    gl.viewport(0, 0, width, height);
  };

  const draw = (coverage: number, direction: number, time: number) => {
    resize();
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(program);
    gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
    gl.uniform1f(coverageLocation, clamp(coverage, 0, 1));
    gl.uniform1f(directionLocation, direction);
    gl.uniform1f(timeLocation, time * 0.001);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
  };

  const run: NavigationTransition = (commit, direction) => {
    if (active) return;

    active = true;
    canvas.classList.add("is-active");
    document.documentElement.classList.add("is-section-transitioning");

    const startedAt = performance.now();
    const normalizedDirection = direction < 0 ? -1 : 1;
    let committed = false;

    const render = (now: number) => {
      const elapsed = now - startedAt;
      let coverage = 0;

      if (elapsed < NAVIGATION_COVER_MS) {
        // OUT: the material grows from the nucleus until it absorbs the
        // complete current section, closely matching the reference loader.
        coverage = smoother(elapsed / NAVIGATION_COVER_MS);
      } else {
        if (!committed) {
          committed = true;
          draw(1, normalizedDirection, now);
          commit();
        }

        if (elapsed < NAVIGATION_COVER_MS + NAVIGATION_HOLD_MS) {
          coverage = 1;
        } else {
          // IN: the same material boundary contracts from the viewport edges
          // back into the nucleus. The destination therefore appears outside
          // first and closes inward, instead of playing a second OUT reveal.
          const revealElapsed =
            elapsed - NAVIGATION_COVER_MS - NAVIGATION_HOLD_MS;
          coverage = 1 - smoother(revealElapsed / NAVIGATION_REVEAL_MS);
        }
      }

      draw(coverage, normalizedDirection, now);

      if (
        elapsed <
        NAVIGATION_COVER_MS + NAVIGATION_HOLD_MS + NAVIGATION_REVEAL_MS
      ) {
        frame = requestAnimationFrame(render);
        return;
      }

      active = false;
      canvas.classList.remove("is-active");
      document.documentElement.classList.remove("is-section-transitioning");
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
    };

    frame = requestAnimationFrame(render);
  };

  navigationTransition = run;

  return {
    destroy: () => {
      cancelAnimationFrame(frame);
      active = false;
      navigationTransition = null;
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
