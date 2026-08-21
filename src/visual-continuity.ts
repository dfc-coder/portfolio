const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

/**
 * One ambient pointer field for the complete portfolio.
 *
 * Hero keeps its richer WebGL response, while this quiet shared layer remains
 * present behind the editorial content of every chapter. That keeps the site
 * feeling like one physical space instead of a set of unrelated scenes.
 */
export const mountVisualContinuity = () => {
  const stage = document.querySelector<HTMLElement>(".ref-stage");
  if (!stage) return () => undefined;

  const existing = stage.querySelector<HTMLElement>(".ref-global-pointer-light");
  if (existing) return () => undefined;

  const light = document.createElement("div");
  light.className = "ref-global-pointer-light";
  light.setAttribute("aria-hidden", "true");
  stage.append(light);

  let frame = 0;
  let currentX = 50;
  let currentY = 44;
  let targetX = currentX;
  let targetY = currentY;
  let currentVelocity = 0;
  let targetVelocity = 0;
  let lastX = innerWidth * 0.5;
  let lastY = innerHeight * 0.44;

  const onPointerMove = (event: PointerEvent) => {
    targetX = clamp((event.clientX / innerWidth) * 100, 0, 100);
    targetY = clamp((event.clientY / innerHeight) * 100, 0, 100);

    const deltaX = event.clientX - lastX;
    const deltaY = event.clientY - lastY;
    targetVelocity = clamp(Math.hypot(deltaX, deltaY) / 42, 0, 1);
    lastX = event.clientX;
    lastY = event.clientY;
  };

  const onPointerLeave = () => {
    targetVelocity = 0;
  };

  const render = () => {
    currentX += (targetX - currentX) * 0.105;
    currentY += (targetY - currentY) * 0.105;
    currentVelocity += (targetVelocity - currentVelocity) * 0.08;
    targetVelocity *= 0.91;

    light.style.setProperty("--ref-pointer-x", `${currentX.toFixed(3)}%`);
    light.style.setProperty("--ref-pointer-y", `${currentY.toFixed(3)}%`);
    light.style.setProperty("--ref-pointer-velocity", currentVelocity.toFixed(4));

    frame = requestAnimationFrame(render);
  };

  addEventListener("pointermove", onPointerMove, { passive: true });
  addEventListener("pointerleave", onPointerLeave);
  frame = requestAnimationFrame(render);

  return () => {
    cancelAnimationFrame(frame);
    removeEventListener("pointermove", onPointerMove);
    removeEventListener("pointerleave", onPointerLeave);
    light.remove();
  };
};
