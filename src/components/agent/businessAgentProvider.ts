import type { AgentMessage, AgentProvider } from "./useAgentRuntime";

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

async function* streamBusinessAgent(question: string): AsyncIterable<string> {
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

      const payload = JSON.parse(frame.data) as { text?: string; message?: string };
      if (frame.event === "token" && payload.text) yield payload.text;
      if (frame.event === "error") throw new Error(payload.message ?? "Business agent unavailable");
    }

    if (done) break;
  }
}

export const businessAgentProvider: AgentProvider = {
  async *ask(question: string, _history: ReadonlyArray<AgentMessage>): AsyncIterable<string> {
    yield* streamBusinessAgent(question);
  },
};
