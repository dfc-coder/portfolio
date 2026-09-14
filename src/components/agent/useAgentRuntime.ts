import { computed, ref, shallowRef } from "vue";

export type AgentRole = "user" | "agent";
export type AgentContextMessage = Record<string, unknown>;

export interface AgentMessage {
  id: number;
  role: AgentRole;
  text: string;
  time: string;
  streaming: boolean;
}

export type AgentEvent =
  | { type: "token"; text: string }
  | { type: "status"; phase: "model" | "responding"; round: number }
  | {
      type: "tool";
      name: string;
      state: "running" | "done";
      round: number;
      ok?: boolean;
    }
  | { type: "conversation"; conversationId: string }
  | { type: "context"; messages: AgentContextMessage[] };

export interface AgentProvider {
  ask(
    question: string,
    context: ReadonlyArray<AgentContextMessage>,
    conversationId: string | null,
  ): AsyncIterable<AgentEvent | string>;
}

export type RuntimeState = "idle" | "listening" | "working" | "speaking";

const PRESENTATION_INTERVAL_MS = 40;
const PRESENTATION_BASE_CPS = 84;
const PRESENTATION_MAX_CPS = 180;
const PRESENTATION_MAX_BATCH = 12;

const timeFormatter = new Intl.DateTimeFormat("en-GB", {
  hour12: false,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export const stamp = (date = new Date()): string => timeFormatter.format(date);

export interface RuntimeHooks {
  onMessage?: (message: AgentMessage) => void;
  onPresent?: (text: string) => void;
}

export function useAgentRuntime(
  provider: AgentProvider,
  hooks: RuntimeHooks = {},
) {
  const messages = ref<AgentMessage[]>([]);
  const draft = ref("");
  const focused = ref(false);
  const busy = ref(false);
  const error = ref<string | null>(null);
  const flow = ref<string[]>([]);
  const context = shallowRef<AgentContextMessage[]>([]);
  const conversationId = shallowRef<string | null>(null);
  const nextId = shallowRef(1);

  let replyId = -1;
  let presentationTimer = 0;
  let presentationQueue = "";
  let presentationBudget = 0;
  let drainResolver: (() => void) | null = null;

  const state = computed<RuntimeState>(() => {
    if (messages.value.some((message) => message.streaming)) return "speaking";
    if (busy.value) return "working";
    if (focused.value || draft.value.length > 0) return "listening";
    return "idle";
  });

  const canSend = computed(
    () => draft.value.trim().length > 0 && !busy.value,
  );

  const push = (
    role: AgentRole,
    text: string,
    streaming = false,
  ): AgentMessage => {
    const message: AgentMessage = {
      id: nextId.value++,
      role,
      text,
      time: stamp(),
      streaming,
    };
    messages.value.push(message);
    if (messages.value.length > 10) messages.value.shift();
    hooks.onMessage?.(message);
    return message;
  };

  const reply = () => messages.value.find((message) => message.id === replyId);

  const resolveDrain = () => {
    if (presentationQueue || presentationTimer) return;
    const resolve = drainResolver;
    drainResolver = null;
    resolve?.();
  };

  const schedulePresentation = () => {
    if (presentationTimer) return;
    presentationTimer = window.setTimeout(present, PRESENTATION_INTERVAL_MS);
  };

  function present() {
    presentationTimer = 0;
    if (!presentationQueue) {
      presentationBudget = 0;
      resolveDrain();
      return;
    }

    const cps = Math.min(
      PRESENTATION_MAX_CPS,
      PRESENTATION_BASE_CPS + presentationQueue.length * 0.32,
    );
    presentationBudget += cps * (PRESENTATION_INTERVAL_MS / 1000);

    const count = Math.min(
      PRESENTATION_MAX_BATCH,
      presentationQueue.length,
      Math.max(1, Math.floor(presentationBudget)),
    );

    const target = reply();
    const batch = presentationQueue.slice(0, count);
    presentationQueue = presentationQueue.slice(count);
    presentationBudget = Math.max(0, presentationBudget - count);

    if (target) {
      target.text += batch;
      hooks.onPresent?.(batch);
    }

    if (presentationQueue) {
      schedulePresentation();
      return;
    }

    presentationBudget = Math.min(1, presentationBudget);
    resolveDrain();
  }

  const waitForPresentation = (): Promise<void> => {
    if (!presentationQueue && !presentationTimer) return Promise.resolve();
    return new Promise((resolve) => {
      drainResolver = resolve;
    });
  };

  const addFlow = (step: string) => {
    if (!step || flow.value.at(-1) === step) return;
    flow.value.push(step);
    if (flow.value.length > 8) flow.value.shift();
  };

  const handleEvent = (event: AgentEvent | string): boolean => {
    if (typeof event !== "string" && event.type === "status") {
      addFlow(
        event.phase === "model"
          ? `MODEL / ROUND ${event.round}`
          : `RESPONSE / ROUND ${event.round}`,
      );
      return false;
    }

    if (typeof event !== "string" && event.type === "tool") {
      if (event.state === "running") addFlow(`TOOL / ${event.name}`);
      if (event.state === "done" && event.ok === false) {
        addFlow(`TOOL ERROR / ${event.name}`);
      }
      return false;
    }

    if (typeof event !== "string" && event.type === "conversation") {
      conversationId.value = event.conversationId;
      return false;
    }

    if (typeof event !== "string" && event.type === "context") {
      context.value = event.messages;
      return false;
    }

    const text = typeof event === "string" ? event : event.text;
    if (!text) return false;

    if (replyId < 0) {
      replyId = push("agent", "", true).id;
    }

    presentationQueue += text;
    schedulePresentation();
    return true;
  };

  const send = async () => {
    const question = draft.value.trim();
    if (!question || busy.value) return;

    draft.value = "";
    error.value = null;
    flow.value = [];
    push("user", question);
    busy.value = true;

    replyId = -1;
    presentationQueue = "";
    presentationBudget = 0;
    let receivedContent = false;

    try {
      for await (const event of provider.ask(
        question,
        context.value,
        conversationId.value,
      )) {
        receivedContent = handleEvent(event) || receivedContent;
      }

      if (!receivedContent) {
        throw new Error("Agent provider returned no conversational content");
      }

      await waitForPresentation();
      const target = reply();
      if (target) target.streaming = false;
    } catch (cause) {
      await waitForPresentation();
      error.value = "The agent could not answer. Try again.";
      const target = reply();
      if (target) target.streaming = false;
      console.error("[agent-os] provider failed", cause);
    } finally {
      busy.value = false;
    }
  };

  const reset = () => {
    if (presentationTimer) clearTimeout(presentationTimer);
    presentationTimer = 0;
    presentationQueue = "";
    presentationBudget = 0;
    replyId = -1;
    const resolve = drainResolver;
    drainResolver = null;
    resolve?.();
    messages.value = [];
    context.value = [];
    conversationId.value = null;
    draft.value = "";
    error.value = null;
    flow.value = [];
  };

  return {
    messages,
    draft,
    focused,
    busy,
    error,
    flow,
    state,
    canSend,
    send,
    reset,
  };
}
