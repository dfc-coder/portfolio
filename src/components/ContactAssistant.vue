<script setup lang="ts">
import { nextTick, ref } from "vue";

type Message = { role: "assistant" | "visitor"; text: string };

const prompts = ["¿En qué proyectos trabajó?", "¿Qué tecnologías usa?", "Quiero coordinar una reunión"];
const messages = ref<Message[]>([
  { role: "assistant", text: "Hola. Soy el asistente profesional de Diego. Puedo responder sobre su experiencia pública o ayudarte a preparar una reunión." },
]);
const input = ref("");
const thinking = ref(false);
const scheduling = ref(false);
const confirmed = ref(false);
const transcript = ref<HTMLElement | null>(null);

const responses = [
  "Diego trabaja en la intersección entre AI aplicada, producto digital y diseño. Sus casos incluyen extracción documental segura, agentes NL→SQL, herramientas MCP y búsqueda semántica.",
  "Su práctica combina Vue, TypeScript, Python, Java, LangChain, RAG y sistemas de datos; además trabaja con electrónica, IoT, diseño industrial y modelado 3D.",
];

const scrollMessages = async () => {
  await nextTick();
  transcript.value?.scrollTo({ top: transcript.value.scrollHeight, behavior: "smooth" });
};

const send = async (value = input.value) => {
  const question = value.trim();
  if (!question || thinking.value) return;
  messages.value.push({ role: "visitor", text: question });
  input.value = "";
  await scrollMessages();
  thinking.value = true;
  window.setTimeout(async () => {
    if (/reuni|calendar|coordinar|agenda/i.test(question)) {
      messages.value.push({ role: "assistant", text: "Puedo consultar disponibilidad y preparar una invitación. La reunión solo se crea después de que confirmes fecha, zona horaria y datos de contacto." });
      scheduling.value = true;
    } else if (/tecnolog|stack|herramient/i.test(question)) {
      messages.value.push({ role: "assistant", text: responses[1] });
    } else {
      messages.value.push({ role: "assistant", text: responses[0] });
    }
    thinking.value = false;
    await scrollMessages();
  }, 620);
};

const confirmMeeting = () => {
  confirmed.value = true;
  messages.value.push({ role: "assistant", text: "Modo seguro: antes de escribir en Calendar se pedirá una confirmación final. Esta demostración no envía ni almacena información." });
  void scrollMessages();
};
</script>

<template>
  <div class="assistant-shell">
    <aside class="assistant-manifest">
      <div class="assistant-status"><i /><span>ASISTENTE / SAFE MODE</span></div>
      <h3>Una puerta de entrada,<br><em>con límites visibles.</em></h3>
      <p>Responderá solamente con información profesional aprobada. La memoria será temporal por visitante y las acciones externas requerirán confirmación explícita.</p>
      <ul>
        <li><span>01</span>CV y proyectos verificados</li>
        <li><span>02</span>Sin credenciales en el navegador</li>
        <li><span>03</span>Calendar con consentimiento</li>
        <li><span>04</span>Memoria aislada y temporal</li>
      </ul>
    </aside>

    <section class="chat-console" aria-label="Preview del asistente profesional">
      <header>
        <div class="console-id"><span>DC—A/01</span><b>PROFESSIONAL LIAISON</b></div>
        <div class="console-scope"><i />KNOWLEDGE BOUNDED</div>
      </header>

      <div ref="transcript" class="chat-transcript" aria-live="polite">
        <div v-for="(message, index) in messages" :key="`${message.role}-${index}`" :class="['chat-message', message.role]">
          <span>{{ message.role === "assistant" ? "DC—A" : "VISITOR" }}</span>
          <p>{{ message.text }}</p>
        </div>
        <div v-if="thinking" class="chat-thinking"><i /><i /><i /></div>

        <form v-if="scheduling && !confirmed" class="meeting-card" @submit.prevent="confirmMeeting">
          <span>PREPARAR REUNIÓN / REQUIERE CONFIRMACIÓN</span>
          <label>FECHA PREFERIDA<input type="date" required></label>
          <label>ZONA HORARIA<select required><option>Buenos Aires · GMT−3</option><option>Madrid · GMT+2</option><option>New York · GMT−4</option></select></label>
          <label>EMAIL<input type="email" placeholder="tu@email.com" required></label>
          <button type="submit">REVISAR SOLICITUD →</button>
        </form>
      </div>

      <div class="chat-prompts">
        <button v-for="prompt in prompts" :key="prompt" type="button" @click="send(prompt)">{{ prompt }}</button>
      </div>

      <form class="chat-input" @submit.prevent="send()">
        <label for="assistant-question">Escribí una pregunta profesional</label>
        <input id="assistant-question" v-model="input" autocomplete="off" placeholder="Preguntá sobre experiencia, proyectos o disponibilidad…">
        <button type="submit" :disabled="!input.trim() || thinking" aria-label="Enviar">↗</button>
      </form>

      <footer><span>SESSION MEMORY / EPHEMERAL</span><span>NO DATA SENT · SAFE DEMO</span></footer>
    </section>
  </div>
</template>
