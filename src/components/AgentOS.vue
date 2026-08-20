<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import AsciiFluidCanvas from "./AsciiFluidCanvas.vue";
import { businessAgentProvider } from "./agent/businessAgentProvider";
import { useAgentRuntime, type AgentProvider } from "./agent/useAgentRuntime";

const props = withDefaults(
  defineProps<{
    /** Override for tests or alternate providers without touching the UI. */
    provider?: AgentProvider;
  }>(),
  { provider: () => businessAgentProvider },
);

/* ------------------------------------------------------------------ dom --- */

const root = ref<HTMLElement | null>(null);
const laneEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLInputElement | null>(null);
const canvasRef = ref<InstanceType<typeof AsciiFluidCanvas> | null>(null);

/* ---------------------------------------------------------------- field --- */

/* Two-column layout: the field owns the left column, the chat owns the right.
   They never overlap, so there is no z-order to fight and no occluders to
   compute — the field is beside the text, as its own presence, not behind it.
   The field reacts through two channels:
     · pulse()  a discrete impulse when a message is committed
     · speak()  a continuous swell per streamed token (morphological speech) */

const stickToBottom = () => {
  const host = laneEl.value;
  if (!host) return;
  host.scrollTo({ top: host.scrollHeight, behavior: "smooth" });
};

const runtime = useAgentRuntime(props.provider, {
  onMessage: (message) => {
    void nextTick(stickToBottom);
    // A visitor message lands as a ripple; the agent's own turns are voiced
    // through speak() instead, so the impulse here is the user's.
    if (message.role === "user") canvasRef.value?.pulse(0.5, 0.5, 1);
  },
  onToken: () => {
    canvasRef.value?.speak(1);
    void nextTick(stickToBottom);
  },
});

const { messages, draft, focused, busy, error, state, canSend, send, seed } = runtime;

/* ----------------------------------------------------------------- copy --- */

seed([
  {
    role: "agent",
    text: "Hi. I can answer questions about Diego's work and, if useful, help you find a time to talk.",
  },
]);

/** "01 Label" lines become an indexed row; everything else is a paragraph. */
type Line = { kind: "text"; value: string } | { kind: "item"; index: string; value: string };

const linesOf = (text: string): Line[] =>
  text.split("\n").map((line): Line => {
    const match = /^(\d{2})\s+(.*)$/.exec(line);
    return match
      ? { kind: "item", index: match[1], value: match[2] }
      : { kind: "text", value: line };
  });

/* --------------------------------------------------------------- scene --- */

const active = ref(true);
let sceneObserver: MutationObserver | null = null;

/** Field weight rises while the agent works, so its column breathes with the
    conversation without ever competing with the text for legibility. */
const fieldWeight = computed(() => {
  if (state.value === "thinking") return 1;
  if (state.value === "speaking") return 0.9;
  if (state.value === "listening") return 0.7;
  return 0.55;
});

const statusLabel = computed(() => {
  if (state.value === "thinking") return "THINKING";
  if (state.value === "speaking") return "RESPONDING";
  if (state.value === "listening") return "LISTENING";
  return "ONLINE";
});

const submit = () => {
  void send();
  inputEl.value?.focus();
};

onMounted(() => {
  void nextTick(stickToBottom);

  const stage = root.value?.closest(".ref-stage") as HTMLElement | null;
  if (stage) {
    const sync = () => (active.value = stage.dataset.scene === "agent");
    sceneObserver = new MutationObserver(sync);
    sceneObserver.observe(stage, { attributes: true, attributeFilter: ["data-scene"] });
    sync();
  }
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

    <!-- Left column: the agent's morphological presence -->
    <aside class="agent-presence" aria-hidden="true">
      <AsciiFluidCanvas
        ref="canvasRef"
        class="agent-presence__field"
        :state="state"
        :paused="!active"
      />
      <div class="agent-presence__label">
        <span class="agent-presence__dot" />
        <span>AGENT</span>
        <b>{{ statusLabel }}</b>
      </div>
    </aside>

    <!-- Right column: the conversation. Text floats, depth comes from shadow. -->
    <div class="agent-chat">
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
          <div class="agent-msg__meta"><span>AGENT</span><i /><time>thinking</time></div>
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
