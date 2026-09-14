import { gsap } from "../motion/gsap";
import { narrativeRuntime, type NarrativeState } from "./narrative-runtime";

const HERO_SELECTOR = ".ref-scene--hero";
const STRUCTURAL_EASE = "power3.inOut";
const SETTLE_EASE = "power3.out";

const createOpening = () => {
  const opening = document.createElement("div");
  opening.className = "creative-opening";
  opening.setAttribute("aria-hidden", "true");
  opening.innerHTML = `
    <div class="creative-opening__meta">
      <span>Diego Cano / Portfolio 2026</span>
      <span>Buenos Aires · GMT−3</span>
    </div>
    <div class="creative-opening__center">
      <span class="creative-opening__mark">DC</span>
      <i class="creative-opening__rule"></i>
      <span class="creative-opening__label">Software<br>Intelligence<br>Objects</span>
    </div>
    <div class="creative-opening__progress"><i></i></div>
  `;
  document.body.append(opening);
  return opening;
};

const ensureThesisParts = (thesis: HTMLElement) => {
  let copy = thesis.querySelector<HTMLElement>(".ref-hero__thesis-copy");
  let accent = thesis.querySelector<HTMLElement>(".ref-hero__thesis-accent");

  if (!copy) {
    copy = document.createElement("span");
    copy.className = "ref-hero__thesis-copy";
    while (thesis.firstChild) copy.append(thesis.firstChild);
    thesis.append(copy);
  }

  if (!accent) {
    accent = document.createElement("i");
    accent.className = "ref-hero__thesis-accent";
    accent.setAttribute("aria-hidden", "true");
    thesis.prepend(accent);
  }

  return { copy, accent };
};

const lockInput = () => {
  const prevent = (event: Event) => event.preventDefault();
  const preventKeys = (event: KeyboardEvent) => {
    if (["ArrowDown", "ArrowUp", "PageDown", "PageUp", "Home", "End", " "].includes(event.key)) {
      event.preventDefault();
    }
  };

  window.addEventListener("wheel", prevent, { passive: false });
  window.addEventListener("touchmove", prevent, { passive: false });
  window.addEventListener("keydown", preventKeys);

  return () => {
    window.removeEventListener("wheel", prevent);
    window.removeEventListener("touchmove", prevent);
    window.removeEventListener("keydown", preventKeys);
  };
};

const mountHeroPointerField = (hero: HTMLElement, thesis: HTMLElement) => {
  const titleWords = Array.from(
    hero.querySelectorAll<HTMLElement>(".ref-hero__title > span > i"),
  );
  const wordFields = titleWords.map((word) => ({
    x: gsap.quickTo(word, "x", { duration: 1.25, ease: SETTLE_EASE }),
    y: gsap.quickTo(word, "y", { duration: 1.25, ease: SETTLE_EASE }),
  }));
  const thesisX = gsap.quickTo(thesis, "x", { duration: 1.4, ease: SETTLE_EASE });
  const thesisY = gsap.quickTo(thesis, "y", { duration: 1.4, ease: SETTLE_EASE });

  let heroRect = hero.getBoundingClientRect();
  let pointerActive = false;

  const measure = () => {
    heroRect = hero.getBoundingClientRect();
  };

  const resetPointerField = () => {
    wordFields.forEach((field) => {
      field.x(0);
      field.y(0);
    });
    thesisX(0);
    thesisY(0);
    hero.dataset.heroHover = "false";
  };

  const onHeroPointerMove = (event: PointerEvent) => {
    if (!heroRect.width || !heroRect.height) return;
    const nx = (event.clientX - heroRect.left) / heroRect.width - 0.5;
    const ny = (event.clientY - heroRect.top) / heroRect.height - 0.5;
    wordFields.forEach((field) => {
      field.x(nx * 9);
      field.y(ny * 5);
    });
    thesisX(nx * -4);
    thesisY(ny * -3);
    hero.dataset.heroHover = "true";
  };

  const onHeroPointerLeave = () => {
    resetPointerField();
  };

  const setPointerActive = (active: boolean) => {
    if (active === pointerActive) return;
    pointerActive = active;

    if (active) {
      measure();
      hero.addEventListener("pointermove", onHeroPointerMove, { passive: true });
      hero.addEventListener("pointerleave", onHeroPointerLeave, { passive: true });
      return;
    }

    hero.removeEventListener("pointermove", onHeroPointerMove);
    hero.removeEventListener("pointerleave", onHeroPointerLeave);
    resetPointerField();
  };

  const syncPointerOwnership = (state: NarrativeState) => {
    setPointerActive(state.scene === "hero");
  };

  const resizeObserver = new ResizeObserver(measure);
  resizeObserver.observe(hero);
  const unsubscribe = narrativeRuntime.subscribe(syncPointerOwnership);

  return () => {
    unsubscribe();
    setPointerActive(false);
    resizeObserver.disconnect();
    gsap.killTweensOf([...titleWords, thesis]);
    gsap.set(titleWords, { x: 0, y: 0 });
    gsap.set(thesis, { x: 0, y: 0 });
    delete hero.dataset.heroHover;
  };
};

export const mountHeroExperience = () => {
  const hero = document.querySelector<HTMLElement>(HERO_SELECTOR);
  if (!hero) return () => undefined;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) {
    document.documentElement.classList.remove("is-refined-intro");
    return () => undefined;
  }

  const thesis = hero.querySelector<HTMLElement>(".ref-hero__thesis");
  if (!thesis) return () => undefined;

  if (document.documentElement.classList.contains("creative-hero-complete")) {
    return mountHeroPointerField(hero, thesis);
  }

  const heroWords = Array.from(
    hero.querySelectorAll<HTMLElement>(".ref-hero__title > span > i"),
  );
  const heroInitials = Array.from(hero.querySelectorAll<HTMLElement>(".ref-hero__initial"));
  const heroTails = Array.from(hero.querySelectorAll<HTMLElement>(".ref-hero__tail"));
  const meta = hero.querySelector<HTMLElement>(".ref-hero__meta");
  const scrollCue = hero.querySelector<HTMLElement>(".ref-scroll-cue");
  const header = document.querySelector<HTMLElement>(".ref-header");

  if (heroWords.length !== 2 || !meta || !scrollCue || !header) {
    return () => undefined;
  }

  const { copy: thesisCopy, accent: thesisAccent } = ensureThesisParts(thesis);

  gsap.killTweensOf([
    ...heroWords,
    ...heroInitials,
    ...heroTails,
    meta,
    thesis,
    thesisCopy,
    thesisAccent,
    scrollCue,
    header,
    ".ref-intro",
    ".ref-intro *",
  ]);

  document.documentElement.classList.remove("is-refined-intro");
  window.scrollTo({ top: 0, behavior: "auto" });

  gsap.set(heroInitials, { opacity: 1, clearProps: "clipPath" });
  gsap.set(heroTails, { opacity: 1, clearProps: "clipPath" });
  gsap.set(heroWords, {
    y: 26,
    opacity: 0,
    willChange: "transform, opacity",
  });
  gsap.set(meta, { opacity: 0, y: 6 });
  gsap.set(thesis, { opacity: 1, y: 0 });
  gsap.set(thesisAccent, {
    scaleY: 0,
    transformOrigin: "top center",
    willChange: "transform",
  });
  gsap.set(thesisCopy, {
    opacity: 0,
    x: -12,
    willChange: "transform, opacity",
  });
  gsap.set(scrollCue, { opacity: 0, y: 8 });
  gsap.set(header, { opacity: 0, y: -6 });

  const opening = createOpening();
  const unlockInput = lockInput();

  const openingMark = opening.querySelector<HTMLElement>(".creative-opening__mark");
  const openingRule = opening.querySelector<HTMLElement>(".creative-opening__rule");
  const openingLabel = opening.querySelector<HTMLElement>(".creative-opening__label");
  const openingMeta = opening.querySelector<HTMLElement>(".creative-opening__meta");
  const openingProgress = opening.querySelector<HTMLElement>(".creative-opening__progress > i");

  const timeline = gsap.timeline({
    onComplete: () => {
      opening.remove();
      unlockInput();
      gsap.set(heroWords, { clearProps: "willChange" });
      gsap.set(thesisCopy, { clearProps: "willChange" });
      gsap.set(thesisAccent, { clearProps: "willChange" });
      document.documentElement.classList.add("creative-hero-complete");
    },
  });

  timeline
    .fromTo(
      openingMark,
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.32, ease: SETTLE_EASE },
      0,
    )
    .to(openingRule, { scaleX: 1, duration: 0.34, ease: STRUCTURAL_EASE }, 0.10)
    .fromTo(
      openingLabel,
      { opacity: 0, x: -6 },
      { opacity: 1, x: 0, duration: 0.28, ease: SETTLE_EASE },
      0.20,
    )
    .fromTo(
      openingMeta,
      { opacity: 0, y: 4 },
      { opacity: 1, y: 0, duration: 0.24, ease: SETTLE_EASE },
      0.24,
    )
    .to(openingProgress, { scaleX: 1, duration: 0.42, ease: STRUCTURAL_EASE }, 0.04)
    .addLabel("curtain", 0.46)
    .to(
      opening,
      { clipPath: "inset(0% 0% 100% 0%)", duration: 0.62, ease: STRUCTURAL_EASE },
      "curtain",
    )
    .addLabel("name", "curtain+=0.28")
    .to(
      heroWords,
      {
        y: 0,
        opacity: 1,
        duration: 0.48,
        stagger: 0.07,
        ease: SETTLE_EASE,
      },
      "name",
    )
    .addLabel("thesis", "name+=0.60")
    .to(thesisAccent, { scaleY: 1, duration: 0.16, ease: STRUCTURAL_EASE }, "thesis")
    .to(
      thesisCopy,
      { opacity: 1, x: 0, duration: 0.24, ease: SETTLE_EASE },
      "thesis+=0.04",
    )
    .to(meta, { opacity: 1, y: 0, duration: 0.18, ease: SETTLE_EASE }, "thesis+=0.32")
    .to(header, { opacity: 1, y: 0, duration: 0.18, ease: SETTLE_EASE }, "thesis+=0.38")
    .to(scrollCue, { opacity: 1, y: 0, duration: 0.18, ease: SETTLE_EASE }, "thesis+=0.44");

  const cleanupPointerField = mountHeroPointerField(hero, thesis);

  return () => {
    timeline.kill();
    unlockInput();
    opening.remove();
    cleanupPointerField();
  };
};