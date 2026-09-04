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
  | { type: "context"; messages: AgentContextMessage[] };

export interface AgentProvider {
  ask(
    question: string,
    context: ReadonlyArray<AgentContextMessage>,
  ): AsyncIterable<AgentEvent | string>;
}

export type RuntimeState = "idle" | "listening" | "working" | "speaking";

const PRESENTATION_BASE_CPS = 52;
const PRESENTATION_MAX_CPS = 92;
const PRESENTATION_MAX_BATCH = 4;

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
  const nextId = shallowRef(1);

  let replyId = -1;
  let presentationFrame = 0;
  let presentationQueue = "";
  let presentationBudget = 0;
  let presentationTime = 0;
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
    if (presentationQueue || presentationFrame) return;
    const resolve = drainResolver;
    drainResolver = null;
    resolve?.();
  };

  const present = (now: number) => {
    presentationFrame = 0;
    if (!presentationQueue) {
      presentationTime = 0;
      resolveDrain();
      return;
    }

    if (!presentationTime) presentationTime = now;
    const dt = Math.min(0.05, Math.max(0.008, (now - presentationTime) / 1000));
    presentationTime = now;

    const cps = Math.min(
      PRESENTATION_MAX_CPS,
      PRESENTATION_BASE_CPS + presentationQueue.length * 0.10,
    );
    presentationBudget += cps * dt;

    const count = Math.min(
      PRESENTATION_MAX_BATCH,
      presentationQueue.length,
      Math.floor(presentationBudget),
    );

    if (count > 0) {
      const target = reply();
      const batch = presentationQueue.slice(0, count);
      presentationQueue = presentationQueue.slice(count);
      presentationBudget -= count;

      if (target) {
        target.text += batch;
        hooks.onPresent?.(batch);
      }
    }

    if (presentationQueue) {
      presentationFrame = requestAnimationFrame(present);
      return;
    }

    presentationBudget = Math.min(1, presentationBudget);
    presentationTime = 0;
    resolveDrain();
  };

  const schedulePresentation = () => {
    if (presentationFrame) return;
    presentationFrame = requestAnimationFrame(present);
  };

  const waitForPresentation = (): Promise<void> => {
    if (!presentationQueue && !presentationFrame) return Promise.resolve();
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
    presentationTime = 0;
    let receivedContent = false;

    try {
      for await (const event of provider.ask(question, context.value)) {
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
    if (presentationFrame) cancelAnimationFrame(presentationFrame);
    presentationFrame = 0;
    presentationQueue = "";
    presentationBudget = 0;
    presentationTime = 0;
    replyId = -1;
    const resolve = drainResolver;
    drainResolver = null;
    resolve?.();
    messages.value = [];
    context.value = [];
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
