import { computed, ref, shallowRef } from "vue";

export type AgentRole = "user" | "agent";

export interface AgentMessage {
  id: number;
  role: AgentRole;
  text: string;
  time: string;
  streaming: boolean;
}

export interface BookingApprovalAction {
  type: "confirm_booking";
  bookingId: string;
  subject: string;
  visitorName: string;
  visitorEmail: string;
  start: string;
  end: string;
  expiresAt: string | null;
}

export type AgentEvent =
  | { type: "token"; text: string }
  | { type: "action_required"; action: BookingApprovalAction }
  | { type: "action_cleared" };

export interface BookingActionResult {
  status: "confirmed" | "cancelled";
  bookingId: string;
  eventId: string | null;
  htmlLink: string | null;
  start: string | null;
  end: string | null;
}

export interface AgentProvider {
  ask(question: string, history: ReadonlyArray<AgentMessage>): AsyncIterable<AgentEvent | string>;
  confirmBooking?: (bookingId: string) => Promise<BookingActionResult>;
  cancelBooking?: (bookingId: string) => Promise<BookingActionResult>;
}

export type RuntimeState = "idle" | "listening" | "thinking" | "speaking";

const TZ = "America/Argentina/Buenos_Aires";
const timeFormatter = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
export const stamp = (date = new Date()): string => timeFormatter.format(date);

export interface RuntimeHooks {
  onMessage?: (message: AgentMessage) => void;
  onToken?: () => void;
}

export function useAgentRuntime(provider: AgentProvider, hooks: RuntimeHooks = {}) {
  const messages = ref<AgentMessage[]>([]);
  const draft = ref("");
  const focused = ref(false);
  const busy = ref(false);
  const approvalBusy = ref(false);
  const error = ref<string | null>(null);
  const pendingAction = ref<BookingApprovalAction | null>(null);
  const approvalResult = ref<BookingActionResult | null>(null);
  const nextId = shallowRef(1);
  let streamFrame = 0;
  let pendingText = "";
  let replyId = -1;

  const state = computed<RuntimeState>(() => {
    if (messages.value.some((message) => message.streaming)) return "speaking";
    if (busy.value || approvalBusy.value) return "thinking";
    if (focused.value || draft.value.length > 0) return "listening";
    return "idle";
  });
  const canSend = computed(() => draft.value.trim().length > 0 && !busy.value && !approvalBusy.value);

  const push = (role: AgentRole, text: string, streaming = false): AgentMessage => {
    const message: AgentMessage = { id: nextId.value++, role, text, time: stamp(), streaming };
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
    if (!target) { pendingText = ""; return; }
    target.text += pendingText;
    pendingText = "";
    hooks.onToken?.();
  };
  const scheduleStreamFlush = () => { if (!streamFrame) streamFrame = requestAnimationFrame(flushStream); };
  const flushStreamNow = () => { if (streamFrame) cancelAnimationFrame(streamFrame); streamFrame = 0; flushStream(); };

  const handleEvent = (event: AgentEvent | string): void => {
    if (typeof event === "string" || event.type === "token") {
      const text = typeof event === "string" ? event : event.text;
      if (!text) return;
      if (replyId < 0) { busy.value = false; replyId = push("agent", "", true).id; }
      pendingText += text;
      scheduleStreamFlush();
      return;
    }
    if (event.type === "action_required") {
      pendingAction.value = event.action;
      approvalResult.value = null;
      return;
    }
    pendingAction.value = null;
  };

  const send = async () => {
    const question = draft.value.trim();
    if (!question || busy.value || approvalBusy.value) return;
    draft.value = "";
    error.value = null;
    approvalResult.value = null;
    push("user", question);
    busy.value = true;
    const history = messages.value.slice(0, -1);
    replyId = -1;
    pendingText = "";
    let receivedContent = false;
    try {
      for await (const event of provider.ask(question, history)) {
        if (typeof event === "string" || event.type === "token") receivedContent = true;
        handleEvent(event);
      }
      flushStreamNow();
      if (!receivedContent) throw new Error("Agent provider returned no conversational content");
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

  const confirmPending = async () => {
    const action = pendingAction.value;
    if (!action || !provider.confirmBooking || approvalBusy.value) return;
    approvalBusy.value = true;
    error.value = null;
    try {
      approvalResult.value = await provider.confirmBooking(action.bookingId);
      pendingAction.value = null;
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "The meeting could not be confirmed.";
      console.error("[agent-os] booking confirmation failed", cause);
    } finally {
      approvalBusy.value = false;
    }
  };

  const cancelPending = async () => {
    const action = pendingAction.value;
    if (!action || !provider.cancelBooking || approvalBusy.value) return;
    approvalBusy.value = true;
    error.value = null;
    try {
      approvalResult.value = await provider.cancelBooking(action.bookingId);
      pendingAction.value = null;
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "The meeting could not be cancelled.";
      console.error("[agent-os] booking cancellation failed", cause);
    } finally {
      approvalBusy.value = false;
    }
  };

  const reset = () => {
    if (streamFrame) cancelAnimationFrame(streamFrame);
    streamFrame = 0; pendingText = ""; replyId = -1; messages.value = []; draft.value = "";
    error.value = null; pendingAction.value = null; approvalResult.value = null; approvalBusy.value = false;
  };

  return { messages, draft, focused, busy, approvalBusy, error, state, canSend, pendingAction, approvalResult, send, confirmPending, cancelPending, reset };
}
