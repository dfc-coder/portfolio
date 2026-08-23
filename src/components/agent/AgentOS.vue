<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  pulseAgentVisual,
  setAgentVisualPhase,
  type AgentVisualPhase,
} from "../../graphics/stageGraphics";
import { businessAgentProvider } from "./businessAgentProvider";
import { useAgentRuntime, type AgentProvider } from "./useAgentRuntime";

const props = withDefaults(
  defineProps<{
    provider?: AgentProvider;
  }>(),
  { provider: () => businessAgentProvider },
);

const laneEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLInputElement | null>(null);
const tokenBeat = ref(0);
let tokenSequence = 0;
let scrollFrame = 0;

const scrollToBottom = () => {
  scrollFrame = 0;
  const host = laneEl.value;
  if (!host) return;
  host.scrollTop = host.scrollHeight;
};

const scheduleScrollToBottom = () => {
  if (scrollFrame) return;
  scrollFrame = requestAnimationFrame(scrollToBottom);
};

const runtime = useAgentRuntime(props.provider, {
  onMessage: (message) => {
    scheduleScrollToBottom();
    if (message.role === "user") pulseAgentVisual(0.78);
  },
  onToken: () => {
    tokenSequence += 1;
    if (tokenSequence % 4 === 0) tokenBeat.value = tokenSequence;
    pulseAgentVisual(0.22);
    scheduleScrollToBottom();
  },
});

const { messages, draft, focused, busy, error, state, canSend, send, seed } = runtime;

seed([
  {
    role: "agent",
    text: "Hi. I can answer questions about Diego's work and, if useful, help you find a time to talk.",
  },
]);

type Line = { kind: "text"; value: string } | { kind: "item"; index: string; value: string };

const linesOf = (text: string): Line[] =>
  text.split("\n").map((line): Line => {
    const match = /^(\d{2})\s+(.*)$/.exec(line);
    return match
      ? { kind: "item", index: match[1], value: match[2] }
      : { kind: "text", value: line };
  });

const statusLabel = computed(() => {
  if (error.value) return "FAULT";
  if (state.value === "thinking") return "PROCESSING";
  if (state.value === "speaking") return "STREAMING";
  if (state.value === "listening") return "INPUT ACTIVE";
  return "STANDBY";
});

const streamLabel = computed(() =>
  tokenBeat.value === 0
    ? "STREAM 0000"
    : `STREAM ${String(tokenBeat.value % 10000).padStart(4, "0")}`,
);

const syncVisualPhase = () => {
  const phase: AgentVisualPhase = error.value ? "error" : state.value;
  setAgentVisualPhase(phase);
};

const submit = () => {
  void send();
  inputEl.value?.focus();
};

watch(state, syncVisualPhase, { immediate: true });
watch(error, syncVisualPhase);

onMounted(() => {
  void nextTick(scheduleScrollToBottom);
});

onBeforeUnmount(() => {
  if (scrollFrame) cancelAnimationFrame(scrollFrame);
  setAgentVisualPhase("idle");
});
</script>

<template>
  <section
    class="agent-os"
    :data-state="error ? 'error' : state"
    aria-label="Agent — ask about Diego's work"
  >
    <h2 class="sr-only">The interface</h2>

    <aside class="agent-presence" aria-hidden="true">
      <div class="agent-core">
        <div class="agent-core__grid" />
        <div class="agent-core__rings"><i /><i /><i /></div>
        <div class="agent-core__reticle"><i /><i /></div>
        <div class="agent-core__readout">
          <span>REASONING FIELD</span>
          <b>{{ statusLabel }}</b>
          <small>{{ streamLabel }}</small>
        </div>
      </div>

      <div class="agent-presence__label">
        <span class="agent-presence__dot" />
        <span>AGENT CORE</span>
        <b>{{ statusLabel }}</b>
      </div>
    </aside>

    <div class="agent-chat">
      <div class="agent-chat__rail" aria-hidden="true">
        <span>LIVE DIALOGUE</span><i /><b>{{ streamLabel }}</b>
      </div>

      <div ref="laneEl" class="agent-lane" role="log" aria-live="polite">
        <article
          v-for="message in messages"
          :key="message.id"
          class="agent-msg"
          :class="`agent-msg--${message.role}`"
        >
          <div class="agent-msg__meta">
            <span>{{ message.role === "agent" ? "AGENT" : "YOU" }}</span>
            <i />
            <time>{{ message.time }}</time>
          </div>

          <div class="agent-msg__body">
            <template v-for="(line, i) in linesOf(message.text)" :key="i">
              <p v-if="line.kind === 'text' && line.value">{{ line.value }}</p>
              <span v-else-if="line.kind === 'text'" class="agent-msg__gap" />
              <p v-else class="agent-msg__item"><b>{{ line.index }}</b>{{ line.value }}</p>
            </template>
            <i v-if="message.streaming" class="agent-msg__caret" />
          </div>
        </article>

        <div v-if="busy" class="agent-msg agent-msg--agent agent-msg--pending">
          <div class="agent-msg__meta"><span>AGENT</span><i /><time>processing</time></div>
          <div class="agent-dots"><i /><i /><i /></div>
        </div>
      </div>

      <form class="agent-ask" @submit.prevent="submit">
        <span>ASK /</span>
        <label class="sr-only" for="agent-os-prompt">Ask about Diego's work</label>
        <input
          id="agent-os-prompt"
          ref="inputEl"
          v-model="draft"
          type="text"
          autocomplete="off"
          spellcheck="false"
          placeholder="Ask about the work, a project, or availability..."
          @focus="focused = true"
          @blur="focused = false"
        />
        <button type="submit" :disabled="!canSend" aria-label="Send question">→</button>
      </form>

      <p v-if="error" class="agent-os__error" role="alert">{{ error }}</p>
    </div>

    <footer class="agent-os__foot">VUE / TYPESCRIPT / THREE.JS / SERVER-SIDE AI / SSE</footer>
  </section>
</template>
