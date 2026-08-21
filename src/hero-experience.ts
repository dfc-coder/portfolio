import gsap from "gsap";
import * as THREE from "three";

const HERO_SELECTOR = ".ref-scene--hero";
const STRUCTURAL_EASE = "power3.inOut";
const SETTLE_EASE = "power3.out";

const vertexShader = /* glsl */ `
  varying vec2 vUv;

  void main() {
    vUv = uv;
    gl_Position = vec4(position, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  precision highp float;

  uniform vec2 uResolution;
  uniform vec2 uPointer;
  uniform float uTime;
  uniform float uVelocity;
  uniform float uReveal;
  varying vec2 vUv;

  float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);

    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));

    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
  }

  float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    mat2 rotate = mat2(0.80, -0.60, 0.60, 0.80);

    for (int i = 0; i < 4; i++) {
      value += noise(p) * amplitude;
      p = rotate * p * 2.02 + 7.13;
      amplitude *= 0.5;
    }

    return value;
  }

  void main() {
    vec2 uv = vUv;
    vec2 p = uv - 0.5;
    float aspect = uResolution.x / max(1.0, uResolution.y);
    p.x *= aspect;

    vec2 pointer = uPointer - 0.5;
    pointer.x *= aspect;

    float distanceToPointer = length(p - pointer);
    float field = fbm(p * 2.1 + vec2(uTime * 0.018, -uTime * 0.014));
    float detail = fbm(p * 5.2 - vec2(uTime * 0.010, uTime * 0.012));

    float impulse = sin(distanceToPointer * 24.0 - uTime * 1.35);
    impulse *= exp(-distanceToPointer * 5.6);
    impulse *= min(1.0, uVelocity * 1.8);

    float halo = exp(-distanceToPointer * 4.2) * (0.025 + uVelocity * 0.055);
    float tonal = 0.018 + field * 0.045 + detail * 0.012 + halo + impulse * 0.012;
    tonal *= uReveal;

    vec3 ink = vec3(0.035, 0.034, 0.031);
    vec3 paper = vec3(0.92, 0.89, 0.83);
    vec3 color = mix(ink, paper, clamp(tonal, 0.0, 0.14));

    float vignette = smoothstep(0.92, 0.25, length((uv - 0.5) * vec2(0.9, 1.1)));
    color *= mix(0.82, 1.0, vignette);

    gl_FragColor = vec4(color, 0.92 * uReveal);
  }
`;

class HeroField {
  private readonly host: HTMLElement;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.Camera();
  private readonly material: THREE.ShaderMaterial;
  private readonly geometry = new THREE.PlaneGeometry(2, 2);
  private readonly mesh: THREE.Mesh;
  private readonly canvas: HTMLCanvasElement;
  private frame = 0;
  private start = performance.now();
  private targetPointer = new THREE.Vector2(0.72, 0.34);
  private pointer = new THREE.Vector2(0.72, 0.34);
  private velocity = 0;
  private targetVelocity = 0;
  private lastPointer = new THREE.Vector2(0.72, 0.34);
  private lastPointerTime = performance.now();
  private resizeObserver: ResizeObserver;

  constructor(host: HTMLElement) {
    this.host = host;
    this.canvas = document.createElement("canvas");
    this.canvas.className = "ref-hero-field";
    this.canvas.setAttribute("aria-hidden", "true");
    host.prepend(this.canvas);

    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      alpha: true,
      antialias: false,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    this.renderer.setClearColor(0x000000, 0);

    this.material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      uniforms: {
        uResolution: { value: new THREE.Vector2(1, 1) },
        uPointer: { value: this.pointer.clone() },
        uTime: { value: 0 },
        uVelocity: { value: 0 },
        uReveal: { value: 0 },
      },
    });

    this.mesh = new THREE.Mesh(this.geometry, this.material);
    this.scene.add(this.mesh);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(host);
    this.resize();

    window.addEventListener("pointermove", this.onPointerMove, { passive: true });
    document.addEventListener("visibilitychange", this.onVisibility);
    this.frame = requestAnimationFrame(this.render);
  }

  get revealUniform() {
    return this.material.uniforms.uReveal;
  }

  private resize = () => {
    const rect = this.host.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    this.renderer.setSize(width, height, false);
    this.material.uniforms.uResolution.value.set(width, height);
  };

  private onPointerMove = (event: PointerEvent) => {
    const rect = this.host.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const y = 1 - Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
    this.targetPointer.set(x, y);

    const now = performance.now();
    const dt = Math.max(16, now - this.lastPointerTime);
    const distance = this.targetPointer.distanceTo(this.lastPointer);
    this.targetVelocity = Math.min(1, (distance / dt) * 1800);
    this.lastPointer.copy(this.targetPointer);
    this.lastPointerTime = now;
  };

  private onVisibility = () => {
    if (!document.hidden && !this.frame) {
      this.start = performance.now() - this.material.uniforms.uTime.value * 1000;
      this.frame = requestAnimationFrame(this.render);
    }
  };

  private render = (now: number) => {
    if (document.hidden) {
      this.frame = 0;
      return;
    }

    this.pointer.lerp(this.targetPointer, 0.055);
    this.velocity += (this.targetVelocity - this.velocity) * 0.09;
    this.targetVelocity *= 0.91;

    this.material.uniforms.uPointer.value.copy(this.pointer);
    this.material.uniforms.uVelocity.value = this.velocity;
    this.material.uniforms.uTime.value = (now - this.start) / 1000;

    this.renderer.render(this.scene, this.camera);
    this.frame = requestAnimationFrame(this.render);
  };

  destroy() {
    cancelAnimationFrame(this.frame);
    this.resizeObserver.disconnect();
    window.removeEventListener("pointermove", this.onPointerMove);
    document.removeEventListener("visibilitychange", this.onVisibility);
    this.geometry.dispose();
    this.material.dispose();
    this.renderer.dispose();
    this.canvas.remove();
  }
}

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

export const mountHeroExperience = () => {
  const hero = document.querySelector<HTMLElement>(HERO_SELECTOR);
  if (!hero) return () => undefined;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) {
    document.documentElement.classList.remove("is-refined-intro");
    return () => undefined;
  }

  const heroWords = Array.from(
    hero.querySelectorAll<HTMLElement>(".ref-hero__title > span > i"),
  );
  const heroInitials = Array.from(hero.querySelectorAll<HTMLElement>(".ref-hero__initial"));
  const heroTails = Array.from(hero.querySelectorAll<HTMLElement>(".ref-hero__tail"));
  const meta = hero.querySelector<HTMLElement>(".ref-hero__meta");
  const thesis = hero.querySelector<HTMLElement>(".ref-hero__thesis");
  const scrollCue = hero.querySelector<HTMLElement>(".ref-scroll-cue");
  const header = document.querySelector<HTMLElement>(".ref-header");

  if (heroWords.length !== 2 || !meta || !thesis || !scrollCue || !header) {
    return () => undefined;
  }

  const { copy: thesisCopy, accent: thesisAccent } = ensureThesisParts(thesis);

  /* The legacy intro still exists in the Vue component, but it is no longer
     allowed to own a visible Hero property. Kill its pending tweens first so
     there is one choreography and one source of timing truth. */
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

  let field: HeroField | null = null;
  try {
    field = new HeroField(hero);
  } catch (error) {
    console.warn("Hero WebGL field unavailable; continuing with DOM motion.", error);
  }

  const openingMark = opening.querySelector<HTMLElement>(".creative-opening__mark");
  const openingRule = opening.querySelector<HTMLElement>(".creative-opening__rule");
  const openingLabel = opening.querySelector<HTMLElement>(".creative-opening__label");
  const openingMeta = opening.querySelector<HTMLElement>(".creative-opening__meta");
  const openingProgress = opening.querySelector<HTMLElement>(".creative-opening__progress > i");

  /* ~1.96s total. Each beat has one visual protagonist:
     opening -> structural curtain -> name -> thesis -> secondary chrome. */
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
    .to(
      openingRule,
      { scaleX: 1, duration: 0.34, ease: STRUCTURAL_EASE },
      0.10,
    )
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
    .to(
      openingProgress,
      { scaleX: 1, duration: 0.42, ease: STRUCTURAL_EASE },
      0.04,
    )
    .addLabel("curtain", 0.46)
    .to(
      opening,
      { clipPath: "inset(0% 0% 100% 0%)", duration: 0.62, ease: STRUCTURAL_EASE },
      "curtain",
    )
    .to(
      field?.revealUniform ?? { value: 0 },
      { value: 1, duration: 0.60, ease: SETTLE_EASE },
      "curtain+=0.03",
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
    .to(
      thesisAccent,
      { scaleY: 1, duration: 0.16, ease: STRUCTURAL_EASE },
      "thesis",
    )
    .to(
      thesisCopy,
      { opacity: 1, x: 0, duration: 0.24, ease: SETTLE_EASE },
      "thesis+=0.04",
    )
    .to(meta, { opacity: 1, y: 0, duration: 0.18, ease: SETTLE_EASE }, "thesis+=0.32")
    .to(header, { opacity: 1, y: 0, duration: 0.18, ease: SETTLE_EASE }, "thesis+=0.38")
    .to(scrollCue, { opacity: 1, y: 0, duration: 0.18, ease: SETTLE_EASE }, "thesis+=0.44");

  const title = hero.querySelector<HTMLElement>(".ref-hero__title");
  const titleX = title ? gsap.quickTo(title, "x", { duration: 1.25, ease: SETTLE_EASE }) : null;
  const titleY = title ? gsap.quickTo(title, "y", { duration: 1.25, ease: SETTLE_EASE }) : null;
  const thesisX = gsap.quickTo(thesis, "x", { duration: 1.4, ease: SETTLE_EASE });
  const thesisY = gsap.quickTo(thesis, "y", { duration: 1.4, ease: SETTLE_EASE });

  const onHeroPointerMove = (event: PointerEvent) => {
    const rect = hero.getBoundingClientRect();
    const nx = (event.clientX - rect.left) / Math.max(1, rect.width) - 0.5;
    const ny = (event.clientY - rect.top) / Math.max(1, rect.height) - 0.5;
    titleX?.(nx * 9);
    titleY?.(ny * 5);
    thesisX(nx * -4);
    thesisY(ny * -3);
    hero.dataset.heroHover = "true";
  };

  const onHeroPointerLeave = () => {
    titleX?.(0);
    titleY?.(0);
    thesisX(0);
    thesisY(0);
    hero.dataset.heroHover = "false";
  };

  hero.addEventListener("pointermove", onHeroPointerMove, { passive: true });
  hero.addEventListener("pointerleave", onHeroPointerLeave, { passive: true });

  return () => {
    timeline.kill();
    unlockInput();
    opening.remove();
    field?.destroy();
    hero.removeEventListener("pointermove", onHeroPointerMove);
    hero.removeEventListener("pointerleave", onHeroPointerLeave);
  };
};
