<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import ArtExhibition from "./components/ArtExhibition.vue";
import ContactAssistant from "./components/ContactAssistant.vue";

type Experience = {
  period: string;
  role: string;
  company: string;
  summary: string;
  focus: string[];
};

type Project = {
  id: string;
  code: string;
  field: string;
  title: string;
  premise: string;
  detail: string;
  stack: string[];
  outcome: string;
  accent: string;
};

const experiences: Experience[] = [
  {
    period: "2025 — NOW",
    role: "AI Engineer",
    company: "aiRoss · Madrid / Remote",
    summary: "Design and implementation of private AI systems for document intelligence, structured extraction and production workflows where evidence, security and human review are first-class concerns.",
    focus: ["Local LLMs", "Document AI", "Python", "Product architecture"],
  },
  {
    period: "2024 — 2025",
    role: "Independent AI Engineer",
    company: "Applied AI · Remote",
    summary: "Agentic systems, retrieval pipelines and natural-language interfaces built around real operational constraints rather than isolated model demonstrations.",
    focus: ["RAG", "Agents", "NL→SQL", "Evaluation"],
  },
  {
    period: "2023 — 2025",
    role: "Software Engineer",
    company: "FK Tech · Argentina",
    summary: "Full-stack products and integrations with an emphasis on maintainable architecture, clear interfaces, secure APIs and delivery across the complete software lifecycle.",
    focus: ["TypeScript", "Backend", "Integrations", "Cloud"],
  },
];

const projects: Project[] = [
  {
    id: "01",
    code: "DOC—AI",
    field: "PRIVATE AI / BANKING",
    title: "Secure Document Extractor",
    premise: "Sensitive documents become structured financial data without leaving isolated infrastructure.",
    detail: "The system converts PDF and image documents, ranks evidence per field, runs local extraction and validates every result against typed schemas. Low-confidence outputs remain visible for human review instead of being disguised as certainty.",
    stack: ["Python", "FastAPI", "Docling", "Local LLM", "Redis"],
    outcome: "Private by design · evidence-linked output",
    accent: "#c65f43",
  },
  {
    id: "02",
    code: "NL→SQL",
    field: "AGENTS / DATA ACCESS",
    title: "Natural Language to SQL",
    premise: "A conversational question reaches data without granting unrestricted database access.",
    detail: "A planner resolves intent, retrieves only the relevant schema, applies business rules and rejects ambiguous or unsafe operations. The interface exposes the plan and preserves the boundary between asking a question and executing a query.",
    stack: ["Python", "Tool calling", "Schema RAG", "SQL policies", "Evaluation"],
    outcome: "Grounded questions · guarded execution",
    accent: "#8d8a82",
  },
  {
    id: "03",
    code: "MCP—03",
    field: "FINTECH / AGENT TOOLS",
    title: "Financial MCP Server",
    premise: "Market data becomes a set of explicit, reusable instruments instead of an opaque recommendation engine.",
    detail: "Each capability has a strict contract, identifiable source and predictable output. Specialized agents can combine quotes, portfolio context and technical signals while the final interpretation remains legible to the user.",
    stack: ["MCP", "Python", "Market data", "Typed tools", "Agents"],
    outcome: "Signals organised as auditable tools",
    accent: "#637087",
  },
  {
    id: "04",
    code: "SEARCH",
    field: "SEMANTIC SEARCH / PRODUCT",
    title: "Intent-aware Shopping Assistant",
    premise: "Product discovery starts from a real need, not from exact keyword matching.",
    detail: "The assistant converts incomplete language into comparable attributes, combines lexical and semantic retrieval and explains why each result is relevant. Ranking quality is evaluated independently from the conversational layer.",
    stack: ["TypeScript", "Embeddings", "Hybrid search", "Catalog API", "Metrics"],
    outcome: "Faster discovery · explainable relevance",
    accent: "#8a735e",
  },
];

const root = ref<HTMLElement | null>(null);
let context: gsap.Context | null = null;
let media: gsap.MatchMedia | null = null;

onMounted(async () => {
  await nextTick();
  gsap.registerPlugin(ScrollTrigger);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  context = gsap.context(() => {
    if (reduced) {
      gsap.set(".opening", { display: "none" });
    } else {
      gsap.timeline({ defaults: { ease: "power3.out" } })
        .from(".opening__line i", { scaleX: 0, transformOrigin: "left", duration: 0.72 })
        .from(".opening__copy span", { yPercent: 110, duration: 0.72, stagger: 0.06 }, "-=.4")
        .to(".opening__copy", { opacity: 0, y: -24, duration: 0.42, delay: 0.22, ease: "power2.in" })
        .to(".opening", { clipPath: "inset(0 0 100% 0)", duration: 0.9, ease: "expo.inOut" }, "-=.12")
        .set(".opening", { display: "none" })
        .from(".hero__title span", { yPercent: 108, duration: 1.05, stagger: 0.08 }, "-=.45")
        .from(".hero__intro, .hero__meta, .hero__scroll", { opacity: 0, y: 22, duration: 0.72, stagger: 0.08 }, "-=.65");
    }

    gsap.to(".reading-progress b", {
      scaleX: 1,
      ease: "none",
      scrollTrigger: { start: 0, end: "max", scrub: 0.15 },
    });

    if (!reduced) {
      gsap.to(".hero__media img", {
        scale: 1,
        yPercent: 7,
        ease: "none",
        scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.8 },
      });
      gsap.to(".hero__title span:first-child", {
        xPercent: -4,
        ease: "none",
        scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.8 },
      });
      gsap.to(".hero__title span:last-child", {
        xPercent: 4,
        ease: "none",
        scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.8 },
      });

      gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((element) => {
        gsap.from(element, {
          y: 54,
          opacity: 0,
          duration: 0.95,
          ease: "power3.out",
          scrollTrigger: { trigger: element, start: "top 84%" },
        });
      });

      gsap.utils.toArray<HTMLElement>(".position__statement .word").forEach((word, index) => {
        gsap.from(word, {
          opacity: 0.12,
          y: 18,
          scrollTrigger: {
            trigger: word,
            start: `top ${88 - (index % 4) * 2}%`,
            end: "top 56%",
            scrub: 0.28,
          },
        });
      });

      gsap.utils.toArray<HTMLElement>(".experience-entry").forEach((entry) => {
        gsap.from(entry.querySelectorAll(".experience-entry__body > *"), {
          opacity: 0,
          y: 32,
          duration: 0.72,
          stagger: 0.06,
          ease: "power3.out",
          scrollTrigger: { trigger: entry, start: "top 72%" },
        });
      });

      media = gsap.matchMedia();
      media.add("(min-width: 901px)", () => {
        gsap.utils.toArray<HTMLElement>(".system-story").forEach((story) => {
          const layers = story.querySelectorAll<HTMLElement>(".system-visual__layer");
          const nodes = story.querySelectorAll<HTMLElement>(".system-node");
          gsap.fromTo(layers, { scale: 0.9, opacity: 0.35 }, {
            scale: 1,
            opacity: 1,
            stagger: 0.08,
            ease: "none",
            scrollTrigger: { trigger: story, start: "top 78%", end: "bottom 28%", scrub: 0.6 },
          });
          gsap.from(nodes, {
            scale: 0,
            opacity: 0,
            stagger: 0.08,
            ease: "back.out(1.5)",
            scrollTrigger: { trigger: story, start: "top 60%" },
          });
        });
      });
    }

    addEventListener("load", () => ScrollTrigger.refresh(), { once: true });
  }, root.value ?? undefined);
});

onBeforeUnmount(() => {
  media?.revert();
  context?.revert();
});
</script>

<template>
  <div ref="root" class="site-shell">
    <a class="skip-link" href="#experience">Skip to professional experience</a>

    <div class="opening" aria-hidden="true">
      <div class="opening__meta"><span>DIEGO CANO / 2026</span><span>SOFTWARE · AI · OBJECTS</span></div>
      <div class="opening__line"><i /></div>
      <div class="opening__copy"><span>ENGINEERING</span><span>WITH A</span><span><em>POINT OF VIEW.</em></span></div>
    </div>

    <header class="site-header">
      <a class="brand" href="#top" aria-label="Diego Cano, home"><strong>DC</strong><span>SOFTWARE ENGINEER<br />+ CREATIVE TECHNOLOGIST</span></a>
      <nav aria-label="Portfolio index">
        <a href="#experience">EXPERIENCE</a>
        <a href="#systems">SYSTEMS</a>
        <a href="#visual-practice">VISUAL WORK</a>
      </nav>
      <a class="ask-link" href="#assistant">ASK THE AGENT ↘</a>
      <div class="reading-progress" aria-hidden="true"><b /></div>
    </header>

    <main id="top">
      <section class="hero">
        <div class="hero__media" aria-hidden="true"><img src="/studio/interior-shadow.png" alt="" /></div>
        <div class="hero__shade" aria-hidden="true" />
        <div class="hero__meta"><span>BUENOS AIRES · ARGENTINA</span><span>PORTFOLIO / SELECTED PRACTICE</span><span>2026</span></div>
        <h1 class="hero__title" aria-label="Diego Cano"><span>DIEGO</span><span>CA<em>N</em>O</span></h1>
        <div class="hero__bottom">
          <p class="hero__intro">I design software systems, intelligent products and physical ideas with the same principle: <em>complexity must become legible.</em></p>
          <a class="hero__scroll" href="#position"><span>ENTER THE WORK</span><i>↓</i></a>
        </div>
      </section>

      <section id="position" class="position">
        <div class="position__aside"><span>PRACTICE / 01</span><p>Engineering is the structure. Design determines what the structure communicates.</p></div>
        <p class="position__statement">
          <span v-for="word in 'I work between software architecture artificial intelligence interaction and physical design. Not as separate identities, but as different ways of making systems understandable.'.split(' ')" :key="`${word}-${Math.random()}`" class="word">{{ word }} </span>
        </p>
        <div class="position__facts" data-reveal>
          <div><span>CORE</span><strong>Distributed systems · AI products · integrations</strong></div>
          <div><span>METHOD</span><strong>Research · architecture · prototype · production</strong></div>
          <div><span>LANGUAGES</span><strong>Python · TypeScript · Java · Rust</strong></div>
        </div>
      </section>

      <section id="experience" class="experience">
        <header class="experience__intro" data-reveal>
          <span>PROFESSIONAL TRAJECTORY</span>
          <h2>Systems are built<br />through <em>continuity.</em></h2>
          <p>The portfolio does not replace the CV. It gives the work context: responsibility, progression and the environments in which each system had to operate.</p>
        </header>

        <div class="experience__timeline">
          <article v-for="experience in experiences" :key="`${experience.period}-${experience.role}`" class="experience-entry">
            <div class="experience-entry__period"><span>{{ experience.period }}</span><i /></div>
            <div class="experience-entry__body">
              <span>{{ experience.company }}</span>
              <h3>{{ experience.role }}</h3>
              <p>{{ experience.summary }}</p>
              <ul><li v-for="item in experience.focus" :key="item">{{ item }}</li></ul>
            </div>
          </article>
        </div>
      </section>

      <section id="systems" class="systems">
        <header class="systems__intro" data-reveal>
          <span>SELECTED TECHNICAL WORK</span>
          <h2>Not exhibits.<br /><em>Working systems.</em></h2>
          <p>The technical projects are presented as case narratives and architectures. They are deliberately not placed inside the visual-art gallery.</p>
        </header>

        <article v-for="(project, index) in projects" :key="project.id" class="system-story" :style="{ '--accent': project.accent }">
          <div class="system-story__visual" aria-hidden="true">
            <div class="system-visual">
              <div class="system-visual__grid" />
              <div class="system-visual__layer layer-a" />
              <div class="system-visual__layer layer-b" />
              <div class="system-visual__layer layer-c" />
              <div class="system-flow-line line-a" />
              <div class="system-flow-line line-b" />
              <i class="system-node node-a" /><i class="system-node node-b" /><i class="system-node node-c" /><i class="system-node node-d" />
              <strong>{{ project.code }}</strong>
              <span>{{ project.field }}</span>
              <small>0{{ index + 1 }} / 0{{ projects.length }}</small>
            </div>
          </div>
          <div class="system-story__copy">
            <span>{{ project.id }} · {{ project.field }}</span>
            <h3>{{ project.title }}</h3>
            <p class="system-story__premise">{{ project.premise }}</p>
            <p>{{ project.detail }}</p>
            <div class="system-story__outcome"><span>OUTCOME</span><strong>{{ project.outcome }}</strong></div>
            <ul><li v-for="item in project.stack" :key="item">{{ item }}</li></ul>
          </div>
        </article>
      </section>

      <div id="visual-practice"><ArtExhibition /></div>

      <section id="assistant" class="assistant-chapter">
        <header class="assistant-chapter__intro" data-reveal>
          <span>PROFESSIONAL LIAISON</span>
          <h2>The portfolio can<br /><em>answer back.</em></h2>
          <p>The agent remains part of the experience. It answers questions about professional work and prepares administrative actions such as meeting requests while keeping confirmation and scope visible.</p>
        </header>
        <ContactAssistant />
      </section>
    </main>

    <footer class="site-footer">
      <div><strong>DIEGO CANO</strong><span>Software Engineer · AI · Creative Technology</span></div>
      <nav><a href="mailto:diegocanomera@gmail.com">EMAIL ↗</a><a href="https://github.com/dfc-coder" target="_blank" rel="noreferrer">GITHUB ↗</a><a href="https://linkedin.com/in/software-engineer-diegocano" target="_blank" rel="noreferrer">LINKEDIN ↗</a></nav>
      <span>BUENOS AIRES · 2026</span>
    </footer>
  </div>
</template>
