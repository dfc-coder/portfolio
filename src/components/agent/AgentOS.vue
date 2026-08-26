<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
    pulseAgentVisual(0.22);
    scheduleScrollToBottom();
  },
});

const {
  messages,
  draft,
  focused,
  busy,
  error,
  state,
  canSend,
  send,
} = runtime;

const starters = [
  {
    label: "PROJECTS",
    prompt: "What has Diego built with Rust and Go?",
  },
  {
    label: "AI SYSTEMS",
    prompt: "Tell me about Diego's agent, RAG, and NL-to-SQL work.",
  },
  {
    label: "EXPERIENCE",
    prompt: "Tell me about Diego's professional experience.",
  },
] as const;

type Line =
  | { kind: "text"; value: string }
  | { kind: "item"; index: string; value: string };

const linesOf = (text: string): Line[] =>
  text.split("\n").map((line): Line => {
    const match = /^(\d{2})\s+(.*)$/.exec(line);
    return match
      ? { kind: "item", index: match[1], value: match[2] }
      : { kind: "text", value: line };
  });

const statusLabel = () => {
  if (error.value) return "FAULT";
  if (state.value === "thinking") return "THINKING";
  if (state.value === "speaking") return "RESPONDING";
  return "READY";
};

const syncVisualPhase = () => {
  const phase: AgentVisualPhase = error.value ? "error" : state.value;
  setAgentVisualPhase(phase);
};

const submit = () => {
  void send();
  inputEl.value?.focus();
};

const startPrompt = (prompt: string) => {
  if (busy.value) return;
  draft.value = prompt;
  submit();
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
    <h2 class="ref-marker"><span>05</span><i aria-hidden="true" /><span>THE INTERFACE</span></h2>

    <aside class="agent-presence" aria-hidden="true">
      <div class="agent-core agent-core--three">
        <span class="agent-core__status">{{ statusLabel() }}</span>
      </div>
    </aside>

    <div class="agent-chat">
      <div ref="laneEl" class="agent-lane" role="log" aria-live="polite">
        <div
          v-if="messages.length === 0 && !busy"
          class="agent-empty"
          aria-label="Suggested questions"
        >
          <p class="agent-empty__intro">Ask about Diego's projects, systems, skills, or experience.</p>
          <div class="agent-empty__starters">
            <button
              v-for="(starter, index) in starters"
              :key="starter.label"
              type="button"
              class="agent-empty__starter"
              @click="startPrompt(starter.prompt)"
            >
              <span>{{ String(index + 1).padStart(2, "0") }}</span>
              <b>{{ starter.label }}</b>
              <small>{{ starter.prompt }}</small>
            </button>
          </div>
        </div>

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
          placeholder="Ask about Diego's work, projects, skills, or experience..."
          @focus="focused = true"
          @blur="focused = false"
        />
        <button type="submit" :disabled="!canSend" aria-label="Send question">→</button>
      </form>

      <p v-if="error" class="agent-os__error" role="alert">{{ error }}</p>
    </div>
  </section>
</template>

<style src="./agent-three-core.css"></style>
<style src="./agent-empty.css"></style>
