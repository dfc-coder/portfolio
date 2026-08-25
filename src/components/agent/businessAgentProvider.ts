import type {
  AgentEvent,
  AgentMessage,
  AgentProvider,
  BookingActionResult,
  BookingApprovalAction,
} from "./useAgentRuntime";

const SESSION_KEY = "portfolio-business-representative-session";

const apiBaseUrl = (): string => {
  const configured = import.meta.env.VITE_AGENT_API_URL?.trim();
  if (!configured) {
    throw new Error("VITE_AGENT_API_URL is not configured");
  }
  return configured.replace(/\/$/, "");
};

const sessionId = (): string => {
  const existing = window.sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;

  const created = `web-${crypto.randomUUID()}`;
  window.sessionStorage.setItem(SESSION_KEY, created);
  return created;
};

type SseFrame = {
  event: string;
  data: string;
};

const parseFrame = (raw: string): SseFrame | null => {
  let event = "message";
  const data: string[] = [];

  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }

  return data.length > 0 ? { event, data: data.join("\n") } : null;
};

const actionFromPayload = (
  payload: Record<string, unknown>,
): BookingApprovalAction => {
  if (payload.type !== "confirm_booking") {
    throw new Error("Unsupported agent action");
  }

  return {
    type: "confirm_booking",
    bookingId: String(payload.booking_id ?? ""),
    subject: String(payload.subject ?? ""),
    visitorName: String(payload.visitor_name ?? ""),
    visitorEmail: String(payload.visitor_email ?? ""),
    start: String(payload.start ?? ""),
    end: String(payload.end ?? ""),
    expiresAt: payload.expires_at ? String(payload.expires_at) : null,
  };
};

async function* streamBusinessAgent(
  question: string,
): AsyncIterable<AgentEvent> {
  const response = await fetch(`${apiBaseUrl()}/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId(),
      message: question,
    }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Business agent request failed with HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    let separator = buffer.indexOf("\n\n");
    while (separator >= 0) {
      const rawFrame = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      separator = buffer.indexOf("\n\n");

      const frame = parseFrame(rawFrame);
      if (!frame) continue;

      const payload = JSON.parse(frame.data) as Record<string, unknown>;
      if (frame.event === "token" && payload.text) {
        yield { type: "token", text: String(payload.text) };
      }
      if (frame.event === "action_required") {
        yield { type: "action_required", action: actionFromPayload(payload) };
      }
      if (frame.event === "action_cleared") {
        yield { type: "action_cleared" };
      }
      if (frame.event === "error") {
        throw new Error(String(payload.message ?? "Business agent unavailable"));
      }
    }

    if (done) break;
  }
}

const bookingAction = async (
  bookingId: string,
  action: "confirm" | "cancel",
): Promise<BookingActionResult> => {
  const response = await fetch(
    `${apiBaseUrl()}/v1/bookings/${encodeURIComponent(bookingId)}/${action}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId() }),
    },
  );

  const payload = (await response.json()) as Record<string, unknown>;
  if (!response.ok) {
    throw new Error(String(payload.detail ?? `Booking ${action} failed`));
  }

  return {
    status: payload.status === "confirmed" ? "confirmed" : "cancelled",
    bookingId: String(payload.booking_id ?? bookingId),
    eventId: payload.event_id ? String(payload.event_id) : null,
    htmlLink: payload.html_link ? String(payload.html_link) : null,
    start: payload.start ? String(payload.start) : null,
    end: payload.end ? String(payload.end) : null,
  };
};

export const businessAgentProvider: AgentProvider = {
  async *ask(
    question: string,
    _history: ReadonlyArray<AgentMessage>,
  ): AsyncIterable<AgentEvent> {
    yield* streamBusinessAgent(question);
  },

  confirmBooking(bookingId: string): Promise<BookingActionResult> {
    return bookingAction(bookingId, "confirm");
  },

  cancelBooking(bookingId: string): Promise<BookingActionResult> {
    return bookingAction(bookingId, "cancel");
  },
};
