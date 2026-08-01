<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

type Project = {
  id: string;
  title: string;
  kicker: string;
  summary: string;
  impact: string;
  year: string;
  code: string;
};

const projects: Project[] = [
  { id: "01", title: "Secure Document\nExtractor", kicker: "AI PRODUCT · BANKING", summary: "Sensitive documents become validated, auditable financial data without leaving isolated infrastructure.", impact: "Zero external API dependency", year: "2026", code: "DOC—AI" },
  { id: "02", title: "Natural Language\nto SQL", kicker: "AGENTS · DATA SECURITY", summary: "A schema-aware agent resolves ambiguity, orchestrates tools and produces guarded executable queries.", impact: "Grounded, guarded SQL", year: "2026", code: "NL—SQL" },
  { id: "03", title: "Financial MCP\nServer", kicker: "FINTECH · MULTI-AGENT", summary: "Real-time market tools and technical signals shaped into clear portfolio recommendations.", impact: "Signals into decisions", year: "2025", code: "MCP—03" },
  { id: "04", title: "Semantic Shopping\nAssistant", kicker: "SEARCH · E-COMMERCE", summary: "Intent-aware catalogue search across more than 50,000 products, designed around how people actually ask.", impact: "60% faster · 40% more accurate", year: "2025", code: "SEARCH" },
];

const root = ref<HTMLElement | null>(null);
const work = ref<HTMLElement | null>(null);
const rail = ref<HTMLElement | null>(null);
let context: gsap.Context | null = null;

onMounted(async () => {
  await nextTick();
  gsap.registerPlugin(ScrollTrigger);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  context = gsap.context(() => {
    gsap.timeline({ defaults: { ease: "power4.out" } })
      .from(".loader-word span", { yPercent: 110, duration: 0.8, stagger: 0.06 })
      .to(".loader", { clipPath: "inset(0 0 100% 0)", duration: 1, delay: 0.22, ease: "power3.inOut" })
      .set(".loader", { display: "none" })
      .from(".hero-title .line-inner", { yPercent: 105, rotate: 2, duration: 1.15, stagger: 0.1 }, "-=.35")
      .from(".hero-intro, .hero-index, .hero-orbit", { opacity: 0, y: 28, duration: 0.8, stagger: 0.09 }, "-=.7");

    gsap.to(".progress", { scaleX: 1, ease: "none", scrollTrigger: { start: 0, end: "max", scrub: 0.25 } });

    if (!reduced) {
      gsap.to(".hero-title .line:first-child", { xPercent: -9, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.7 } });
      gsap.to(".hero-title .line:last-child", { xPercent: 8, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.7 } });
      gsap.to(".hero-orbit", { rotate: 190, scale: 0.72, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.8 } });
      gsap.to(".hero-grid", { yPercent: 18, opacity: 0, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 1 } });

      if (work.value && rail.value) {
        const distance = () => Math.max(0, rail.value!.scrollWidth - innerWidth);
        gsap.to(rail.value, {
          x: () => -distance(),
          ease: "none",
          scrollTrigger: {
            trigger: work.value,
            start: "top top",
            end: () => `+=${distance() + innerHeight * 0.75}`,
            pin: true,
            scrub: 0.65,
            invalidateOnRefresh: true,
          },
        });
      }

      gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((element) => {
        gsap.from(element, { y: 75, opacity: 0, duration: 1.05, ease: "power3.out", scrollTrigger: { trigger: element, start: "top 84%" } });
      });
      gsap.utils.toArray<HTMLElement>(".manifesto-word").forEach((word, index) => {
        gsap.from(word, { opacity: 0.12, y: 18, duration: 0.45, scrollTrigger: { trigger: word, start: `top ${88 - (index % 4) * 3}%`, end: "top 56%", scrub: 0.4 } });
      });
    }
  }, root.value ?? undefined);
});

onBeforeUnmount(() => context?.revert());
</script>

<template>
  <div ref="root" class="site-shell">
    <div class="loader" aria-hidden="true"><div class="loader-meta"><span>DC® / PORTFOLIO</span><span>BUENOS AIRES / 2026</span></div><div class="loader-word"><span>FORM</span><span>MEETS</span><span>INTELLIGENCE.</span></div></div>
    <div class="grain" aria-hidden="true" />
    <header class="header"><a href="#top" class="logo" aria-label="Diego Cano — home"><b>DC</b><span>DESIGN ×<br>TECHNOLOGY</span></a><nav><a href="#work">WORK</a><a href="#profile">PROFILE</a><a href="#contact">CONTACT</a></nav><div class="availability"><i />AVAILABLE / 2026</div><div class="progress" /></header>

    <main id="top">
      <section class="hero">
        <div class="hero-grid" aria-hidden="true" />
        <div class="hero-index"><span>01 — 04</span><span>DESIGNER / DEVELOPER</span><span>ARG / GMT−3</span></div>
        <div class="hero-orbit" aria-hidden="true"><span>DESIGN</span><i /><span>CODE</span><b>↗</b></div>
        <h1 class="hero-title" aria-label="Diego Cano"><span class="line"><span class="line-inner">DIEGO</span></span><span class="line line-alt"><span class="line-inner">CA<em>N</em>O</span></span></h1>
        <div class="hero-bottom"><p class="hero-intro">I turn complex systems into digital products that feel <em>clear, useful and alive.</em></p><a href="#work" class="hero-cta"><span>EXPLORE<br>SELECTED WORK</span><b>↓</b></a></div>
      </section>

      <section class="manifesto" id="profile">
        <div class="section-label"><span>01 / POSITION</span><span>A PRACTICE BETWEEN DISCIPLINES</span></div>
        <p class="manifesto-copy"><span v-for="word in 'Design judgment and technical depth should not live in separate rooms. I connect both to build intelligent products with a distinct point of view.'.split(' ')" :key="word" class="manifesto-word">{{ word }} </span></p>
        <div class="manifesto-note" data-reveal><span>PRODUCT THINKING</span><p>From a messy question to a coherent system: research, interaction, visual language and production code.</p></div>
      </section>

      <section ref="work" id="work" class="work-section">
        <div class="work-head"><span>02 / SELECTED WORK</span><p>FOUR SYSTEMS<br>ONE POINT OF VIEW</p><b>SCROLL TO EXPLORE →</b></div>
        <div ref="rail" class="project-rail">
          <article v-for="(project, index) in projects" :key="project.id" class="project-panel">
            <div class="project-number">{{ project.id }}</div>
            <div :class="['project-visual', `visual-${index + 1}`]" aria-hidden="true"><div class="visual-grid" /><span>{{ project.code }}</span><i /><i /><i /></div>
            <div class="project-meta"><span>{{ project.kicker }}</span><span>{{ project.year }}</span></div>
            <h2>{{ project.title }}</h2>
            <div class="project-bottom"><strong>{{ project.impact }}</strong><p>{{ project.summary }}</p><button type="button" aria-label="Open project">↗</button></div>
          </article>
          <div class="rail-end"><span>END / 04</span><h3>More work<br><em>in progress.</em></h3><a href="#contact">START A CONVERSATION ↗</a></div>
        </div>
      </section>

      <section class="method">
        <div class="section-label"><span>03 / METHOD</span><span>HOW THE WORK MOVES</span></div>
        <h2 data-reveal>From ambiguity<br>to <em>useful form.</em></h2>
        <div class="method-grid">
          <article data-reveal><span>01</span><h3>Frame</h3><p>Understand the real problem, the people inside it and the constraints that shape the answer.</p></article>
          <article data-reveal><span>02</span><h3>Shape</h3><p>Turn research into flows, prototypes, visual systems and an interaction language with intent.</p></article>
          <article data-reveal><span>03</span><h3>Build</h3><p>Translate the concept into clean, resilient software without sanding away its personality.</p></article>
        </div>
      </section>

      <section class="profile-strip">
        <div class="profile-statement" data-reveal><span>DESIGNER’S EYE</span><b>+</b><span>ENGINEER’S MIND</span></div>
        <div class="profile-facts"><div><span>BASED</span><strong>Buenos Aires, AR</strong></div><div><span>FOCUS</span><strong>AI products · Systems · Interaction</strong></div><div><span>STACK</span><strong>Vue · TypeScript · Python · Java</strong></div></div>
      </section>

      <section id="contact" class="contact">
        <span>04 / LET’S MAKE SOMETHING MATTER</span>
        <h2 data-reveal>Have a difficult<br>idea? <em>Good.</em></h2>
        <div class="contact-line"><p>I like projects where clarity is hard-earned.</p><a href="mailto:diegocanomera@gmail.com">DIEGOCANOMERA@GMAIL.COM <b>↗</b></a></div>
      </section>
    </main>
    <footer><span>© 2026 DIEGO CANO</span><div><a href="https://github.com/dfc-coder">GITHUB ↗</a><a href="https://linkedin.com/in/software-engineer-diegocano">LINKEDIN ↗</a></div><span>DESIGNED & BUILT IN BUENOS AIRES</span></footer>
  </div>
</template>
