<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  pulseAgentInteraction,
  pulseAgentSpeech,
  pulseAgentVisual,
  setAgentVisualPhase,
  type AgentVisualPhase,
} from "../../graphics/stageGraphics";
import { portfolioAgentProvider } from "./portfolioAgentProvider";
import { useAgentRuntime, type AgentProvider } from "./useAgentRuntime";

const props = withDefaults(
  defineProps<{
    provider?: AgentProvider;
  }>(),
  { provider: () => portfolioAgentProvider },
);

const laneEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLInputElement | null>(null);
let scrollFrame = 0;
let followStream = true;
let speechChars = 0;

const isNearBottom = (host: HTMLElement) =>
  host.scrollHeight - host.scrollTop - host.clientHeight < 96;

const scrollToBottom = () => {
  scrollFrame = 0;
  const host = laneEl.value;
  if (!host || !followStream) return;
  host.scrollTop = host.scrollHeight;
};

const scheduleScrollToBottom = () => {
  if (scrollFrame) return;
  scrollFrame = requestAnimationFrame(scrollToBottom);
};

const handleLaneScroll = () => {
  const host = laneEl.value;
  if (!host) return;
  followStream = isNearBottom(host);
};

const pulsePresentedText = (text: string) => {
  speechChars += text.replace(/\s/g, "").length;
  const boundary = /[\s,.!?;:]/.test(text);
  if (!boundary && speechChars < 6) return;

  const punctuation = /[!?]/.test(text) ? 0.18 : /[.]/.test(text) ? 0.12 : /[,;:]/.test(text) ? 0.05 : 0;
  const strength = Math.min(0.96, 0.36 + speechChars * 0.060 + punctuation);
  pulseAgentSpeech(strength);
  speechChars = 0;
};

const runtime = useAgentRuntime(props.provider, {
  onMessage: (message) => {
    if (message.role === "user") {
      followStream = true;
      speechChars = 0;
    }
    scheduleScrollToBottom();
    pulseAgentVisual(message.role === "user" ? 0.52 : 0.18);
  },
  onPresent: (text) => {
    pulsePresentedText(text);
    scheduleScrollToBottom();
  },
});

const {
  messages,
  draft,
  focused,
  busy,
  error,
  flow,
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

const statusLabel = computed(() => {
  if (error.value) return "DEGRADED";
  if (state.value === "working") return "WORKING";
  if (state.value === "speaking") return "SPEAKING";
  if (state.value === "listening") return "LISTENING";
  return "READY";
});

const visualPhase = (): AgentVisualPhase => {
  if (error.value) return "error";
  if (state.value === "working") return "thinking";
  return state.value;
};

const syncVisualPhase = () => {
  setAgentVisualPhase(visualPhase());
};

const phaseImpulse = (phase: AgentVisualPhase) => {
  if (phase === "thinking") return 0.42;
  if (phase === "speaking") return 0.20;
  if (phase === "listening") return 0.24;
  if (phase === "error") return 0.48;
  return 0.10;
};

const wakeAgent = (strength = 0.16) => {
  pulseAgentVisual(strength);
};

const engageAgent = () => {
  pulseAgentInteraction(0.82);
  wakeAgent(0.34);
  void nextTick(() => inputEl.value?.focus());
};

const submit = () => {
  if (!canSend.value) return;
  followStream = true;
  speechChars = 0;
  pulseAgentVisual(0.50);
  void send();
  inputEl.value?.focus();
};

const startPrompt = (prompt: string) => {
  if (busy.value) return;
  pulseAgentInteraction(0.34);
  draft.value = prompt;
  submit();
};

watch(
  state,
  () => {
    syncVisualPhase();
    pulseAgentVisual(phaseImpulse(visualPhase()));
  },
  { immediate: true },
);
watch(error, syncVisualPhase);
watch(draft, (next, previous) => {
  if (next.length > previous.length && next.length % 6 === 0) pulseAgentVisual(0.08);
});

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

    <button
      type="button"
      class="agent-presence"
      aria-label="Engage the portfolio agent"
      @click="engageAgent"
      @pointerenter="wakeAgent(0.12)"
    >
      <div class="agent-core agent-core--three">
        <span class="agent-core__status">{{ statusLabel }}</span>
      </div>
    </button>

    <div class="agent-chat">
      <div
        ref="laneEl"
        class="agent-lane"
        role="log"
        aria-live="polite"
        @scroll="handleLaneScroll"
      >
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
              @pointerenter="wakeAgent(0.06)"
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
            <p v-if="message.streaming" class="agent-msg__stream">
              {{ message.text }}<i class="agent-msg__caret" />
            </p>
            <template v-else v-for="(line, i) in linesOf(message.text)" :key="i">
              <p v-if="line.kind === 'text' && line.value">{{ line.value }}</p>
              <span v-else-if="line.kind === 'text'" class="agent-msg__gap" />
              <p v-else class="agent-msg__item"><b>{{ line.index }}</b>{{ line.value }}</p>
            </template>
          </div>
        </article>

        <div v-if="busy" class="agent-msg agent-msg--agent agent-msg--pending">
          <div class="agent-msg__meta"><span>AGENT</span><i /><time>EXECUTION</time></div>
          <div class="agent-flow" aria-label="Current agent execution flow">
            <template v-for="(step, index) in flow" :key="`${index}-${step}`">
              <span>{{ step }}</span>
              <i v-if="index < flow.length - 1">→</i>
            </template>
          </div>
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
          @focus="focused = true; wakeAgent(0.16)"
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
