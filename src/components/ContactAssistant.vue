<script setup lang="ts">
import { nextTick, ref } from "vue";

type Message = { role: "assistant" | "visitor"; text: string };
type Workflow = "none" | "meeting" | "followup";

const prompts = [
  "Professional experience",
  "Technical projects",
  "Prepare a meeting",
  "Prepare a follow-up",
];

const initialMessage: Message = {
  role: "assistant",
  text: "Ask about Diego’s experience or projects, or prepare a meeting or follow-up for review. This demo never sends or schedules anything.",
};

const messages = ref<Message[]>([{ ...initialMessage }]);
const input = ref("");
const thinking = ref(false);
const workflow = ref<Workflow>("none");
const reviewed = ref(false);
const transcript = ref<HTMLElement | null>(null);

const scrollMessages = async () => {
  await nextTick();
  transcript.value?.scrollTo({ top: transcript.value.scrollHeight, behavior: "smooth" });
};

const responseFor = (question: string): string => {
  if (/experience|career|worked|trajectory/i.test(question)) {
    return "Diego’s recent trajectory includes AI engineering for private document intelligence, independent work on agents and retrieval systems, and full-stack software engineering focused on integrations, secure APIs and maintainable architecture.";
  }

  if (/project|system|technology|stack/i.test(question)) {
    return "Selected systems include a private document extractor, a guarded NL-to-SQL agent, a financial MCP tool server and intent-aware semantic search. The core stack spans Python, TypeScript, Java, local LLMs, RAG, APIs and distributed workflows.";
  }

  if (/follow.?up|remind|administrative|email/i.test(question)) {
    workflow.value = "followup";
    return "Complete the recipient, subject and context below. The result remains a local draft for review.";
  }

  if (/available|availability|meeting|call|calendar|schedule/i.test(question)) {
    workflow.value = "meeting";
    return "Complete the preferred date, timezone and contact email below. The request remains a draft and is not added to a calendar.";
  }

  return "I can answer about professional experience and technical projects, or prepare a meeting or follow-up draft.";
};

const send = async (value = input.value) => {
  const question = value.trim();
  if (!question || thinking.value) return;

  messages.value.push({ role: "visitor", text: question });
  input.value = "";
  workflow.value = "none";
  reviewed.value = false;
  await scrollMessages();

  thinking.value = true;
  window.setTimeout(async () => {
    messages.value.push({ role: "assistant", text: responseFor(question) });
    thinking.value = false;
    await scrollMessages();
  }, 320);
};

const reviewWorkflow = () => {
  reviewed.value = true;
  messages.value.push({
    role: "assistant",
    text:
      workflow.value === "meeting"
        ? "Meeting request prepared for review. No calendar event or email was created."
        : "Follow-up draft prepared for review. No message was sent or stored.",
  });
  workflow.value = "none";
  void scrollMessages();
};

const reset = () => {
  messages.value = [{ ...initialMessage }];
  input.value = "";
  workflow.value = "none";
  reviewed.value = false;
};
</script>

<template>
  <section class="agent-console" aria-label="Professional administrative agent demonstration">
    <header class="agent-console__header">
      <div><span>DC / PROFESSIONAL AGENT</span><strong>Ask or prepare an action</strong></div>
      <button type="button" @click="reset">RESET</button>
    </header>

    <div ref="transcript" class="agent-transcript" aria-live="polite">
      <div
        v-for="(message, index) in messages"
        :key="`${message.role}-${index}`"
        :class="['agent-message', message.role]"
      >
        <span>{{ message.role === "assistant" ? "AGENT" : "YOU" }}</span>
        <p>{{ message.text }}</p>
      </div>

      <div v-if="thinking" class="agent-thinking" aria-label="Agent is preparing a response">
        <i /><i /><i />
      </div>

      <form
        v-if="workflow === 'meeting' && !reviewed"
        class="agent-workflow"
        @submit.prevent="reviewWorkflow"
      >
        <h3>Prepare meeting request</h3>
        <label>Preferred date<input type="date" required /></label>
        <label>
          Timezone
          <select required>
            <option>Buenos Aires · GMT−3</option>
            <option>Madrid · GMT+2</option>
            <option>New York · GMT−4</option>
          </select>
        </label>
        <label>Contact email<input type="email" placeholder="name@company.com" required /></label>
        <button type="submit">CREATE REVIEWABLE REQUEST</button>
      </form>

      <form
        v-if="workflow === 'followup' && !reviewed"
        class="agent-workflow"
        @submit.prevent="reviewWorkflow"
      >
        <h3>Prepare follow-up draft</h3>
        <label>Recipient<input type="email" placeholder="name@company.com" required /></label>
        <label>Subject<input type="text" placeholder="Project follow-up" required /></label>
        <label>Context<textarea placeholder="What should the follow-up cover?" required /></label>
        <button type="submit">CREATE REVIEWABLE DRAFT</button>
      </form>
    </div>

    <div class="agent-actions" aria-label="Suggested actions">
      <button v-for="prompt in prompts" :key="prompt" type="button" @click="send(prompt)">
        {{ prompt }}
      </button>
    </div>

    <form class="agent-input" @submit.prevent="send()">
      <label for="assistant-question">Your question</label>
      <input
        id="assistant-question"
        v-model="input"
        autocomplete="off"
        placeholder="Ask about experience, projects or availability…"
      />
      <button type="submit" :disabled="!input.trim() || thinking">SEND</button>
    </form>
  </section>
</template>
