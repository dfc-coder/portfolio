<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import AsciiFluidCanvas from "./AsciiFluidCanvas.vue";
import type { Occluder } from "./agent/asciiField";
import { localProvider, useAgentRuntime, type AgentProvider } from "./agent/useAgentRuntime";

const props = withDefaults(
  defineProps<{
    /** Swap for an on-device model without touching this component. */
    provider?: AgentProvider;
  }>(),
  { provider: () => localProvider },
);

/* ------------------------------------------------------------------ dom --- */

const root = ref<HTMLElement | null>(null);
const laneEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLInputElement | null>(null);
const canvasRef = ref<InstanceType<typeof AsciiFluidCanvas> | null>(null);
const bubbleEls = ref<HTMLElement[]>([]);

const setBubbleRef = (el: unknown, index: number) => {
  if (el instanceof HTMLElement) bubbleEls.value[index] = el;
};

/* ------------------------------------------------------------ occluders --- */

const occluders = ref<Occluder[]>([]);
let tokenTick = 0;

/* The field spans the whole section, so occluders and impulses are normalised
   against the section box — not the lane — or the parting lands off-target. */
const measure = () => {
  const host = root.value;
  if (!host) return;
  const box = host.getBoundingClientRect();
  if (box.width < 2) return;
  bubbleEls.value.length = messages.value.length;
  occluders.value = bubbleEls.value.filter(Boolean).map((el) => {
    const r = el.getBoundingClientRect();
    return {
      x: (r.left - box.left) / box.width,
      y: (r.top - box.top) / box.height,
      w: r.width / box.width,
      h: r.height / box.height,
    };
  });
};

const pulseFrom = (el: HTMLElement | undefined, strength: number) => {
  const host = root.value;
  if (!host || !el) return;
  const box = host.getBoundingClientRect();
  const r = el.getBoundingClientRect();
  canvasRef.value?.pulse(
    (r.left + r.width / 2 - box.left) / box.width,
    (r.top + r.height / 2 - box.top) / box.height,
    strength,
  );
};

/** Newest message always sits on the baseline, just above the prompt. */
const stickToBottom = () => {
  const host = laneEl.value;
  if (!host) return;
  host.scrollTo({ top: host.scrollHeight, behavior: "smooth" });
};

const runtime = useAgentRuntime(props.provider, {
  onMessage: () => {
    void nextTick(() => {
      stickToBottom();
      measure();
      pulseFrom(bubbleEls.value[messages.value.length - 1], 1);
    });
  },
  onToken: () => {
    tokenTick += 1;
    if (tokenTick % 4 !== 0) return;
    void nextTick(stickToBottom);
    pulseFrom(bubbleEls.value[messages.value.length - 1], 0.22);
  },
});

const { messages, draft, focused, busy, error, state, canSend, send, seed } = runtime;

/* ----------------------------------------------------------------- copy --- */

seed([
  { role: "user", text: "What has Diego built with RAG?" },
  {
    role: "agent",
    text: [
      "Diego has used Retrieval Augmented Generation in several production-grade systems.",
      "",
      "01 Natural Language → SQL",
      "02 Document Intelligence",
      "03 Semantic Product Search",
    ].join("\n"),
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
let resizeObserver: ResizeObserver | null = null;

/** The field is the agent's presence, so it is only loud while the agent works.
    When the visitor is reading, the transcript wins. */
const fieldWeight = computed(() => {
  if (state.value === "thinking") return 1;
  if (state.value === "speaking") return 0.78;
  return 0.5;
});

const submit = () => {
  void send();
  inputEl.value?.focus();
};

onMounted(() => {
  resizeObserver = new ResizeObserver(() => measure());
  if (root.value) resizeObserver.observe(root.value);
  void nextTick(() => {
    stickToBottom();
    measure();
  });

  const stage = root.value?.closest(".ref-stage") as HTMLElement | null;
  if (stage) {
    const sync = () => (active.value = stage.dataset.scene === "agent");
    sceneObserver = new MutationObserver(sync);
    sceneObserver.observe(stage, { attributes: true, attributeFilter: ["data-scene"] });
    sync();
  }
});

watch(messages, () => void nextTick(measure), { deep: true });

onBeforeUnmount(() => {
  sceneObserver?.disconnect();
  resizeObserver?.disconnect();
});
</script>

<template>
  <section
    ref="root"
    class="agent-os"
    :data-state="state"
    :style="{ '--field-weight': fieldWeight }"
    aria-label="Agent 0 — ask about Diego's work"
  >
    <div class="ref-marker"><span>05</span><i />THE INTERFACE</div>

    <AsciiFluidCanvas
      ref="canvasRef"
      class="agent-os__field"
      :state="state"
      :occluders="occluders"
      :paused="!active"
    />

    <div ref="laneEl" class="agent-lane" role="log" aria-live="polite">
      <article
        v-for="(message, index) in messages"
        :key="message.id"
        :ref="(el) => setBubbleRef(el, index)"
        class="agent-msg"
        :class="`agent-msg--${message.role}`"
      >
        <div class="agent-msg__meta">
          <span>{{ message.role === "agent" ? "AGENT 0" : "YOU" }}</span>
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
        <div class="agent-msg__meta"><span>AGENT 0</span><i /><time>thinking</time></div>
        <div class="agent-dots"><i /><i /><i /></div>
      </div>
    </div>

    <form class="agent-ask" @submit.prevent="submit">
      <span>ASK /</span>
      <label class="sr-only" for="agent-os-prompt">Ask Agent 0 about Diego's work</label>
      <input
        id="agent-os-prompt"
        ref="inputEl"
        v-model="draft"
        type="text"
        autocomplete="off"
        spellcheck="false"
        placeholder="Type your question about Diego's work..."
        @focus="focused = true"
        @blur="focused = false"
      />
      <button type="submit" :disabled="!canSend" aria-label="Send question">→</button>
    </form>

    <p v-if="error" class="agent-os__error" role="alert">{{ error }}</p>

    <footer class="agent-os__foot">BUILT WITH VUE / TS / WEBGL</footer>
  </section>
</template>
