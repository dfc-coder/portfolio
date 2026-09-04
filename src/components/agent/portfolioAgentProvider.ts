import type {
  AgentContextMessage,
  AgentEvent,
  AgentProvider,
} from "./useAgentRuntime";

const apiBaseUrl = (): string => {
  const configured = import.meta.env.VITE_AGENT_API_URL?.trim();
  if (!configured) {
    throw new Error("VITE_AGENT_API_URL is not configured");
  }
  return configured.replace(/\/$/, "");
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

async function* streamPortfolioAgent(
  question: string,
  context: ReadonlyArray<AgentContextMessage>,
): AsyncIterable<AgentEvent> {
  const response = await fetch(`${apiBaseUrl()}/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: question, context }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Portfolio agent request failed with HTTP ${response.status}`);
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
      if (frame.event === "status") {
        const phase = String(payload.phase);
        if (phase === "model" || phase === "responding") {
          yield {
            type: "status",
            phase,
            round: Number(payload.round ?? 0),
          };
        }
      }
      if (frame.event === "tool" && payload.name) {
        const state = String(payload.state);
        if (state === "running" || state === "done") {
          yield {
            type: "tool",
            name: String(payload.name),
            state,
            round: Number(payload.round ?? 0),
            ok: typeof payload.ok === "boolean" ? payload.ok : undefined,
          };
        }
      }
      if (frame.event === "context" && Array.isArray(payload.messages)) {
        yield {
          type: "context",
          messages: payload.messages as AgentContextMessage[],
        };
      }
      if (frame.event === "error") {
        throw new Error(String(payload.message ?? "Portfolio agent unavailable"));
      }
    }

    if (done) break;
  }
}

export const portfolioAgentProvider: AgentProvider = {
  async *ask(
    question: string,
    context: ReadonlyArray<AgentContextMessage>,
  ): AsyncIterable<AgentEvent> {
    yield* streamPortfolioAgent(question, context);
  },
};
