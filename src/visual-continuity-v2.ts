const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

/**
 * Shared pointer field for all chapters.
 * Hero keeps its WebGL material; this layer supplies one quiet ambient response
 * to the remaining scenes. The light deliberately trails and offsets the cursor
 * so it reads as surface illumination rather than a CSS spotlight.
 */
export const mountVisualContinuity = () => {
  const stage = document.querySelector<HTMLElement>(".ref-stage");
  if (!stage) return () => undefined;

  stage.querySelector(".ref-global-pointer-light")?.remove();

  const light = document.createElement("div");
  light.className = "ref-global-pointer-light";
  light.setAttribute("aria-hidden", "true");
  stage.append(light);

  let frame = 0;
  let currentX = 47;
  let currentY = 47;
  let targetX = currentX;
  let targetY = currentY;
  let currentVelocity = 0;
  let targetVelocity = 0;
  let lastX = innerWidth * 0.5;
  let lastY = innerHeight * 0.44;

  const onPointerMove = (event: PointerEvent) => {
    const normalizedX = (event.clientX / innerWidth) * 100;
    const normalizedY = (event.clientY / innerHeight) * 100;

    targetX = clamp(normalizedX - 2.4, -4, 104);
    targetY = clamp(normalizedY + 2.8, -4, 104);

    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    targetVelocity = clamp(Math.hypot(dx, dy) / 46, 0, 1);
    lastX = event.clientX;
    lastY = event.clientY;
  };

  const onPointerLeave = () => {
    targetVelocity = 0;
  };

  const render = () => {
    currentX += (targetX - currentX) * 0.052;
    currentY += (targetY - currentY) * 0.044;
    currentVelocity += (targetVelocity - currentVelocity) * 0.07;
    targetVelocity *= 0.88;

    const x = `${currentX.toFixed(3)}%`;
    const y = `${currentY.toFixed(3)}%`;
    const velocity = currentVelocity.toFixed(4);

    stage.style.setProperty("--ref-pointer-x", x);
    stage.style.setProperty("--ref-pointer-y", y);
    stage.style.setProperty("--ref-pointer-velocity", velocity);
    light.style.setProperty("--ref-pointer-x", x);
    light.style.setProperty("--ref-pointer-y", y);
    light.style.setProperty("--ref-pointer-velocity", velocity);

    frame = requestAnimationFrame(render);
  };

  addEventListener("pointermove", onPointerMove, { passive: true });
  addEventListener("pointerleave", onPointerLeave);
  frame = requestAnimationFrame(render);

  return () => {
    cancelAnimationFrame(frame);
    removeEventListener("pointermove", onPointerMove);
    removeEventListener("pointerleave", onPointerLeave);
    ["--ref-pointer-x", "--ref-pointer-y", "--ref-pointer-velocity"].forEach(
      (property) => stage.style.removeProperty(property),
    );
    light.remove();
  };
};
