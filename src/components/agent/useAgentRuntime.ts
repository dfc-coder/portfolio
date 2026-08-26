import { computed, ref, shallowRef } from "vue";

export type AgentRole = "user" | "agent";

export interface AgentMessage {
  id: number;
  role: AgentRole;
  text: string;
  time: string;
  streaming: boolean;
}

export type AgentEvent = { type: "token"; text: string };

export interface AgentProvider {
  ask(
    question: string,
    history: ReadonlyArray<AgentMessage>,
  ): AsyncIterable<AgentEvent | string>;
}

export type RuntimeState = "idle" | "listening" | "thinking" | "speaking";

const TZ = "America/Argentina/Buenos_Aires";
const timeFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ,
  hour12: false,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export const stamp = (date = new Date()): string => timeFormatter.format(date);

export interface RuntimeHooks {
  onMessage?: (message: AgentMessage) => void;
  onToken?: () => void;
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
  const nextId = shallowRef(1);
  let streamFrame = 0;
  let pendingText = "";
  let replyId = -1;

  const state = computed<RuntimeState>(() => {
    if (messages.value.some((message) => message.streaming)) return "speaking";
    if (busy.value) return "thinking";
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

  const flushStream = () => {
    streamFrame = 0;
    if (!pendingText) return;
    const target = reply();
    if (!target) {
      pendingText = "";
      return;
    }

    target.text += pendingText;
    pendingText = "";
    hooks.onToken?.();
  };

  const scheduleStreamFlush = () => {
    if (streamFrame) return;
    streamFrame = requestAnimationFrame(flushStream);
  };

  const flushStreamNow = () => {
    if (streamFrame) cancelAnimationFrame(streamFrame);
    streamFrame = 0;
    flushStream();
  };

  const handleEvent = (event: AgentEvent | string): void => {
    const text = typeof event === "string" ? event : event.text;
    if (!text) return;
    if (replyId < 0) {
      busy.value = false;
      replyId = push("agent", "", true).id;
    }
    pendingText += text;
    scheduleStreamFlush();
  };

  const send = async () => {
    const question = draft.value.trim();
    if (!question || busy.value) return;

    draft.value = "";
    error.value = null;
    push("user", question);
    busy.value = true;

    const history = messages.value.slice(0, -1);
    replyId = -1;
    pendingText = "";
    let receivedContent = false;

    try {
      for await (const event of provider.ask(question, history)) {
        receivedContent = true;
        handleEvent(event);
      }

      flushStreamNow();
      if (!receivedContent) {
        throw new Error("Agent provider returned no conversational content");
      }
      const target = reply();
      if (target) target.streaming = false;
    } catch (cause) {
      flushStreamNow();
      error.value = "The agent could not answer. Try again.";
      const target = reply();
      if (target) target.streaming = false;
      console.error("[agent-os] provider failed", cause);
    } finally {
      busy.value = false;
    }
  };

  const reset = () => {
    if (streamFrame) cancelAnimationFrame(streamFrame);
    streamFrame = 0;
    pendingText = "";
    replyId = -1;
    messages.value = [];
    draft.value = "";
    error.value = null;
  };

  return {
    messages,
    draft,
    focused,
    busy,
    error,
    state,
    canSend,
    send,
    reset,
  };
}
