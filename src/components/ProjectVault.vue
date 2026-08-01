<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

type ArchitectureNode = { label: string; detail: string };
type Project = {
  id: string;
  code: string;
  title: string;
  field: string;
  year: string;
  premise: string;
  narrative: string;
  contribution: string;
  stack: string[];
  architecture: ArchitectureNode[];
  flow: string[];
  accent: string;
};

const projects: Project[] = [
  {
    id: "01",
    code: "DOC—AI",
    title: "Secure Document Extractor",
    field: "AI PRODUCT / BANKING",
    year: "2026",
    premise: "Convertir documentación sensible en datos financieros verificables, sin convertir la privacidad en una concesión.",
    narrative: "El proyecto parte de una tensión muy humana: necesitamos que una máquina lea rápido, pero no podemos permitir que invente ni exponga información. La experiencia se diseña alrededor de la trazabilidad; cada dato conserva su relación con la fuente y cada excepción puede revisarse.",
    contribution: "Arquitectura de producto, pipeline de extracción, validación y experiencia de revisión.",
    stack: ["Python", "Vision / OCR", "LLM local", "Schemas", "Audit trail"],
    architecture: [
      { label: "INGESTA", detail: "PDF · imágenes · lotes" },
      { label: "LECTURA", detail: "OCR + layout" },
      { label: "EXTRACCIÓN", detail: "modelo aislado" },
      { label: "CONTROL", detail: "schema + reglas" },
      { label: "SALIDA", detail: "dato + evidencia" },
    ],
    flow: ["Documento", "Segmentación", "Extracción", "Validación", "Revisión humana"],
    accent: "#b9f3d2",
  },
  {
    id: "02",
    code: "NL→SQL",
    title: "Natural Language to SQL",
    field: "AGENTS / DATA SECURITY",
    year: "2026",
    premise: "Permitir que una pregunta cotidiana llegue a los datos sin entregar acceso irrestricto a la base.",
    narrative: "No se trata solamente de traducir palabras a SQL. El sistema debe reconocer ambigüedad, comprender un esquema cambiante, explicar lo que hará y detenerse cuando una consulta excede sus permisos. La interfaz convierte ese proceso invisible en una secuencia legible.",
    contribution: "Orquestación del agente, recuperación de esquema, guardrails y lenguaje de interacción.",
    stack: ["LangChain", "Python", "PostgreSQL", "RAG", "Policy layer"],
    architecture: [
      { label: "PREGUNTA", detail: "intención + contexto" },
      { label: "SCHEMA RAG", detail: "tablas relevantes" },
      { label: "PLANNER", detail: "plan verificable" },
      { label: "GUARD", detail: "permisos + costo" },
      { label: "RESULTADO", detail: "dato explicado" },
    ],
    flow: ["Pregunta", "Desambiguación", "Plan", "SQL seguro", "Respuesta"],
    accent: "#f16b42",
  },
  {
    id: "03",
    code: "MCP—03",
    title: "Financial MCP Server",
    field: "FINTECH / MULTI-AGENT",
    year: "2025",
    premise: "Transformar señales de mercado dispersas en herramientas reutilizables por agentes especializados.",
    narrative: "El servidor funciona como una mesa de instrumentos. Cada herramienta tiene un contrato estricto, una fuente reconocible y una salida que otro agente puede interpretar. La decisión permanece fuera de la caja negra: se muestran señales, límites y evidencia.",
    contribution: "Diseño de herramientas, contratos MCP, procesamiento de señales y experiencia explicativa.",
    stack: ["MCP", "Python", "Market data", "Tool schemas", "Agents"],
    architecture: [
      { label: "FUENTES", detail: "mercado + cartera" },
      { label: "TOOLS", detail: "contratos MCP" },
      { label: "SEÑALES", detail: "cálculo técnico" },
      { label: "AGENTES", detail: "roles coordinados" },
      { label: "LECTURA", detail: "evidencia + límites" },
    ],
    flow: ["Datos", "Herramientas", "Señales", "Síntesis", "Decisión humana"],
    accent: "#92b7ff",
  },
  {
    id: "04",
    code: "SEARCH",
    title: "Semantic Shopping Assistant",
    field: "SEARCH / E-COMMERCE",
    year: "2025",
    premise: "Buscar productos según la intención real de una persona, no solamente por coincidencia literal.",
    narrative: "Comprar suele empezar con una necesidad incompleta: un uso, una sensación, un presupuesto. El asistente convierte esa conversación en señales de búsqueda y deja que el catálogo responda con alternativas comparables, sin esconder por qué aparece cada resultado.",
    contribution: "Arquitectura de búsqueda, ranking semántico, conversación y evaluación de resultados.",
    stack: ["Embeddings", "Vector search", "TypeScript", "Catalog API", "Evaluation"],
    architecture: [
      { label: "INTENCIÓN", detail: "lenguaje natural" },
      { label: "CONTEXTO", detail: "filtros + catálogo" },
      { label: "RETRIEVAL", detail: "híbrido semántico" },
      { label: "RANKING", detail: "relevancia + reglas" },
      { label: "ELECCIÓN", detail: "comparación clara" },
    ],
    flow: ["Necesidad", "Atributos", "Búsqueda", "Ranking", "Comparación"],
    accent: "#d5b9ff",
  },
];

const selected = ref<number | null>(null);
const tab = ref<"story" | "system">("story");
const activeProject = computed(() => (selected.value === null ? null : projects[selected.value]));

const open = (index: number) => {
  tab.value = "story";
  selected.value = index;
};
const close = () => {
  selected.value = null;
};
const key = (event: KeyboardEvent) => {
  if (event.key === "Escape") close();
  if (selected.value === null) return;
  if (event.key === "ArrowRight") selected.value = (selected.value + 1) % projects.length;
  if (event.key === "ArrowLeft") selected.value = (selected.value - 1 + projects.length) % projects.length;
};

watch(selected, (value) => {
  document.body.classList.toggle("has-overlay", value !== null);
});
onMounted(() => addEventListener("keydown", key));
onBeforeUnmount(() => {
  removeEventListener("keydown", key);
  document.body.classList.remove("has-overlay");
});
</script>

<template>
  <section id="work" class="project-vault">
    <header class="vault-head">
      <div class="chapter-code"><span>02</span><i />PROYECTOS / TRABAJOS</div>
      <p>Casos para leer en dos capas:<br><em>la historia humana y el sistema técnico.</em></p>
      <span class="vault-hint">SCROLL PARA RECORRER →</span>
    </header>

    <div class="project-rail">
      <article
        v-for="(project, index) in projects"
        :key="project.id"
        class="project-artifact"
        :style="{ '--project-accent': project.accent }"
      >
        <button class="artifact-open" type="button" :aria-label="`Abrir caso ${project.title}`" @click="open(index)">
          <span class="artifact-index">{{ project.id }} / {{ String(projects.length).padStart(2, "0") }}</span>
          <div class="artifact-visual" aria-hidden="true">
            <svg viewBox="0 0 820 520" role="presentation">
              <defs>
                <filter :id="`blur-${index}`"><feGaussianBlur stdDeviation="18" /></filter>
                <linearGradient :id="`fade-${index}`" x1="0" x2="1">
                  <stop offset="0" stop-color="currentColor" stop-opacity=".02" />
                  <stop offset="1" stop-color="currentColor" stop-opacity=".8" />
                </linearGradient>
              </defs>
              <g class="artifact-map">
                <path d="M45 276 C185 30 310 486 488 214 S690 92 784 251" />
                <path d="M20 356 C210 124 292 420 470 319 S698 198 815 365" />
                <circle cx="155" cy="185" r="92" />
                <circle cx="594" cy="284" r="152" />
                <circle cx="594" cy="284" r="44" class="solid" />
                <rect x="309" y="95" width="118" height="118" rx="8" />
              </g>
              <ellipse cx="560" cy="270" rx="220" ry="180" :fill="project.accent" opacity=".25" :filter="`url(#blur-${index})`" />
            </svg>
            <span class="artifact-code">{{ project.code }}</span>
            <span class="artifact-axis axis-x" />
            <span class="artifact-axis axis-y" />
          </div>
          <div class="artifact-data"><span>{{ project.field }}</span><span>{{ project.year }}</span></div>
          <h2>{{ project.title }}</h2>
          <div class="artifact-bottom">
            <p>{{ project.premise }}</p>
            <span class="artifact-cta">ABRIR EXPEDIENTE <b>↗</b></span>
          </div>
        </button>
      </article>

      <aside class="vault-end">
        <span>ARCHIVO / 04</span>
        <p>La forma cambia.<br>El criterio permanece.</p>
        <a href="#contact">CONVERSAR SOBRE EL TRABAJO ↘</a>
      </aside>
    </div>
  </section>

  <Teleport to="body">
    <Transition name="dossier">
      <div v-if="activeProject" class="project-dossier" role="dialog" aria-modal="true" :aria-label="activeProject.title">
        <button class="dossier-backdrop" type="button" aria-label="Cerrar proyecto" @click="close" />
        <article :style="{ '--project-accent': activeProject.accent }">
          <header>
            <div><span>{{ activeProject.id }} / CASE STUDY</span><b>{{ activeProject.field }}</b></div>
            <button type="button" @click="close">CERRAR <i>×</i></button>
          </header>

          <div class="dossier-title">
            <span>{{ activeProject.code }} · {{ activeProject.year }}</span>
            <h2>{{ activeProject.title }}</h2>
          </div>

          <nav class="dossier-tabs" aria-label="Vista del proyecto">
            <button :class="{ active: tab === 'story' }" type="button" @click="tab = 'story'">01 · NARRATIVA</button>
            <button :class="{ active: tab === 'system' }" type="button" @click="tab = 'system'">02 · SISTEMA</button>
          </nav>

          <div v-if="tab === 'story'" class="dossier-story">
            <p>{{ activeProject.narrative }}</p>
            <dl>
              <div><dt>APORTE</dt><dd>{{ activeProject.contribution }}</dd></div>
              <div><dt>TECNOLOGÍAS</dt><dd><span v-for="item in activeProject.stack" :key="item">{{ item }}</span></dd></div>
            </dl>
          </div>

          <div v-else class="dossier-system">
            <div class="architecture-map">
              <template v-for="(node, index) in activeProject.architecture" :key="node.label">
                <div class="architecture-node">
                  <span>{{ String(index + 1).padStart(2, "0") }}</span>
                  <strong>{{ node.label }}</strong>
                  <small>{{ node.detail }}</small>
                </div>
                <i v-if="index < activeProject.architecture.length - 1">→</i>
              </template>
            </div>
            <div class="system-flow"><span v-for="item in activeProject.flow" :key="item">{{ item }}</span></div>
            <p>Diagrama conceptual del sistema. Cada caso puede ampliarse con decisiones, restricciones, métricas y enlaces verificables.</p>
          </div>

          <footer>
            <button type="button" @click="selected = (selected! - 1 + projects.length) % projects.length">← ANTERIOR</button>
            <span>{{ activeProject.id }} — {{ String(projects.length).padStart(2, "0") }}</span>
            <button type="button" @click="selected = (selected! + 1) % projects.length">SIGUIENTE →</button>
          </footer>
        </article>
      </div>
    </Transition>
  </Teleport>
</template>
