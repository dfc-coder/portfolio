const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const CURSOR_INTERACTIVE = "button, a, input, textarea, select, [data-cursor]";
type CursorState = "idle" | "hover" | "press" | "text";

const cursorStateFor = (element: Element | null): CursorState => {
  if (!element) return "idle";
  return element.matches("input, textarea") ? "text" : "hover";
};

/**
 * Owns the visual effects that intentionally survive chapter boundaries:
 * one ambient pointer field and, on fine pointers, one custom cursor.
 * Both share a single animation frame loop and a single pointer listener.
 */
export const mountVisualContinuity = () => {
  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const portfolio = document.querySelector<HTMLElement>(".ref-portfolio");
  if (!stage || !portfolio) return () => undefined;

  stage.querySelector(".ref-global-pointer-light")?.remove();
  portfolio.querySelector(".ref-cursor")?.remove();
  portfolio.querySelector(".ref-cursor-ring")?.remove();

  const light = document.createElement("div");
  light.className = "ref-global-pointer-light";
  light.setAttribute("aria-hidden", "true");
  stage.append(light);

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

  const setCursorState = (state: CursorState) => {
    cursorState = state;
    if (cursor) cursor.dataset.state = state;
    if (ring) ring.dataset.state = state;
  };

  const onPointerMove = (event: PointerEvent) => {
    pointerX = event.clientX;
    pointerY = event.clientY;
    targetX = clamp((pointerX / innerWidth) * 100 - 2.4, -4, 104);
    targetY = clamp((pointerY / innerHeight) * 100 + 2.8, -4, 104);

    const dx = pointerX - lastX;
    const dy = pointerY - lastY;
    targetVelocity = clamp(Math.hypot(dx, dy) / 46, 0, 1);
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

  const render = () => {
    currentX += (targetX - currentX) * .052;
    currentY += (targetY - currentY) * .044;
    currentVelocity += (targetVelocity - currentVelocity) * .07;
    targetVelocity *= .88;

    const x = `${currentX.toFixed(3)}%`;
    const y = `${currentY.toFixed(3)}%`;
    const velocity = currentVelocity.toFixed(4);
    stage.style.setProperty("--ref-pointer-x", x);
    stage.style.setProperty("--ref-pointer-y", y);
    stage.style.setProperty("--ref-pointer-velocity", velocity);

    if (ring) {
      ringX += (pointerX - ringX) * .16;
      ringY += (pointerY - ringY) * .16;
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
    light.remove();
    cursor?.remove();
    ring?.remove();
    portfolio.classList.remove("has-cursor");
  };
};
