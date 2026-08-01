<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import LivingMatter from "./components/LivingMatter.vue";
import CreativeGallery from "./components/CreativeGallery.vue";
import ProjectVault from "./components/ProjectVault.vue";
import ContactAssistant from "./components/ContactAssistant.vue";

const root = ref<HTMLElement | null>(null);
let context: gsap.Context | null = null;
let media: gsap.MatchMedia | null = null;

onMounted(async () => {
  await nextTick();
  gsap.registerPlugin(ScrollTrigger);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  context = gsap.context(() => {
    if (reduced) {
      gsap.set(".loader", { display: "none" });
    } else {
      gsap.timeline({ defaults: { ease: "power4.out" } })
        .from(".loader-signal i", { scaleY: 0, transformOrigin: "bottom", duration: 0.8, stagger: 0.045 })
        .from(".loader-copy span", { yPercent: 120, duration: 0.72, stagger: 0.055 }, "-=.42")
        .to(".loader-copy", { opacity: 0, y: -40, duration: 0.5, delay: 0.28, ease: "power2.in" })
        .to(".loader", { clipPath: "inset(0 0 100% 0)", duration: 1.05, ease: "expo.inOut" }, "-=.14")
        .set(".loader", { display: "none" })
        .from(".hero-title .title-inner", { yPercent: 112, rotate: 2.5, duration: 1.2, stagger: 0.1 }, "-=.56")
        .from(".hero-kicker, .hero-statement, .hero-scroll, .discipline-orbit", { opacity: 0, y: 24, duration: 0.85, stagger: 0.08 }, "-=.74");
    }

    gsap.to(".scroll-progress", {
      scaleX: 1,
      ease: "none",
      scrollTrigger: { start: 0, end: "max", scrub: 0.25 },
    });

    if (!reduced) {
      gsap.to(".hero-title .title-line:first-child", {
        xPercent: -10,
        scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.8 },
      });
      gsap.to(".hero-title .title-line:last-child", {
        xPercent: 11,
        scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.8 },
      });
      gsap.to(".discipline-orbit", {
        rotation: 150,
        scale: 0.72,
        scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 1 },
      });
      gsap.to(".hero-interface", {
        yPercent: 18,
        opacity: 0,
        scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom 20%", scrub: 0.8 },
      });

      gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((element) => {
        gsap.from(element, {
          y: 80,
          opacity: 0,
          duration: 1.15,
          ease: "power3.out",
          scrollTrigger: { trigger: element, start: "top 86%" },
        });
      });

      gsap.utils.toArray<HTMLElement>(".about-lead .word").forEach((word, index) => {
        gsap.from(word, {
          opacity: 0.09,
          y: 22,
          scrollTrigger: { trigger: word, start: `top ${90 - (index % 5) * 2}%`, end: "top 55%", scrub: 0.35 },
        });
      });

      gsap.to(".chapter-signal", {
        rotation: 280,
        scrollTrigger: { trigger: ".about-intro", start: "top bottom", end: "bottom top", scrub: 0.6 },
      });

      media = gsap.matchMedia();
      media.add("(min-width: 821px)", () => {
        const vault = document.querySelector<HTMLElement>(".project-vault");
        const rail = document.querySelector<HTMLElement>(".project-rail");
        if (!vault || !rail) return;
        const distance = () => Math.max(0, rail.scrollWidth - innerWidth);
        gsap.to(rail, {
          x: () => -distance(),
          ease: "none",
          scrollTrigger: {
            trigger: vault,
            start: "top top",
            end: () => `+=${distance() + innerHeight * 0.65}`,
            pin: true,
            scrub: 0.7,
            invalidateOnRefresh: true,
          },
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
    <div class="loader" aria-hidden="true">
      <div class="loader-top"><span>DIEGO CANO / PORTFOLIO 2026</span><span>INITIALIZING LIVING SYSTEM</span></div>
      <div class="loader-signal"><i v-for="n in 28" :key="n" /></div>
      <div class="loader-copy"><span>SYSTEMS</span><span>WITH A</span><span><em>HUMAN</em> EDGE.</span></div>
    </div>

    <LivingMatter />
    <div class="grain" aria-hidden="true" />
    <div class="edge-vignette" aria-hidden="true" />

    <header class="site-header">
      <a class="brand" href="#top" aria-label="Diego Cano, inicio"><b>DC</b><span>CREATIVE TECHNOLOGIST<br>+ INDUSTRIAL DESIGNER</span></a>
      <nav aria-label="Navegación principal">
        <a href="#about"><span>01</span>QUIÉN SOY</a>
        <a href="#work"><span>02</span>PROYECTOS</a>
        <a href="#contact"><span>03</span>CONTACTO</a>
      </nav>
      <div class="header-signal"><i />BAI · GMT−3</div>
      <div class="scroll-progress" />
    </header>

    <main id="top">
      <section class="hero">
        <div class="hero-interface" aria-hidden="true">
          <span class="coordinate coordinate-a">X / 034.61</span>
          <span class="coordinate coordinate-b">Y / 118.04</span>
          <span class="coordinate coordinate-c">MATTER / ACTIVE</span>
          <span class="cross cross-a" /><span class="cross cross-b" />
          <div class="hero-axis axis-horizontal" /><div class="hero-axis axis-vertical" />
        </div>

        <p class="hero-kicker"><span>PORTFOLIO / CV / AUTOBIOGRAPHICAL SYSTEM</span><span>BUENOS AIRES · 2026</span></p>

        <h1 class="hero-title" aria-label="Diego Cano">
          <span class="title-line"><span class="title-inner">DIEGO</span></span>
          <span class="title-line title-offset"><span class="title-inner">CA<em>N</em>O</span></span>
        </h1>

        <div class="discipline-orbit" aria-hidden="true">
          <svg viewBox="0 0 160 160"><defs><path id="orbit" d="M80,80 m-62,0 a62,62 0 1,1 124,0 a62,62 0 1,1 -124,0" /></defs><text><textPath href="#orbit">CODE · OBJECTS · INTELLIGENCE · SYSTEMS · </textPath></text></svg>
          <i /><b>∿</b>
        </div>

        <div class="hero-bottom">
          <p class="hero-statement">Diseño inteligencia, interfaces y objetos.<br><em>Una práctica entre código, materia y curiosidad.</em></p>
          <div class="hero-facets" aria-label="Áreas de práctica">
            <span>AI / SOFTWARE</span><span>ELECTRÓNICA / IoT</span><span>DISEÑO INDUSTRIAL</span><span>3D / IMAGEN</span>
          </div>
          <a class="hero-scroll" href="#about"><span>ENTRAR AL ATELIER</span><i>↓</i></a>
        </div>
      </section>

      <section id="about" class="about-chapter">
        <div class="about-intro">
          <div class="chapter-code"><span>01</span><i />QUIÉN SOY</div>
          <div class="chapter-signal" aria-hidden="true"><i /><i /><i /><b>DC</b></div>
          <p class="about-lead">
            <span v-for="word in 'Pienso como ingeniero pero observo como diseñador. Me interesan los sistemas que se pueden tocar, comprender y sentir.'.split(' ')" :key="word" class="word">{{ word }} </span>
          </p>
          <div class="about-note" data-reveal>
            <span>STATEMENT / 01</span>
            <p>Soy Diego Cano. Trabajo con AI y software, pero mi lenguaje también se formó entre circuitos, muebles, modelos 3D, interfaces y preguntas sobre cómo funcionan las cosas.</p>
          </div>
        </div>

        <div class="practice-constellation" data-reveal>
          <article><span>01 / LOGIC</span><h2>Inteligencia<br><em>aplicada.</em></h2><p>Agentes, RAG, datos y productos donde la complejidad se vuelve una experiencia legible.</p></article>
          <article><span>02 / SIGNAL</span><h2>Electrónica<br><em>e IoT.</em></h2><p>Prototipos, sensores y curiosidad por el momento exacto en que el software entra al mundo físico.</p></article>
          <article><span>03 / MATTER</span><h2>Objetos<br><em>y espacio.</em></h2><p>Diseño industrial, mobiliario, materialidad y modelado 3D como otra forma de pensar sistemas.</p></article>
          <div class="constellation-line" aria-hidden="true" />
        </div>

        <div class="gallery-chapter">
          <div class="gallery-context"><span>ARCHIVO MATERIAL / 10 PIEZAS</span><p>La galería no acompaña el relato.<br><em>Es parte del relato.</em></p></div>
          <CreativeGallery />
        </div>
      </section>

      <ProjectVault />

      <section id="contact" class="contact-chapter">
        <div class="contact-heading">
          <div class="chapter-code"><span>03</span><i />CONTACTO / AI LIAISON</div>
          <h2 data-reveal>La última interfaz<br>es una <em>conversación.</em></h2>
          <p data-reveal>Una capa de contacto viva: responde sobre experiencia profesional, muestra evidencia aprobada y puede preparar una reunión sin operar fuera de sus límites.</p>
        </div>
        <ContactAssistant />
      </section>
    </main>

    <footer class="site-footer">
      <div><span>DIEGO CANO © 2026</span><span>BUILT WITH VUE · THREE.JS · GSAP</span></div>
      <p>SYSTEMS WITH<br><em>A HUMAN EDGE.</em></p>
      <nav><a href="https://github.com/dfc-coder" target="_blank" rel="noreferrer">GITHUB ↗</a><a href="https://linkedin.com/in/software-engineer-diegocano" target="_blank" rel="noreferrer">LINKEDIN ↗</a><a href="mailto:diegocanomera@gmail.com">EMAIL ↗</a></nav>
    </footer>
  </div>
</template>
