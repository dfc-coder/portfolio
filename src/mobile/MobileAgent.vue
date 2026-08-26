<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from "vue";
import { businessAgentProvider } from "../components/agent/businessAgentProvider";
import { useAgentRuntime } from "../components/agent/useAgentRuntime";

const laneEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLInputElement | null>(null);
let scrollFrame = 0;

const scrollToBottom = () => {
  scrollFrame = 0;
  const lane = laneEl.value;
  if (lane) lane.scrollTop = lane.scrollHeight;
};

const scheduleScroll = () => {
  if (scrollFrame) return;
  scrollFrame = requestAnimationFrame(scrollToBottom);
};

const runtime = useAgentRuntime(businessAgentProvider, {
  onMessage: scheduleScroll,
  onToken: scheduleScroll,
});

const { messages, draft, busy, error, canSend, send } = runtime;

const starters = [
  ["01", "PROJECTS", "What has Diego built with Rust and Go?"],
  ["02", "AI SYSTEMS", "Tell me about Diego's agent, RAG, and NL-to-SQL work."],
  ["03", "EXPERIENCE", "Tell me about Diego's professional experience."],
] as const;

const submit = async () => {
  await send();
  await nextTick();
  inputEl.value?.focus();
};

const start = (prompt: string) => {
  if (busy.value) return;
  draft.value = prompt;
  void submit();
};

onBeforeUnmount(() => {
  if (scrollFrame) cancelAnimationFrame(scrollFrame);
});
</script>

<template>
  <div class="m-agent">
    <div ref="laneEl" class="m-agent__lane" role="log" aria-live="polite">
      <div v-if="messages.length === 0 && !busy" class="m-agent__empty">
        <p>Ask about Diego's projects, systems, skills, or experience.</p>
        <button
          v-for="starter in starters"
          :key="starter[0]"
          type="button"
          class="m-agent__starter"
          @click="start(starter[2])"
        >
          <span>{{ starter[0] }}</span>
          <strong>{{ starter[1] }}</strong>
          <small>{{ starter[2] }}</small>
          <b aria-hidden="true">→</b>
        </button>
      </div>

      <article
        v-for="message in messages"
        :key="message.id"
        :class="['m-agent__message', `m-agent__message--${message.role}`]"
      >
        <header><span>{{ message.role === 'agent' ? 'AGENT' : 'YOU' }}</span><time>{{ message.time }}</time></header>
        <p>{{ message.text }}</p>
      </article>

      <div v-if="busy" class="m-agent__thinking"><span /><span /><span /></div>
    </div>

    <form class="m-agent__form" @submit.prevent="submit">
      <label for="mobile-agent-prompt">ASK /</label>
      <input
        id="mobile-agent-prompt"
        ref="inputEl"
        v-model="draft"
        type="text"
        autocomplete="off"
        placeholder="Ask about Diego's work..."
      />
      <button type="submit" :disabled="!canSend" aria-label="Send question">→</button>
    </form>
    <p v-if="error" class="m-agent__error">{{ error }}</p>
  </div>
</template>
