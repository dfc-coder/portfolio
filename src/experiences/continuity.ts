const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const damp = (current: number, target: number, response: number, dt: number) =>
  current + (target - current) * (1 - Math.exp(-response * dt));

const easeInOutSine = (value: number) =>
  -(Math.cos(Math.PI * clamp(value, 0, 1)) - 1) / 2;

const CURSOR_INTERACTIVE = "button, a, input, textarea, select, [data-cursor]";
const NAVIGATION_COVER_MS = 780;
const NAVIGATION_HOLD_MS = 110;
const NAVIGATION_REVEAL_MS = 840;

type CursorState = "idle" | "hover" | "press" | "text";
type NavigationCommit = () => void;
type NavigationTransition = (commit: NavigationCommit, direction: number) => void;

let navigationTransition: NavigationTransition | null = null;

const cursorStateFor = (element: Element | null): CursorState => {
  if (!element) return "idle";
  return element.matches("input, textarea") ? "text" : "hover";
};

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

float fbm(vec2 p) {
  float value = 0.0;
  float amplitude = 0.5;
  mat2 rotation = mat2(0.80, -0.60, 0.60, 0.80);

  for (int octave = 0; octave < 5; octave++) {
    value += amplitude * noise(p);
    p = rotation * p * 2.03 + vec2(13.7, 9.2);
    amplitude *= 0.5;
  }

  return value;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution.xy;
  float aspect = uResolution.x / max(uResolution.y, 1.0);

  // The transition grows from one irregular nucleus instead of sweeping
  // across the viewport. Direction only biases the nucleus very slightly.
  vec2 origin = vec2(0.5 + uDirection * 0.025, 0.5);
  vec2 p = (uv - origin) * vec2(aspect, 1.0);
  float radius = length(p);
  float angle = atan(p.y, p.x);

  float coarse = fbm(p * 3.25 + vec2(uTime * 0.030, -uTime * 0.025));
  float medium = fbm(p * 7.80 - vec2(uTime * 0.038, uTime * 0.021));
  float filament =
    sin(angle * 11.0 + coarse * 7.0 + uTime * 0.18) * 0.024 +
    sin(angle * 23.0 - medium * 8.0) * 0.012;

  float field =
    radius +
    (coarse - 0.5) * 0.22 +
    (medium - 0.5) * 0.065 +
    filament;

  bool covering = uProgress <= 0.5;
  float localProgress = covering
    ? uProgress * 2.0
    : (uProgress - 0.5) * 2.0;
  float growth = localProgress * localProgress * (3.0 - 2.0 * localProgress);

  // Dynamic maximum guarantees complete coverage on wide viewports while
  // keeping the first visible nucleus compact.
  float maximumRadius = length(vec2(aspect * 0.58, 0.62)) + 0.26;
  float threshold = mix(-0.17, maximumRadius, growth);
  float edgeWidth = mix(0.052, 0.028, growth);
  float inside = 1.0 - smoothstep(
    threshold - edgeWidth,
    threshold + edgeWidth,
    field
  );

  // Cover: organic matter grows from the centre.
  // Reveal: a transparent hole grows from the same centre, rebuilding the
  // destination without ever exposing the physical scroll jump.
  float alpha = covering ? inside : 1.0 - inside;
  float edge = 1.0 - smoothstep(0.0, 0.074, abs(field - threshold));

  float debrisNoise = noise(
    p * 38.0 +
    vec2(uTime * 0.11, -uTime * 0.08) +
    coarse * 4.0
  );
  float debris = edge * smoothstep(0.57, 0.94, debrisNoise);

  vec3 ink = vec3(0.027, 0.028, 0.026);
  vec3 paper = vec3(0.933, 0.914, 0.886);
  vec3 accent = vec3(0.773, 0.404, 0.282);
  vec3 edgeTone = mix(paper, accent, 0.54 + coarse * 0.22);
  vec3 color = mix(
    ink,
    edgeTone,
    clamp(edge * 0.72 + debris * 0.24, 0.0, 1.0)
  );

  float surfaceGrain = noise(gl_FragCoord.xy * 0.14 + uTime * 3.0) - 0.5;
  color += surfaceGrain * 0.012;
  alpha = clamp(max(alpha, edge * (0.10 + debris * 0.34)), 0.0, 1.0);

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

const createNavigationTransition = (portfolio: HTMLElement) => {
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
    return null;
  }

  const vertex = compileShader(gl, gl.VERTEX_SHADER, vertexShader);
  const fragment = compileShader(gl, gl.FRAGMENT_SHADER, fragmentShader);
  const program = vertex && fragment ? gl.createProgram() : null;

  if (!vertex || !fragment || !program) {
    vertex && gl.deleteShader(vertex);
    fragment && gl.deleteShader(fragment);
    canvas.remove();
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

  const draw = (progress: number, direction: number, time: number) => {
    resize();
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(program);
    gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
    gl.uniform1f(progressLocation, progress);
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
      let progress = 0;

      if (elapsed < NAVIGATION_COVER_MS) {
        const cover = easeInOutSine(elapsed / NAVIGATION_COVER_MS);
        progress = 0.5 * cover;
      } else {
        if (!committed) {
          // The destination is committed only while the erosion mask is fully
          // opaque. The user never sees the physical scroll position change.
          committed = true;
          draw(0.5, normalizedDirection, now);
          commit();
        }

        if (elapsed < NAVIGATION_COVER_MS + NAVIGATION_HOLD_MS) {
          progress = 0.5;
        } else {
          const revealElapsed =
            elapsed - NAVIGATION_COVER_MS - NAVIGATION_HOLD_MS;
          const reveal = easeInOutSine(revealElapsed / NAVIGATION_REVEAL_MS);
          progress = 0.5 + reveal * 0.5;
        }
      }

      draw(progress, normalizedDirection, now);

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

  return {
    run,
    destroy: () => {
      cancelAnimationFrame(frame);
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

/**
 * Owns visual effects that intentionally survive chapter boundaries:
 * ambient pointer field, custom cursor and menu-driven section transition.
 */
export const mountVisualContinuity = () => {
  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const portfolio = document.querySelector<HTMLElement>(".ref-portfolio");
  if (!stage || !portfolio) return () => undefined;

  stage.querySelector(".ref-global-pointer-light")?.remove();
  portfolio.querySelector(".ref-cursor")?.remove();
  portfolio.querySelector(".ref-cursor-ring")?.remove();
  portfolio.querySelector(".ref-navigation-transition")?.remove();

  const light = document.createElement("div");
  light.className = "ref-global-pointer-light";
  light.setAttribute("aria-hidden", "true");
  stage.append(light);

  const sectionTransition = createNavigationTransition(portfolio);
  navigationTransition = sectionTransition?.run ?? null;

  const cursorEnabled = matchMedia(
    "(pointer: fine) and (prefers-reduced-motion: no-preference)",
  ).matches;
  const cursor = cursorEnabled ? document.createElement("div") : null;
  const ring = cursorEnabled ? document.createElement("div") : null;

  if (cursor && ring) {
    cursor.className = "ref-cursor";
    ring.className = "ref-cursor-ring";
    cursor.setAttribute("aria-hidden", "true");
    ring.setAttribute("aria-hidden", "true");
    portfolio.append(cursor, ring);
    portfolio.classList.add("has-cursor");
  }

  let frame = 0;
  let currentX = 47;
  let currentY = 47;
  let targetX = currentX;
  let targetY = currentY;
  let currentVelocity = 0;
  let targetVelocity = 0;
  let pointerX = innerWidth * 0.5;
  let pointerY = innerHeight * 0.44;
  let lastX = pointerX;
  let lastY = pointerY;
  let ringX = pointerX;
  let ringY = pointerY;
  let cursorSeen = false;
  let cursorState: CursorState = "idle";
  let lastFrameTime = performance.now();

  const setCursorState = (state: CursorState) => {
    cursorState = state;
    if (cursor) cursor.dataset.state = state;
    if (ring) ring.dataset.state = state;
  };

  const onPointerMove = (event: PointerEvent) => {
    pointerX = event.clientX;
    pointerY = event.clientY;
    targetX = clamp((pointerX / innerWidth) * 100 - 1.4, -4, 104);
    targetY = clamp((pointerY / innerHeight) * 100 + 1.6, -4, 104);

    const dx = pointerX - lastX;
    const dy = pointerY - lastY;
    targetVelocity = clamp(Math.hypot(dx, dy) / 44, 0, 1);
    lastX = pointerX;
    lastY = pointerY;

    if (!cursor || !ring) return;

    cursor.style.transform = `translate3d(${pointerX}px, ${pointerY}px, 0)`;
    if (!cursorSeen) {
      cursorSeen = true;
      ringX = pointerX;
      ringY = pointerY;
      cursor.classList.add("is-on");
      ring.classList.add("is-on");
    }
  };

  const onPointerOver = (event: PointerEvent) => {
    if (!cursor) return;

    const interactive =
      (event.target as Element | null)?.closest(CURSOR_INTERACTIVE) ?? null;
    setCursorState(cursorStateFor(interactive));
  };

  const onPointerDown = () => {
    if (cursorState !== "text") setCursorState("press");
  };

  const onPointerUp = (event: PointerEvent) => {
    const interactive =
      (event.target as Element | null)?.closest(CURSOR_INTERACTIVE) ?? null;
    setCursorState(cursorStateFor(interactive));
  };

  const onPointerOut = (event: PointerEvent) => {
    if (event.relatedTarget || !cursor || !ring) return;

    cursorSeen = false;
    cursor.classList.remove("is-on");
    ring.classList.remove("is-on");
    targetVelocity = 0;
  };

  const render = (time: number) => {
    const dt = Math.min(0.05, Math.max(0.001, (time - lastFrameTime) / 1000));
    lastFrameTime = time;

    currentX = damp(currentX, targetX, 8.5, dt);
    currentY = damp(currentY, targetY, 8.5, dt);
    currentVelocity = damp(currentVelocity, targetVelocity, 10, dt);
    targetVelocity *= Math.exp(-8 * dt);

    stage.style.setProperty("--ref-pointer-x", `${currentX.toFixed(3)}%`);
    stage.style.setProperty("--ref-pointer-y", `${currentY.toFixed(3)}%`);
    stage.style.setProperty("--ref-pointer-velocity", currentVelocity.toFixed(4));

    if (ring) {
      ringX = damp(ringX, pointerX, 18, dt);
      ringY = damp(ringY, pointerY, 18, dt);
      ring.style.transform = `translate3d(${ringX}px, ${ringY}px, 0)`;
    }

    frame = requestAnimationFrame(render);
  };

  addEventListener("pointermove", onPointerMove, { passive: true });

  if (cursorEnabled) {
    addEventListener("pointerover", onPointerOver, { passive: true });
    addEventListener("pointerdown", onPointerDown, { passive: true });
    addEventListener("pointerup", onPointerUp, { passive: true });
    document.documentElement.addEventListener("pointerout", onPointerOut);
  }

  frame = requestAnimationFrame(render);

  return () => {
    cancelAnimationFrame(frame);
    removeEventListener("pointermove", onPointerMove);
    removeEventListener("pointerover", onPointerOver);
    removeEventListener("pointerdown", onPointerDown);
    removeEventListener("pointerup", onPointerUp);
    document.documentElement.removeEventListener("pointerout", onPointerOut);
    ["--ref-pointer-x", "--ref-pointer-y", "--ref-pointer-velocity"].forEach(
      (property) => stage.style.removeProperty(property),
    );
    navigationTransition = null;
    sectionTransition?.destroy();
    light.remove();
    cursor?.remove();
    ring?.remove();
    portfolio.classList.remove("has-cursor");
  };
};
