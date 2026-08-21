<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import AsciiFluidCanvas from "./AsciiFluidCanvas.vue";
import { businessAgentProvider } from "./businessAgentProvider";
import { useAgentRuntime, type AgentProvider } from "./useAgentRuntime";

const props = withDefaults(
  defineProps<{
    provider?: AgentProvider;
  }>(),
  { provider: () => businessAgentProvider },
);

const root = ref<HTMLElement | null>(null);
const laneEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLInputElement | null>(null);
const canvasRef = ref<InstanceType<typeof AsciiFluidCanvas> | null>(null);

const tokenBeat = ref(0);
let tokenSequence = 0;

const stickToBottom = () => {
  const host = laneEl.value;
  if (!host) return;
  host.scrollTo({ top: host.scrollHeight, behavior: "smooth" });
};

const runtime = useAgentRuntime(props.provider, {
  onMessage: (message) => {
    void nextTick(stickToBottom);
    if (message.role === "user") canvasRef.value?.pulse(0.5, 0.5, 0.9);
  },
  onToken: () => {
    tokenSequence += 1;
    tokenBeat.value = tokenSequence;

    const angle = tokenSequence * 2.399963229728653;
    const radius = 0.11 + (tokenSequence % 6) * 0.018;
    const x = 0.5 + Math.cos(angle) * radius;
    const y = 0.5 + Math.sin(angle) * radius * 0.72;
    canvasRef.value?.speak(1.35);
    canvasRef.value?.pulse(x, y, 0.2);
    void nextTick(stickToBottom);
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

const active = ref(true);
let sceneObserver: MutationObserver | null = null;

const fieldWeight = computed(() => {
  if (state.value === "thinking") return 1;
  if (state.value === "speaking") return 0.94;
  if (state.value === "listening") return 0.72;
  return 0.58;
});

const statusLabel = computed(() => {
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

const submit = () => {
  void send();
  inputEl.value?.focus();
};

onMounted(() => {
  void nextTick(stickToBottom);

  const stage = root.value?.closest(".ref-stage") as HTMLElement | null;
  if (!stage) return;

  const sync = () => (active.value = stage.dataset.scene === "agent");
  sceneObserver = new MutationObserver(sync);
  sceneObserver.observe(stage, { attributes: true, attributeFilter: ["data-scene"] });
  sync();
});

watch(messages, () => void nextTick(stickToBottom), { deep: true });

onBeforeUnmount(() => {
  sceneObserver?.disconnect();
});
</script>

<template>
  <section
    ref="root"
    class="agent-os"
    :data-state="state"
    :style="{ '--field-weight': fieldWeight }"
    aria-label="Agent — ask about Diego's work"
  >
    <div class="ref-marker"><span>05</span><i />THE INTERFACE</div>

    <aside class="agent-presence" aria-hidden="true">
      <div class="agent-core">
        <AsciiFluidCanvas
          ref="canvasRef"
          class="agent-presence__field"
          :state="state"
          :paused="!active"
        />
        <div class="agent-core__grid" />
        <div class="agent-core__rings"><i /><i /><i /></div>
        <div class="agent-core__reticle"><i /><i /></div>
        <i v-if="tokenBeat > 0" :key="tokenBeat" class="agent-core__token-ring" />
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

    <footer class="agent-os__foot">VUE / TYPESCRIPT / SERVER-SIDE AI / SSE</footer>
  </section>
</template>
