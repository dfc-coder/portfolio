import { gsap } from "../motion/gsap";
import { setStageTransition } from "../graphics/stageGraphics";

const NAVIGATION_COVER_SECONDS = 0.9;
const NAVIGATION_HOLD_SECONDS = 0.02;
const NAVIGATION_REVEAL_SECONDS = 0.98;

type NavigationCommit = () => void;
type NavigationTransition = (commit: NavigationCommit, direction: number) => void;

let navigationTransition: NavigationTransition | null = null;

const smoother = (value: number) => {
  const x = Math.min(1, Math.max(0, value));
  return x * x * x * (x * (x * 6 - 15) + 10);
};

export const mountSectionTransition = (_portfolio: HTMLElement) => {
  let timeline: gsap.core.Timeline | null = null;
  let active = false;

  const finish = () => {
    active = false;
    setStageTransition(0, 1, false);
    document.documentElement.classList.remove("is-section-transitioning");
  };

  const run: NavigationTransition = (commit, direction) => {
    if (active) return;

    active = true;
    const normalizedDirection = direction < 0 ? -1 : 1;
    const state = { progress: 0 };

    document.documentElement.classList.add("is-section-transitioning");
    setStageTransition(0, normalizedDirection, true);

    timeline?.kill();
    timeline = gsap.timeline({
      defaults: { overwrite: true },
      onComplete: finish,
      onInterrupt: finish,
    });

    timeline
      .to(state, {
        progress: 1,
        duration: NAVIGATION_COVER_SECONDS,
        ease: "none",
        onUpdate: () =>
          setStageTransition(smoother(state.progress), normalizedDirection, true),
      })
      .add(() => {
        setStageTransition(1, normalizedDirection, true);
        commit();
      })
      .to({}, { duration: NAVIGATION_HOLD_SECONDS })
      .to(state, {
        progress: 0,
        duration: NAVIGATION_REVEAL_SECONDS,
        ease: "none",
        onUpdate: () =>
          setStageTransition(smoother(state.progress), normalizedDirection, true),
      });
  };

  navigationTransition = run;

  return {
    destroy: () => {
      timeline?.kill();
      timeline = null;
      active = false;
      navigationTransition = null;
      finish();
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
