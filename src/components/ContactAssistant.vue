<script setup lang="ts">
import { nextTick, ref } from "vue";

type Message = { role: "assistant" | "visitor"; text: string };
type ActionMode = "meeting" | "followup" | null;

const prompts = [
  "¿Qué experiencia tiene?",
  "¿En qué proyectos trabajó?",
  "Consultar disponibilidad",
  "Preparar un seguimiento",
];

const messages = ref<Message[]>([
  {
    role: "assistant",
    text: "Soy el asistente profesional de Diego. Puedo responder sobre experiencia y proyectos, consultar disponibilidad de demostración y preparar acciones administrativas para revisión.",
  },
]);

const input = ref("");
const thinking = ref(false);
const actionMode = ref<ActionMode>(null);
const confirmed = ref(false);
const transcript = ref<HTMLElement | null>(null);

const scrollMessages = async () => {
  await nextTick();
  transcript.value?.scrollTo({ top: transcript.value.scrollHeight, behavior: "smooth" });
};

const respond = (question: string): string => {
  if (/experien|trayectoria|trabaj/i.test(question)) {
    return "Diego trabaja como AI Engineer en aiRoss y anteriormente desarrolló productos de AI aplicada e ingeniería full-stack. Su foco está en sistemas privados de IA, agentes, integraciones y productos distribuidos.";
  }
  if (/tecnolog|stack|herramient/i.test(question)) {
    return "Su stack principal combina Python, TypeScript, Java y Rust, con experiencia en FastAPI, Vue, sistemas RAG, agentes, APIs, bases vectoriales, infraestructura local y cloud.";
  }
  return "Los casos seleccionados incluyen extracción documental privada, un agente NL→SQL con guardrails, herramientas financieras mediante MCP y búsqueda semántica orientada a intención.";
};

const send = async (value = input.value) => {
  const question = value.trim();
  if (!question || thinking.value) return;

  messages.value.push({ role: "visitor", text: question });
  input.value = "";
  actionMode.value = null;
  confirmed.value = false;
  await scrollMessages();
  thinking.value = true;

  window.setTimeout(async () => {
    if (/dispon|agenda|horario/i.test(question)) {
      messages.value.push({
        role: "assistant",
        text: "La disponibilidad de demostración muestra ventanas el martes y jueves por la tarde, hora de Buenos Aires. Podés preparar una solicitud concreta abajo; nada se envía sin confirmación final.",
      });
      actionMode.value = "meeting";
    } else if (/reuni|coordinar|agendar|calendar/i.test(question)) {
      messages.value.push({
        role: "assistant",
        text: "Puedo preparar una reunión con fecha, zona horaria, motivo y contacto. La acción queda en estado de revisión hasta una confirmación explícita.",
      });
      actionMode.value = "meeting";
    } else if (/seguim|follow|recordatorio|correo|mail/i.test(question)) {
      messages.value.push({
        role: "assistant",
        text: "Puedo preparar un seguimiento administrativo con destinatario, asunto y contexto. Esta demostración sólo genera la solicitud; no envía mensajes ni almacena datos.",
      });
      actionMode.value = "followup";
    } else {
      messages.value.push({ role: "assistant", text: respond(question) });
    }

    thinking.value = false;
    await scrollMessages();
  }, 520);
};

const confirmAction = () => {
  confirmed.value = true;
  const text = actionMode.value === "meeting"
    ? "Solicitud preparada. En una integración real se mostraría el resumen final y recién después de tu confirmación se crearía el evento de Calendar."
    : "Seguimiento preparado. En una integración real se mostraría el borrador completo y recién después de tu confirmación se enviaría el correo.";
  messages.value.push({ role: "assistant", text });
  actionMode.value = null;
  void scrollMessages();
};
</script>

<template>
  <div class="assistant-shell">
    <aside class="assistant-manifest">
      <div class="assistant-status"><i /><span>AGENT / CONTROLLED ACTIONS</span></div>
      <h3>Information first.<br /><em>Actions with consent.</em></h3>
      <p>The agent separates answers from external actions. It can explain professional work immediately, while meetings and follow-ups remain reviewable before any integration writes data.</p>
      <ul>
        <li><span>01</span>Verified professional context</li>
        <li><span>02</span>Availability and meeting preparation</li>
        <li><span>03</span>Administrative follow-up drafts</li>
        <li><span>04</span>Explicit confirmation before writes</li>
      </ul>
    </aside>

    <section class="chat-console" aria-label="Professional and administrative agent demo">
      <header>
        <div class="console-id"><span>DC—A/02</span><b>PROFESSIONAL LIAISON</b></div>
        <div class="console-scope"><i />BOUNDED ACTION MODE</div>
      </header>

      <div ref="transcript" class="chat-transcript" aria-live="polite">
        <div v-for="(message, index) in messages" :key="`${message.role}-${index}`" :class="['chat-message', message.role]">
          <span>{{ message.role === "assistant" ? "DC—A" : "VISITOR" }}</span>
          <p>{{ message.text }}</p>
        </div>
        <div v-if="thinking" class="chat-thinking"><i /><i /><i /></div>

        <form v-if="actionMode === 'meeting' && !confirmed" class="meeting-card" @submit.prevent="confirmAction">
          <span>PREPARE MEETING / REVIEW REQUIRED</span>
          <label>PREFERRED DATE<input type="date" required /></label>
          <label>TIME WINDOW<select required><option>Tuesday · 15:00–18:00</option><option>Thursday · 14:00–18:00</option><option>Propose another time</option></select></label>
          <label>TIME ZONE<select required><option>Buenos Aires · GMT−3</option><option>Madrid · GMT+2</option><option>New York · GMT−4</option></select></label>
          <label>CONTACT EMAIL<input type="email" placeholder="name@company.com" required /></label>
          <label class="meeting-card__wide">MEETING PURPOSE<input type="text" placeholder="Project, interview or technical discussion" required /></label>
          <button type="submit">REVIEW REQUEST →</button>
        </form>

        <form v-if="actionMode === 'followup' && !confirmed" class="meeting-card" @submit.prevent="confirmAction">
          <span>PREPARE FOLLOW-UP / REVIEW REQUIRED</span>
          <label>RECIPIENT<input type="email" placeholder="recipient@company.com" required /></label>
          <label>SUBJECT<input type="text" placeholder="Follow-up subject" required /></label>
          <label class="meeting-card__wide">CONTEXT<input type="text" placeholder="What should the follow-up reference?" required /></label>
          <button type="submit">REVIEW DRAFT →</button>
        </form>
      </div>

      <div class="chat-prompts">
        <button v-for="prompt in prompts" :key="prompt" type="button" @click="send(prompt)">{{ prompt }}</button>
      </div>

      <form class="chat-input" @submit.prevent="send()">
        <label for="assistant-question">Ask about work or prepare an administrative action</label>
        <input id="assistant-question" v-model="input" autocomplete="off" placeholder="Experience, projects, availability or follow-up…" />
        <button type="submit" :disabled="!input.trim() || thinking" aria-label="Send question">↗</button>
      </form>

      <footer><span>SESSION MEMORY / EPHEMERAL</span><span>DEMO MODE · NO EXTERNAL WRITE</span></footer>
    </section>
  </div>
</template>
