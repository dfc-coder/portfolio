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
 * Owns the cross-chapter pointer field and custom cursor. The pointer field is
 * a localized compositor layer: position, direction and stretch are updated
 * through transforms, so the gradient itself is never repainted per frame.
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
  let velocityX = 0;
  let velocityY = 0;
  let targetVelocityX = 0;
  let targetVelocityY = 0;
  let lightAngle = 0;
  let lastPointerX = pointerX;
  let lastPointerY = pointerY;
  let cursorSeen = false;
  let cursorState: CursorState = "idle";
  let lastFrameTime = performance.now();

  const positionLight = () => {
    const speed = Math.min(1, Math.hypot(velocityX, velocityY));
    if (speed > 0.012) lightAngle = Math.atan2(velocityY, velocityX);

    const stretch = 1 + speed * 0.28;
    const crossScale = 1 - speed * 0.08;
    const pulse = 1 + speed * 0.035;

    light.style.transform =
      `translate3d(${lightX}px, ${lightY}px, 0) ` +
      `translate(-50%, -50%) rotate(${lightAngle}rad) ` +
      `scale(${(stretch * pulse).toFixed(4)}, ${(crossScale * pulse).toFixed(4)})`;
    light.style.opacity = String(0.92 + speed * 0.08);
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

    lightX = damp(lightX, pointerX, 8.5, dt);
    lightY = damp(lightY, pointerY, 8.5, dt);
    velocityX = damp(velocityX, targetVelocityX, 12, dt);
    velocityY = damp(velocityY, targetVelocityY, 12, dt);

    const decay = Math.exp(-8.5 * dt);
    targetVelocityX *= decay;
    targetVelocityY *= decay;
    positionLight();

    if (ring && cursorSeen) {
      ringX = damp(ringX, pointerX, 20, dt);
      ringY = damp(ringY, pointerY, 20, dt);
      ring.style.transform = `translate3d(${ringX}px, ${ringY}px, 0)`;
    }

    const lightSettled =
      Math.abs(lightX - pointerX) < 0.15 &&
      Math.abs(lightY - pointerY) < 0.15 &&
      Math.abs(velocityX) < 0.003 &&
      Math.abs(velocityY) < 0.003 &&
      Math.abs(targetVelocityX) < 0.003 &&
      Math.abs(targetVelocityY) < 0.003;
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
    const distance = Math.hypot(dx, dy);
    const magnitude = Math.min(1, distance / 40);

    if (distance > 0.001) {
      targetVelocityX = (dx / distance) * magnitude;
      targetVelocityY = (dy / distance) * magnitude;
    }

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
    targetVelocityX = 0;
    targetVelocityY = 0;
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
