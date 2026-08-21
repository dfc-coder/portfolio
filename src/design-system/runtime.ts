import { mountVisualContinuity } from "../visual-continuity-v2";

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const readNumber = (element: HTMLElement, property: string) => {
  const value = Number.parseFloat(getComputedStyle(element).getPropertyValue(property));
  return Number.isFinite(value) ? clamp01(value) : 0;
};

/**
 * Runtime ownership for shared design-system behavior.
 *
 * Individual chapter directors own semantic progress. This layer owns only
 * repeated behavior that must be identical everywhere: chapter-statement
 * travel and the global ambient pointer field.
 */
export const mountDesignSystemRuntime = () => {
  const stage = document.querySelector<HTMLElement>(".ref-stage");
  if (!stage) return () => undefined;

  const disposePointer = mountVisualContinuity();
  let frame = 0;

  const render = () => {
    const trajectoryIntro = document.querySelector<HTMLElement>(".trajectory-intro");
    const systemsIntro = document.querySelector<HTMLElement>(".systems-intro");

    if (trajectoryIntro) {
      const enter = readNumber(stage, "--trajectory-intro-in");
      const exit = readNumber(stage, "--trajectory-intro-out");
      const y = (1 - enter) * 42 - exit * 58;
      trajectoryIntro.style.setProperty("transform", `translate3d(0, ${y.toFixed(2)}px, 0)`, "important");
    }

    if (systemsIntro) {
      const enter = readNumber(stage, "--systems-intro-in");
      const exit = readNumber(stage, "--systems-intro-out");
      const y = (1 - enter) * 42 - exit * 58;
      systemsIntro.style.setProperty("transform", `translate3d(0, ${y.toFixed(2)}px, 0)`, "important");
    }

    frame = requestAnimationFrame(render);
  };

  frame = requestAnimationFrame(render);

  return () => {
    cancelAnimationFrame(frame);
    disposePointer();
  };
};
