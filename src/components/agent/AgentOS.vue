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
const engaged = ref(false);
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
    engaged.value = true;
    pulseAgentVisual(message.role === "user" ? 0.82 : 0.34);
  },
  onToken: () => {
    pulseAgentVisual(0.26);
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
  reset,
} = runtime;

const starters = [
  {
    label: "PROJECTS",
    eyebrow: "SYSTEMS / CODE",
    prompt: "What has Diego built with Rust and Go?",
  },
  {
    label: "AI SYSTEMS",
    eyebrow: "AGENTS / RAG",
    prompt: "Tell me about Diego's agent, RAG, and NL-to-SQL work.",
  },
  {
    label: "EXPERIENCE",
    eyebrow: "CAREER / IMPACT",
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
  if (state.value === "thinking") return "REASONING";
  if (state.value === "speaking") return "SPEAKING";
  if (state.value === "listening") return "LISTENING";
  return "ONLINE";
});

const statusCopy = computed(() => {
  if (error.value) return "Connection interrupted. I can retry when you are ready.";
  if (state.value === "thinking") return "Connecting projects, systems and experience.";
  if (state.value === "speaking") return "Answering from Diego's portfolio context.";
  if (state.value === "listening") return "I'm listening. Ask naturally.";
  return "Ready when you are.";
});

const sessionHeadline = computed(() => {
  if (messages.value.length > 0) return "Conversation context active";
  if (engaged.value || focused.value) return "Ask me anything about the work";
  return "A conversational interface to the portfolio";
});

const promptPlaceholder = computed(() => {
  if (state.value === "thinking") return "Working on your question...";
  if (state.value === "speaking") return "You can ask a follow-up while I answer...";
  if (messages.value.length > 0) return "Ask a follow-up...";
  return "Ask about projects, architecture, skills or experience...";
});

const contextLabel = computed(() => {
  const turns = messages.value.filter((message) => message.role === "user").length;
  return turns > 0 ? `${String(turns).padStart(2, "0")} TURNS / MEMORY ACTIVE` : "PORTFOLIO MEMORY / READY";
});

const syncVisualPhase = () => {
  const phase: AgentVisualPhase = error.value ? "error" : state.value;
  setAgentVisualPhase(phase);
};

const phaseImpulse = (phase: AgentVisualPhase) => {
  if (phase === "thinking") return 0.58;
  if (phase === "speaking") return 0.44;
  if (phase === "listening") return 0.30;
  if (phase === "error") return 0.66;
  return 0.14;
};

const wakeAgent = (strength = 0.24) => {
  engaged.value = true;
  pulseAgentVisual(strength);
};

const engageAgent = () => {
  wakeAgent(0.52);
  void nextTick(() => inputEl.value?.focus());
};

const submit = () => {
  if (!canSend.value) return;
  engaged.value = true;
  pulseAgentVisual(0.72);
  void send();
  inputEl.value?.focus();
};

const startPrompt = (prompt: string) => {
  if (busy.value) return;
  engaged.value = true;
  pulseAgentVisual(0.46);
  draft.value = prompt;
  submit();
};

const resetSession = () => {
  reset();
  engaged.value = true;
  pulseAgentVisual(0.38);
  void nextTick(() => inputEl.value?.focus());
};

watch(
  state,
  (next) => {
    syncVisualPhase();
    pulseAgentVisual(phaseImpulse(next));
  },
  { immediate: true },
);
watch(error, syncVisualPhase);
watch(draft, (next, previous) => {
  if (next.length > previous.length && next.length % 3 === 0) pulseAgentVisual(0.08);
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
    :data-engaged="engaged || focused || messages.length > 0 ? 'true' : 'false'"
    aria-label="Agent — ask about Diego's work"
  >
    <h2 class="ref-marker"><span>05</span><i aria-hidden="true" /><span>THE INTERFACE</span></h2>

    <button
      type="button"
      class="agent-presence"
      aria-label="Engage the portfolio agent"
      @click="engageAgent"
      @pointerenter="wakeAgent(0.18)"
    >
      <div class="agent-core agent-core--three">
        <span class="agent-presence__orbit agent-presence__orbit--outer" aria-hidden="true" />
        <span class="agent-presence__orbit agent-presence__orbit--inner" aria-hidden="true" />
        <span class="agent-presence__reticle" aria-hidden="true" />
        <span class="agent-presence__node agent-presence__node--a" aria-hidden="true" />
        <span class="agent-presence__node agent-presence__node--b" aria-hidden="true" />

        <span class="agent-core__identity">DC // KNOWLEDGE INTERFACE</span>
        <strong class="agent-core__status">{{ statusLabel }}</strong>
        <span class="agent-core__caption">{{ statusCopy }}</span>
        <span v-if="!engaged && !focused && messages.length === 0" class="agent-core__hint">CLICK TO ENGAGE</span>
      </div>
    </button>

    <div class="agent-chat">
      <header class="agent-session">
        <div class="agent-session__identity">
          <span>DC / AGENT</span>
          <strong>{{ sessionHeadline }}</strong>
        </div>
        <div class="agent-session__state">
          <i aria-hidden="true" />
          <span>{{ statusLabel }}</span>
        </div>
        <button
          v-if="messages.length > 0"
          type="button"
          class="agent-session__reset"
          @click="resetSession"
        >
          NEW SESSION
        </button>
      </header>

      <div ref="laneEl" class="agent-lane" role="log" aria-live="polite">
        <div
          v-if="messages.length === 0 && !busy"
          class="agent-empty"
          aria-label="Suggested questions"
        >
          <div class="agent-empty__lead">
            <span>READY FOR A CONVERSATION</span>
            <p>I know the projects, architecture decisions, skills and experience behind this portfolio.</p>
          </div>

          <div class="agent-empty__starters">
            <button
              v-for="(starter, index) in starters"
              :key="starter.label"
              type="button"
              class="agent-empty__starter"
              @pointerenter="wakeAgent(0.12)"
              @click="startPrompt(starter.prompt)"
            >
              <span class="agent-empty__index">{{ String(index + 1).padStart(2, "0") }}</span>
              <span class="agent-empty__copy">
                <small>{{ starter.eyebrow }}</small>
                <b>{{ starter.label }}</b>
                <em>{{ starter.prompt }}</em>
              </span>
              <i aria-hidden="true">↗</i>
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
            <span>{{ message.role === "agent" ? "DC / AGENT" : "YOU" }}</span>
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
          <div class="agent-msg__meta"><span>DC / AGENT</span><i /><time>reasoning</time></div>
          <div class="agent-dots"><i /><i /><i /></div>
        </div>
      </div>

      <form class="agent-ask" @submit.prevent="submit">
        <span>YOU /</span>
        <label class="sr-only" for="agent-os-prompt">Ask about Diego's work</label>
        <input
          id="agent-os-prompt"
          ref="inputEl"
          v-model="draft"
          type="text"
          autocomplete="off"
          spellcheck="false"
          :placeholder="promptPlaceholder"
          @focus="focused = true; wakeAgent(0.24)"
          @blur="focused = false"
        />
        <button type="submit" :disabled="!canSend" aria-label="Send question">SEND ↗</button>
      </form>

      <footer class="agent-context" aria-hidden="true">
        <span>{{ contextLabel }}</span>
        <span>STREAM / LIVE</span>
      </footer>

      <p v-if="error" class="agent-os__error" role="alert">{{ error }}</p>
    </div>
  </section>
</template>

<style src="./agent-three-core.css"></style>
<style src="./agent-empty.css"></style>
<style src="./agent-presence.css"></style>
