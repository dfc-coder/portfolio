function parseEvents(raw) {
  const events = [];
  let name = null;
  let data = [];

  function flush() {
    if (!name || data.length === 0) {
      name = null;
      data = [];
      return;
    }

    const payloadText = data.join("\n");
    let payload;
    try {
      payload = JSON.parse(payloadText);
    } catch (error) {
      throw new Error(`Invalid SSE JSON for event ${name}: ${error.message}`);
    }

    events.push({ name, payload });
    name = null;
    data = [];
  }

  for (const line of String(raw || "").split(/\r?\n/)) {
    if (line === "") {
      flush();
      continue;
    }
    if (line.startsWith("event:")) {
      name = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      data.push(line.slice(5).trimStart());
    }
  }
  flush();

  return events;
}

function factsFromTrace(trace) {
  const facts = [];

  for (const round of trace?.rounds || []) {
    for (const call of round?.tool_calls || []) {
      const envelope = call?.result;
      const result = envelope?.result || envelope;
      for (const fact of result?.facts || []) {
        if (fact && typeof fact.text === "string") {
          facts.push({ source: String(fact.source || ""), text: fact.text });
        }
      }
    }
  }

  const unique = new Map();
  for (const fact of facts) {
    unique.set(`${fact.source}\u0000${fact.text}`, fact);
  }
  return [...unique.values()];
}

function toolsFromTrace(trace, streamedTools) {
  if (!trace) {
    return streamedTools;
  }

  const tools = [];
  for (const round of trace.rounds || []) {
    for (const call of round?.tool_calls || []) {
      tools.push({
        name: String(call?.name || ""),
        arguments: call?.arguments || null,
        ok: call?.ok ?? null,
      });
    }
  }
  return tools;
}

module.exports = function transformResponse(_json, text) {
  const answer = [];
  const streamedTools = [];
  let trace = null;

  for (const event of parseEvents(text)) {
    if (event.name === "token" && typeof event.payload?.text === "string") {
      answer.push(event.payload.text);
      continue;
    }

    if (event.name === "tool" && event.payload?.state === "running") {
      streamedTools.push({
        name: String(event.payload?.name || ""),
        arguments: null,
        ok: null,
      });
      continue;
    }

    if (event.name === "trace") {
      trace = event.payload;
      continue;
    }

    if (event.name === "error") {
      throw new Error(String(event.payload?.message || "portfolio agent error"));
    }
  }

  const sources = factsFromTrace(trace);
  return {
    answer: answer.join("").trim(),
    context: sources.map((fact) => fact.text),
    sources,
    tools: toolsFromTrace(trace, streamedTools),
    trace,
  };
};
