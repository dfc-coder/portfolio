<script setup lang="ts">
import { nextTick, ref } from "vue";

type Message = { role: "assistant" | "visitor"; text: string };
type Workflow = "none" | "meeting" | "followup";

const prompts = ["Show professional experience", "Check availability", "Prepare a meeting", "Prepare a follow-up"];
const messages = ref<Message[]>([
  { role: "assistant", text: "I can answer from Diego’s approved professional profile and prepare administrative actions for review. Nothing is sent or scheduled without explicit confirmation." },
]);
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
  if (/available|availability|schedule/i.test(question)) {
    workflow.value = "meeting";
    return "I can prepare an availability request. Choose a preferred date and timezone; the request remains a draft until the final review step.";
  }
  if (/follow.?up|remind|administrative|email/i.test(question)) {
    workflow.value = "followup";
    return "I can prepare a concise follow-up with recipient, subject and context. This demonstration creates a reviewable draft only.";
  }
  if (/meeting|call|calendar/i.test(question)) {
    workflow.value = "meeting";
    return "I can prepare a meeting request. Calendar access would occur only after date, timezone, contact details and the final action are explicitly confirmed.";
  }
  if (/project|system|technology|stack/i.test(question)) {
    return "Selected systems include a private document extractor, a guarded NL-to-SQL agent, a financial MCP tool server and intent-aware semantic search. The core stack spans Python, TypeScript, Java, local LLMs, RAG, APIs and distributed workflows.";
  }
  return "I can answer about experience, technical systems and availability, or prepare a meeting or administrative follow-up for review.";
};

const send = async (value = input.value) => {
  const question = value.trim();
  if (!question || thinking.value) return;
  messages.value.push({ role: "visitor", text: question });
  input.value = "";
  reviewed.value = false;
  await scrollMessages();
  thinking.value = true;
  window.setTimeout(async () => {
    messages.value.push({ role: "assistant", text: responseFor(question) });
    thinking.value = false;
    await scrollMessages();
  }, 420);
};

const reviewWorkflow = () => {
  reviewed.value = true;
  messages.value.push({
    role: "assistant",
    text: workflow.value === "meeting"
      ? "The meeting request is ready for final review. This demo does not write to Calendar or send email."
      : "The follow-up draft is ready for final review. This demo does not send or store the message.",
  });
  void scrollMessages();
};
</script>

<template>
  <div class="assistant-shell">
    <aside class="assistant-manifest">
      <div class="assistant-status"><i /><span>PROFESSIONAL AGENT / REVIEW MODE</span></div>
      <h3>Useful actions,<br /><em>visible limits.</em></h3>
      <p>The agent answers from approved professional information and prepares administrative workflows without silently executing them.</p>
      <ul>
        <li><span>01</span>Experience and projects</li>
        <li><span>02</span>Availability requests</li>
        <li><span>03</span>Meeting preparation</li>
        <li><span>04</span>Administrative follow-ups</li>
      </ul>
    </aside>

    <section class="chat-console" aria-label="Professional administrative agent demonstration">
      <header>
        <div class="console-id"><span>DC—A/02</span><b>PROFESSIONAL LIAISON</b></div>
        <div class="console-scope"><i />APPROVED KNOWLEDGE</div>
      </header>

      <div ref="transcript" class="chat-transcript" aria-live="polite">
        <div v-for="(message, index) in messages" :key="`${message.role}-${index}`" :class="['chat-message', message.role]">
          <span>{{ message.role === "assistant" ? "DC—A" : "VISITOR" }}</span>
          <p>{{ message.text }}</p>
        </div>
        <div v-if="thinking" class="chat-thinking"><i /><i /><i /></div>

        <form v-if="workflow === 'meeting' && !reviewed" class="meeting-card" @submit.prevent="reviewWorkflow">
          <span>MEETING REQUEST / REVIEW REQUIRED</span>
          <label>PREFERRED DATE<input type="date" required /></label>
          <label>TIMEZONE<select required><option>Buenos Aires · GMT−3</option><option>Madrid · GMT+2</option><option>New York · GMT−4</option></select></label>
          <label>CONTACT EMAIL<input type="email" placeholder="name@company.com" required /></label>
          <button type="submit">PREPARE FOR REVIEW →</button>
        </form>

        <form v-if="workflow === 'followup' && !reviewed" class="meeting-card" @submit.prevent="reviewWorkflow">
          <span>FOLLOW-UP DRAFT / REVIEW REQUIRED</span>
          <label>RECIPIENT<input type="email" placeholder="name@company.com" required /></label>
          <label>SUBJECT<input type="text" placeholder="Project follow-up" required /></label>
          <label>CONTEXT<input type="text" placeholder="What should be followed up?" required /></label>
          <button type="submit">PREPARE DRAFT →</button>
        </form>
      </div>

      <div class="chat-prompts">
        <button v-for="prompt in prompts" :key="prompt" type="button" @click="send(prompt)">{{ prompt }}</button>
      </div>

      <form class="chat-input" @submit.prevent="send()">
        <label for="assistant-question">Ask about work or prepare an administrative action</label>
        <input id="assistant-question" v-model="input" autocomplete="off" placeholder="Experience, projects, availability, meetings…" />
        <button type="submit" :disabled="!input.trim() || thinking" aria-label="Send">↗</button>
      </form>

      <footer><span>SESSION / EPHEMERAL</span><span>NO EXTERNAL WRITE WITHOUT CONFIRMATION</span></footer>
    </section>
  </div>
</template>
