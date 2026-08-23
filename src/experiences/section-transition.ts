import { gsap } from "../motion/gsap";
import { setStageTransition } from "../graphics/stageGraphics";

type NavigationCommit = () => void;
type NavigationTransition = (commit: NavigationCommit, direction: number) => void;
type GsapTimeline = ReturnType<typeof gsap.timeline>;

let navigationTransition: NavigationTransition | null = null;

export const mountSectionTransition = (_portfolio: HTMLElement) => {
  let timeline: GsapTimeline | null = null;
  let active = false;

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
      onComplete: () => {
        active = false;
        setStageTransition(0, normalizedDirection, false);
        document.documentElement.classList.remove("is-section-transitioning");
      },
    });

    timeline
      .to(state, {
        progress: 1,
        duration: 0.62,
        ease: "power3.inOut",
        onUpdate: () => setStageTransition(state.progress, normalizedDirection, true),
      })
      .add(() => commit())
      .to({}, { duration: 0.04 })
      .to(state, {
        progress: 0,
        duration: 0.70,
        ease: "power3.inOut",
        onUpdate: () => setStageTransition(state.progress, normalizedDirection, true),
      });
  };

  navigationTransition = run;

  return {
    destroy: () => {
      timeline?.kill();
      timeline = null;
      active = false;
      navigationTransition = null;
      setStageTransition(0, 1, false);
      document.documentElement.classList.remove("is-section-transitioning");
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
