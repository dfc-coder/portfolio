<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import CreativeGallery from "./components/CreativeGallery.vue";

const projects = [
  ["01", "DOC / AI", "AI PRODUCT · BANKING · ON-PREMISE", "Secure Document Extractor", "Sensitive PDFs and images become validated, auditable financial data without leaving isolated infrastructure.", "Zero external API dependency", "signal", "2026"],
  ["02", "NL / SQL", "AGENTS · NLP · DATA SECURITY", "NL-to-SQL Agent", "A schema-aware agent that resolves ambiguity, orchestrates tools and produces safe executable queries.", "Grounded, guarded SQL", "cobalt", "2026"],
  ["03", "MCP / 03", "FINTECH · MCP · MULTI-AGENT", "Financial MCP Server", "Real-time market tools, technical indicators and multi-agent analysis shaped into portfolio recommendations.", "Signals into decisions", "ink", "2025"],
  ["04", "SEARCH", "SEARCH · E-COMMERCE · AI", "Semantic Shopping Assistant", "An AI shopping assistant that understands intent and searches a catalogue of more than 50,000 products.", "60% faster · 40% more accurate", "coral", "2025"],
  ["05", "RAG / AWS", "RAG · INSURANCE · AWS", "Insurance Knowledge Assistant", "AWS S3 ingestion, document indexing and retrieval connected to a dependable answer-generation API.", "Knowledge made operational", "ice", "2025"],
  ["06", "AGENT / RAG", "PLATFORM · RAG · KNOWLEDGE", "Multi-Agent RAG Platform", "A multi-agent platform connected to internal knowledge bases for faster onboarding and technical diagnosis.", "−30% onboarding · −40% debugging", "sand", "2025"],
] as const;

const cleanup: Array<() => void> = [];
onMounted(() => {
  gsap.registerPlugin(ScrollTrigger);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduced) {
    gsap.timeline({ defaults: { ease: "power4.out" } })
      .from(".intro-screen h1 span", { yPercent: 110, duration: 0.85, stagger: 0.08 })
      .to(".intro-screen", { clipPath: "inset(0 0 100% 0)", duration: 1.05, delay: 0.3, ease: "power3.inOut" })
      .set(".intro-screen", { display: "none" })
      .from(".hero-line", { yPercent: 100, opacity: 0, duration: 1, stagger: 0.12 }, "-=.55");
    gsap.utils.toArray<HTMLElement>(".reveal-item").forEach((element) => gsap.from(element, { y: 70, opacity: 0, duration: 1, scrollTrigger: { trigger: element, start: "top 82%" } }));
  } else gsap.set(".intro-screen", { display: "none" });
  gsap.to(".header-progress", { scaleX: 1, ease: "none", scrollTrigger: { start: 0, end: "max", scrub: 0.2 } });
  if (matchMedia("(pointer:fine)").matches) {
    const cursor = document.querySelector<HTMLElement>(".cursor");
    let x = -100, y = -100, cx = -100, cy = -100, frame = 0;
    const move = (event: PointerEvent) => { x = event.clientX; y = event.clientY; };
    const render = () => { if (cursor) { cx += (x - cx) * 0.25; cy += (y - cy) * 0.25; cursor.style.transform = `translate3d(${cx - 17}px,${cy - 17}px,0)`; } frame = requestAnimationFrame(render); };
    addEventListener("pointermove", move, { passive: true }); frame = requestAnimationFrame(render);
    cleanup.push(() => { removeEventListener("pointermove", move); cancelAnimationFrame(frame); });
  }
});
onBeforeUnmount(() => { cleanup.forEach((fn) => fn()); ScrollTrigger.getAll().forEach((trigger) => trigger.kill()); });
</script>

<template>
  <div class="noise" aria-hidden="true" /><div class="cursor" aria-hidden="true"><i class="cursor-ring" /></div>
  <div class="intro-screen" aria-hidden="true"><span>DC® / 2026</span><h1><span>IDEAS NEED</span><span>FORM + FUNCTION.</span></h1><span>DESIGN × TECHNOLOGY</span></div>
  <header class="site-header"><a class="brand" href="#top" aria-label="Diego Cano — home"><b>DC</b><span>Designer<br>Developer</span></a><nav class="nav"><a href="#work">Work</a><a href="#about">Profile</a><a href="#contact">Contact</a></nav><a class="availability" href="#contact"><i />Available for selected work</a><span class="header-progress" /></header>
  <main id="top"><section class="hero"><div class="hero-meta"><span>BUENOS AIRES / ARG</span><span>PRODUCT · VISUAL · CODE</span><span>© 2026</span></div><h1><span class="hero-line">DESIGNER</span><span class="hero-line hero-line--alt"><em>&amp;</em> DEVELOPER</span></h1><div class="hero-foot"><p>I shape complex technology into clear, useful and memorable digital products.</p><a class="round-link" href="#work"><span>Selected work</span><span>↘</span></a></div><div class="hero-stamp"><span>THINK</span><b>↗</b><span>MAKE</span></div></section>
    <div class="ticker"><div class="ticker-track"><span>DESIGN SYSTEMS ✦ AI PRODUCTS ✦ CREATIVE DEVELOPMENT ✦ INTERACTION DESIGN ✦</span><span>DESIGN SYSTEMS ✦ AI PRODUCTS ✦ CREATIVE DEVELOPMENT ✦ INTERACTION DESIGN ✦</span></div></div>
    <section id="work" class="work"><div class="section-intro reveal-item"><span>01 / SELECTED WORK</span><h2>Built to be used.<br><em>Designed to be felt.</em></h2><p>Strategy, interface and engineering working as one discipline.</p></div><div class="project-grid"><article v-for="(project, index) in projects" :key="project[0]" :class="['project-card', project[6], { 'project-card--wide': index === 0 || index === 5 }]"><div class="project-top"><span>{{ project[0] }}</span><span>{{ project[2] }}</span><span>{{ project[7] }}</span></div><div class="project-art"><i /><i /><i /><strong>{{ project[1] }}</strong></div><div class="project-copy"><h3>{{ project[3] }}</h3><div><b>{{ project[5] }}</b><p>{{ project[4] }}</p></div><span class="project-arrow">↗</span></div></article></div></section>
    <section id="about" class="profile"><div class="profile-label">02 / PROFILE</div><div class="profile-main reveal-item"><p class="profile-lead">I work where <em>design judgment</em> meets <em>technical depth.</em></p><p class="profile-note">From the first messy question to a production-ready system, I connect research, product thinking, visual language and code.</p></div><CreativeGallery /><div class="capability-grid"><div><span>01</span><h3>Product design</h3><p>Flows, information architecture, prototypes and design systems.</p></div><div><span>02</span><h3>Creative development</h3><p>Expressive, accessible interfaces built for real-world use.</p></div><div><span>03</span><h3>AI systems</h3><p>Agents, retrieval and intelligent workflows with visible reasoning.</p></div><div><span>04</span><h3>Full-stack delivery</h3><p>From interaction details to resilient product architecture.</p></div></div></section>
    <section id="contact" class="contact"><span>03 / START A CONVERSATION</span><h2>Have a difficult<br>idea? <em>Good.</em></h2><div class="contact-row"><p>Let’s turn it into something clear,<br>useful and impossible to ignore.</p><a href="mailto:diegocanomera@gmail.com">diegocanomera@gmail.com ↗</a></div></section></main>
  <footer><strong>Diego Cano</strong><span>Designer &amp; Developer</span><div><a href="https://github.com/dfc-coder">GitHub ↗</a><a href="https://linkedin.com/in/software-engineer-diegocano">LinkedIn ↗</a></div><span>Buenos Aires · 2026</span></footer>
</template>
