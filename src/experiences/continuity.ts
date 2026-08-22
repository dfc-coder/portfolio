import { mountSectionTransition } from "./section-transition";

export { transitionSectionNavigation } from "./section-transition";

const damp = (current: number, target: number, response: number, dt: number) =>
  current + (target - current) * (1 - Math.exp(-response * dt));

const CURSOR_INTERACTIVE = "button, a, input, textarea, select, [data-cursor]";
type CursorState = "idle" | "hover" | "press" | "text";

const cursorStateFor = (element: Element | null): CursorState => {
  if (!element) return "idle";
  return element.matches("input, textarea") ? "text" : "hover";
};

/**
 * Owns the cross-chapter pointer field and custom cursor. Expensive visual
 * work runs only while the pointer is moving; the ambient light itself moves
 * through compositor transforms instead of repainting a gradient every frame.
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

  const sectionTransition = mountSectionTransition(portfolio);

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
  let pointerX = innerWidth * 0.5;
  let pointerY = innerHeight * 0.44;
  let lightX = pointerX;
  let lightY = pointerY;
  let ringX = pointerX;
  let ringY = pointerY;
  let velocity = 0;
  let targetVelocity = 0;
  let lastPointerX = pointerX;
  let lastPointerY = pointerY;
  let cursorSeen = false;
  let cursorState: CursorState = "idle";
  let lastFrameTime = performance.now();

  const positionLight = () => {
    light.style.transform = `translate3d(${lightX}px, ${lightY}px, 0) translate(-50%, -50%)`;
    light.style.opacity = String(0.94 + Math.min(0.06, velocity * 0.06));
  };

  const setCursorState = (state: CursorState) => {
    cursorState = state;
    if (cursor) cursor.dataset.state = state;
    if (ring) ring.dataset.state = state;
  };

  const render = (time: number) => {
    frame = 0;
    const dt = Math.min(0.05, Math.max(0.001, (time - lastFrameTime) / 1000));
    lastFrameTime = time;

    lightX = damp(lightX, pointerX, 10, dt);
    lightY = damp(lightY, pointerY, 10, dt);
    velocity = damp(velocity, targetVelocity, 11, dt);
    targetVelocity *= Math.exp(-9 * dt);
    positionLight();

    if (ring && cursorSeen) {
      ringX = damp(ringX, pointerX, 20, dt);
      ringY = damp(ringY, pointerY, 20, dt);
      ring.style.transform = `translate3d(${ringX}px, ${ringY}px, 0)`;
    }

    const lightSettled =
      Math.abs(lightX - pointerX) < 0.15 &&
      Math.abs(lightY - pointerY) < 0.15 &&
      velocity < 0.003 &&
      targetVelocity < 0.003;
    const ringSettled =
      !ring ||
      !cursorSeen ||
      (Math.abs(ringX - pointerX) < 0.12 && Math.abs(ringY - pointerY) < 0.12);

    if (!lightSettled || !ringSettled) {
      frame = requestAnimationFrame(render);
    }
  };

  const requestRender = () => {
    if (frame) return;
    lastFrameTime = performance.now();
    frame = requestAnimationFrame(render);
  };

  const onPointerMove = (event: PointerEvent) => {
    pointerX = event.clientX;
    pointerY = event.clientY;

    const dx = pointerX - lastPointerX;
    const dy = pointerY - lastPointerY;
    targetVelocity = Math.min(1, Math.hypot(dx, dy) / 44);
    lastPointerX = pointerX;
    lastPointerY = pointerY;

    if (cursor && ring) {
      cursor.style.transform = `translate3d(${pointerX}px, ${pointerY}px, 0)`;
      if (!cursorSeen) {
        cursorSeen = true;
        ringX = pointerX;
        ringY = pointerY;
        cursor.classList.add("is-on");
        ring.classList.add("is-on");
      }
    }

    requestRender();
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
    requestRender();
  };

  addEventListener("pointermove", onPointerMove, { passive: true });
  if (cursorEnabled) {
    addEventListener("pointerover", onPointerOver, { passive: true });
    addEventListener("pointerdown", onPointerDown, { passive: true });
    addEventListener("pointerup", onPointerUp, { passive: true });
    document.documentElement.addEventListener("pointerout", onPointerOut);
  }

  positionLight();

  return () => {
    if (frame) cancelAnimationFrame(frame);
    removeEventListener("pointermove", onPointerMove);
    removeEventListener("pointerover", onPointerOver);
    removeEventListener("pointerdown", onPointerDown);
    removeEventListener("pointerup", onPointerUp);
    document.documentElement.removeEventListener("pointerout", onPointerOut);
    sectionTransition?.destroy();
    light.remove();
    cursor?.remove();
    ring?.remove();
    portfolio.classList.remove("has-cursor");
  };
};
