<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import AsciiFluidCanvas from "./AsciiFluidCanvas.vue";

type Message = {
  id: number;
  role: "user" | "agent";
  text: string;
  x: number;
  y: number;
  width: number;
};

const input = ref("");
const thinking = ref(false);
const messageId = ref(3);

const messages = ref<Message[]>([
  {
    id: 1,
    role: "user",
    text: "What has Diego built with RAG?",
    x: 11,
    y: 16,
    width: 28,
  },
  {
    id: 2,
    role: "agent",
    text: "Diego has used Retrieval Augmented Generation in several production-grade systems: guarded NL→SQL, private document intelligence and intent-aware semantic search.",
    x: 62,
    y: 27,
    width: 31,
  },
  {
    id: 3,
    role: "user",
    text: "Can you compare their architectures?",
    x: 15,
    y: 62,
    width: 31,
  },
]);

const canSend = computed(() => input.value.trim().length > 0 && !thinking.value);

const responseFor = (question: string): string => {
  if (/rag|retrieval|architecture|compare/i.test(question)) {
    return "They share the same principle: retrieval narrows context before generation. NL→SQL retrieves only relevant schema and rules, document intelligence ranks evidence before extraction, and semantic search combines structured attributes with embeddings before ranking.";
  }

  if (/experience|career|work/i.test(question)) {
    return "Diego works across applied AI, distributed systems and integration architecture, with a focus on production APIs, RAG, agents, cloud workflows and maintainable software systems.";
  }

  if (/project|build|system/i.test(question)) {
    return "Selected systems include private document extraction, guarded NL→SQL, a financial MCP server and intent-aware semantic search. Each project emphasizes traceability, explicit contracts and production constraints.";
  }

  if (/skill|stack|technology/i.test(question)) {
    return "Core technologies include Python, TypeScript, Java, FastAPI, local LLMs, RAG, MCP, AWS and distributed integration patterns.";
  }

  if (/contact|available|availability|meeting/i.test(question)) {
    return "You can use this interface to understand Diego's work and then continue through the contact details provided in the portfolio.";
  }

  return "Ask about Diego's experience, projects, architecture, stack or applied AI work. I answer only from the portfolio context.";
};

const positions = [
  { x: 58, y: 56, width: 34 },
  { x: 12, y: 36, width: 31 },
  { x: 60, y: 18, width: 31 },
  { x: 16, y: 68, width: 33 },
];

const addMessage = async (role: Message["role"], text: string) => {
  messageId.value += 1;
  const slot = positions[messageId.value % positions.length];
  messages.value.push({ id: messageId.value, role, text, ...slot });
  if (messages.value.length > 5) messages.value.shift();
  await nextTick();
};

const send = async () => {
  const question = input.value.trim();
  if (!question || thinking.value) return;

  input.value = "";
  await addMessage("user", question);
  thinking.value = true;

  window.setTimeout(async () => {
    await addMessage("agent", responseFor(question));
    thinking.value = false;
  }, 420);
};
</script>

<template>
  <section class="jarvis-ui" aria-label="Agent 0 portfolio interface">
    <header class="jarvis-ui__header">
      <div class="jarvis-ui__title">
        <strong>DC / AGENT 0</strong>
        <span>SECTION 05 / THE INTERFACE</span>
      </div>
      <div class="jarvis-ui__status" aria-label="Agent status">
        <span class="jarvis-ui__status-dot" />
        <span>{{ thinking ? "THINKING" : "ONLINE" }}</span>
      </div>
    </header>

    <div class="jarvis-ui__field">
      <AsciiFluidCanvas :active="thinking" />

      <article
        v-for="message in messages"
        :key="message.id"
        :class="['jarvis-bubble', `jarvis-bubble--${message.role}`]"
        :style="{
          left: `${message.x}%`,
          top: `${message.y}%`,
          width: `${message.width}%`,
        }"
      >
        <div class="jarvis-bubble__meta">
          <span>{{ message.role === "agent" ? "AGENT 0" : "YOU" }}</span>
          <i />
        </div>
        <p>{{ message.text }}</p>
      </article>

      <div v-if="thinking" class="jarvis-thinking" aria-live="polite">
        <span>AGENT 0</span>
        <i /><i /><i />
      </div>
    </div>

    <form class="jarvis-input" @submit.prevent="send">
      <span>ASK /</span>
      <label for="jarvis-question" class="sr-only">Ask Agent 0 about Diego's work</label>
      <input
        id="jarvis-question"
        v-model="input"
        type="text"
        autocomplete="off"
        placeholder="Type your question about Diego's work..."
      />
      <button type="submit" :disabled="!canSend" aria-label="Send question">→</button>
    </form>
  </section>
</template>
