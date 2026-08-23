import gsap from "gsap";

type NavigationCommit = () => void;
type NavigationTransition = (commit: NavigationCommit, direction: number) => void;

let navigationTransition: NavigationTransition | null = null;

export const mountSectionTransition = (portfolio: HTMLElement) => {
  portfolio.querySelector(".ref-navigation-transition")?.remove();

  const cover = document.createElement("div");
  cover.className = "ref-navigation-transition";
  cover.setAttribute("aria-hidden", "true");
  portfolio.append(cover);

  let timeline: gsap.core.Timeline | null = null;
  let active = false;

  const run: NavigationTransition = (commit, direction) => {
    if (active) return;

    active = true;
    const origin = direction < 0 ? "42% 50%" : "58% 50%";
    cover.style.setProperty("--transition-origin", origin);
    cover.classList.add("is-active");
    document.documentElement.classList.add("is-section-transitioning");

    timeline?.kill();
    timeline = gsap.timeline({
      defaults: { overwrite: true },
      onComplete: () => {
        active = false;
        cover.classList.remove("is-active");
        document.documentElement.classList.remove("is-section-transitioning");
        gsap.set(cover, { clearProps: "clipPath,opacity,visibility" });
      },
    });

    timeline
      .set(cover, {
        visibility: "visible",
        opacity: 1,
        clipPath: `circle(0% at ${origin})`,
      })
      .to(cover, {
        clipPath: `circle(150% at ${origin})`,
        duration: 0.54,
        ease: "expo.inOut",
      })
      .add(() => commit())
      .to({}, { duration: 0.04 })
      .to(cover, {
        clipPath: `circle(0% at ${origin})`,
        duration: 0.62,
        ease: "expo.inOut",
      });
  };

  navigationTransition = run;

  return {
    destroy: () => {
      timeline?.kill();
      timeline = null;
      active = false;
      navigationTransition = null;
      document.documentElement.classList.remove("is-section-transitioning");
      cover.remove();
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
