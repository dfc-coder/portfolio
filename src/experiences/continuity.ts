import { mountSectionTransition } from "./section-transition";

export { transitionSectionNavigation } from "./section-transition";

const CURSOR_INTERACTIVE = "button, a, input, textarea, select, [data-cursor]";
type CursorState = "idle" | "hover" | "press" | "text";

const cursorStateFor = (element: Element | null): CursorState => {
  if (!element) return "idle";
  return element.matches("input, textarea") ? "text" : "hover";
};

/**
 * Cross-chapter continuity now owns only the custom cursor and section
 * transition. Pointer illumination belongs to the shared Three atmosphere.
 */
export const mountVisualContinuity = () => {
  const portfolio = document.querySelector<HTMLElement>(".ref-portfolio");
  if (!portfolio) return () => undefined;

  portfolio.querySelector(".ref-cursor")?.remove();
  portfolio.querySelector(".ref-cursor-ring")?.remove();

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

  let cursorSeen = false;
  let cursorState: CursorState = "idle";

  const setCursorState = (state: CursorState) => {
    cursorState = state;
    if (cursor) cursor.dataset.state = state;
    if (ring) ring.dataset.state = state;
  };

  const onPointerMove = (event: PointerEvent) => {
    if (!cursor || !ring) return;
    const transform = `translate3d(${event.clientX}px, ${event.clientY}px, 0)`;
    cursor.style.transform = transform;
    ring.style.transform = transform;

    if (!cursorSeen) {
      cursorSeen = true;
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
  };

  if (cursorEnabled) {
    addEventListener("pointermove", onPointerMove, { passive: true });
    addEventListener("pointerover", onPointerOver, { passive: true });
    addEventListener("pointerdown", onPointerDown, { passive: true });
    addEventListener("pointerup", onPointerUp, { passive: true });
    document.documentElement.addEventListener("pointerout", onPointerOut);
  }

  return () => {
    removeEventListener("pointermove", onPointerMove);
    removeEventListener("pointerover", onPointerOver);
    removeEventListener("pointerdown", onPointerDown);
    removeEventListener("pointerup", onPointerUp);
    document.documentElement.removeEventListener("pointerout", onPointerOut);
    sectionTransition?.destroy();
    cursor?.remove();
    ring?.remove();
    portfolio.classList.remove("has-cursor");
  };
};
