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

function uniqueFacts(facts) {
  const unique = new Map();
  for (const fact of facts) {
    unique.set(`${fact.source}\u0000${fact.text}`, fact);
  }
  return [...unique.values()];
}

function appendFacts(target, result) {
  for (const fact of result?.facts || []) {
    if (fact && typeof fact.text === "string" && fact.text.length > 0) {
      target.push({ source: String(fact.source || ""), text: fact.text });
    }
  }
}

function factsFromTrace(trace) {
  const facts = [];

  for (const round of trace?.rounds || []) {
    for (const call of round?.tool_calls || []) {
      const envelope = call?.result;
      appendFacts(facts, envelope?.result || envelope);
    }
  }

  return uniqueFacts(facts);
}

function factsFromContext(messages) {
  const facts = [];

  for (const message of messages || []) {
    if (message?.role !== "tool" || typeof message.content !== "string") {
      continue;
    }

    let envelope;
    try {
      envelope = JSON.parse(message.content);
    } catch (_error) {
      continue;
    }

    appendFacts(facts, envelope?.result || envelope);
  }

  return uniqueFacts(facts);
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
  let returnedContext = [];

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

    if (event.name === "context" && Array.isArray(event.payload?.messages)) {
      returnedContext = event.payload.messages;
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

  const tracedFacts = factsFromTrace(trace);
  const sources = tracedFacts.length > 0 ? tracedFacts : factsFromContext(returnedContext);

  return {
    answer: answer.join("").trim(),
    context: sources.map((fact) => fact.text),
    sources,
    tools: toolsFromTrace(trace, streamedTools),
    trace,
  };
};
