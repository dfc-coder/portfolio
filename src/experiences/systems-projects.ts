export type GraphNode = {
  id: string;
  label: string;
  x: number;
  y: number;
  step: number;
  accent?: boolean;
};

export type GraphEdge = {
  from: string;
  to: string;
  step: number;
  label?: string;
  path?: string;
};

export type SystemProject = {
  id: string;
  code: string;
  field: string;
  title: string;
  premise: string;
  detail: string;
  stack: string[];
  outcome: string;
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
};

export const systemsProjects: SystemProject[] = [
  {
    id: "00",
    code: "REACT—AI",
    field: "AGENTIC AI / LOCAL-FIRST",
    title: "Reflective ReAct Agent",
    premise:
      "A general-purpose local assistant can reason, use tools and recover from execution failures without being tied to a specific domain.",
    detail:
      "A bounded ReAct loop combines injected tools, deterministic verification and triggered reflection. Local inference runs on Qwen through llama.cpp, with private retrieval and specialised embedding/reranking, while an AWS-compatible runtime provides the infrastructure needed to test the same agent as a real system.",
    stack: [
      "Python",
      "Qwen3.5 2B",
      "ReAct + Reflection",
      "llama.cpp",
      "OpenVINO",
      "LangChain",
      "AWS CDK / Lambda",
      "S3 Vectors",
      "Podman / Floci",
    ],
    outcome: "General-purpose local agent · controlled autonomous execution",
    graph: {
      nodes: [
        { id: "request", label: "REQUEST", x: 6, y: 32, step: 0 },
        { id: "router", label: "ROUTER", x: 20, y: 32, step: 1 },
        { id: "reason", label: "REASON", x: 42, y: 18, step: 2, accent: true },
        { id: "tools", label: "TOOLS", x: 64, y: 18, step: 3 },
        { id: "verify", label: "VERIFY", x: 64, y: 46, step: 4 },
        { id: "reflect", label: "REFLECT", x: 42, y: 46, step: 5, accent: true },
        { id: "model", label: "LOCAL MODEL", x: 88, y: 32, step: 6 },
      ],
      edges: [
        { from: "request", to: "router", step: 0 },
        { from: "router", to: "reason", step: 1, label: "PLAN", path: "M 20 32 H 31 V 18 H 42" },
        { from: "reason", to: "tools", step: 2 },
        { from: "tools", to: "verify", step: 3, label: "RESULT", path: "M 64 18 V 46" },
        { from: "verify", to: "reflect", step: 4 },
        { from: "reflect", to: "reason", step: 5, label: "RETRY", path: "M 42 46 V 18" },
        { from: "verify", to: "model", step: 6, path: "M 64 46 H 76 V 32 H 88" },
        { from: "model", to: "reason", step: 7, path: "M 88 32 H 78 V 9 H 42 V 18" },
      ],
    },
  },
  {
    id: "01",
    code: "DOC—AI",
    field: "PRIVATE AI / BANKING",
    title: "Secure Document Extractor",
    premise:
      "Sensitive documents become structured financial data without leaving isolated infrastructure.",
    detail:
      "PDF and image documents are segmented, ranked by field and processed by local models. Typed validation and evidence links keep uncertainty reviewable instead of hiding it behind a confident answer.",
    stack: ["Python", "FastAPI", "Docling", "Local LLM", "Redis"],
    outcome: "Private by design · evidence-linked output",
    graph: {
      nodes: [
        { id: "document", label: "DOCUMENT", x: 7, y: 18, step: 0 },
        { id: "segment", label: "SEGMENT", x: 25, y: 18, step: 1 },
        { id: "rank", label: "RANK", x: 43, y: 18, step: 2, accent: true },
        { id: "extract", label: "EXTRACT", x: 61, y: 18, step: 3 },
        { id: "validate", label: "VALIDATE", x: 79, y: 18, step: 4 },
        { id: "review", label: "REVIEW", x: 43, y: 49, step: 5 },
        { id: "evidence", label: "EVIDENCE", x: 82, y: 49, step: 6, accent: true },
      ],
      edges: [
        { from: "document", to: "segment", step: 0 },
        { from: "segment", to: "rank", step: 1 },
        { from: "rank", to: "extract", step: 2, label: "FIELD" },
        { from: "extract", to: "validate", step: 3 },
        { from: "segment", to: "review", step: 4, path: "M 25 18 V 49 H 43" },
        { from: "review", to: "extract", step: 5, label: "UNCERTAIN", path: "M 43 49 H 52 V 18 H 61" },
        { from: "validate", to: "evidence", step: 6, path: "M 79 18 H 82 V 49" },
      ],
    },
  },
  {
    id: "02",
    code: "NL→SQL",
    field: "AGENTS / DATA ACCESS",
    title: "Natural Language to SQL",
    premise:
      "A conversational question reaches data without granting unrestricted database access.",
    detail:
      "A planner resolves intent, retrieves only relevant schema, applies business rules and rejects ambiguous or unsafe operations before generating a guarded query.",
    stack: ["Python", "Tool calling", "Schema RAG", "SQL policies", "Evaluation"],
    outcome: "Grounded questions · guarded execution",
    graph: {
      nodes: [
        { id: "question", label: "QUESTION", x: 10, y: 10, step: 0 },
        { id: "intent", label: "INTENT", x: 35, y: 10, step: 1, accent: true },
        { id: "schema", label: "SCHEMA", x: 24, y: 32, step: 2 },
        { id: "policy", label: "POLICY", x: 47, y: 32, step: 3 },
        { id: "planner", label: "PLANNER", x: 35, y: 53, step: 4 },
        { id: "sql", label: "GUARDED SQL", x: 79, y: 53, step: 5, accent: true },
      ],
      edges: [
        { from: "question", to: "intent", step: 0 },
        { from: "intent", to: "schema", step: 1, label: "GROUND", path: "M 35 10 V 20 H 24 V 32" },
        { from: "intent", to: "policy", step: 2, label: "BOUND", path: "M 35 10 V 20 H 47 V 32" },
        { from: "schema", to: "planner", step: 3, path: "M 24 32 V 43 H 35 V 53" },
        { from: "policy", to: "planner", step: 4, path: "M 47 32 V 43 H 35 V 53" },
        { from: "planner", to: "sql", step: 5 },
      ],
    },
  },
  {
    id: "03",
    code: "MCP—03",
    field: "FINTECH / AGENT TOOLS",
    title: "Financial MCP Server",
    premise:
      "Market data becomes explicit, reusable instruments rather than an opaque recommendation engine.",
    detail:
      "Each capability exposes a strict contract, identifiable source and predictable output so specialised agents can combine evidence without hiding how an interpretation was produced.",
    stack: ["MCP", "Python", "Market data", "Typed tools", "Agents"],
    outcome: "Signals organised as auditable tools",
    graph: {
      nodes: [
        { id: "agent", label: "AGENT", x: 7, y: 32, step: 0 },
        { id: "contract", label: "TOOL CONTRACT", x: 28, y: 32, step: 1, accent: true },
        { id: "quote", label: "QUOTE", x: 53, y: 10, step: 2 },
        { id: "history", label: "HISTORY", x: 53, y: 32, step: 3 },
        { id: "signals", label: "SIGNALS", x: 53, y: 54, step: 4 },
        { id: "typed", label: "TYPED RESULT", x: 76, y: 32, step: 5 },
        { id: "evidence", label: "EVIDENCE", x: 92, y: 32, step: 6, accent: true },
      ],
      edges: [
        { from: "agent", to: "contract", step: 0 },
        { from: "contract", to: "quote", step: 1, path: "M 28 32 H 39 V 10 H 53" },
        { from: "contract", to: "history", step: 2 },
        { from: "contract", to: "signals", step: 3, path: "M 28 32 H 39 V 54 H 53" },
        { from: "quote", to: "typed", step: 4, path: "M 53 10 H 65 V 32 H 76" },
        { from: "history", to: "typed", step: 5 },
        { from: "signals", to: "typed", step: 6, path: "M 53 54 H 65 V 32 H 76" },
        { from: "typed", to: "evidence", step: 7 },
      ],
    },
  },
  {
    id: "04",
    code: "SEARCH",
    field: "SEMANTIC SEARCH / PRODUCT",
    title: "Intent-aware Shopping Assistant",
    premise:
      "Product discovery starts from a real need, not from exact keyword matching.",
    detail:
      "Incomplete language is converted into comparable attributes, hybrid retrieval candidates and explainable ranking signals evaluated independently from the conversational layer.",
    stack: ["TypeScript", "Embeddings", "Hybrid search", "Catalog API", "Metrics"],
    outcome: "Faster discovery · explainable relevance",
    graph: {
      nodes: [
        { id: "need", label: "NEED", x: 7, y: 32, step: 0 },
        { id: "attributes", label: "ATTRIBUTES", x: 23, y: 32, step: 1, accent: true },
        { id: "semantic", label: "SEMANTIC", x: 42, y: 13, step: 2 },
        { id: "keyword", label: "KEYWORD", x: 42, y: 51, step: 3 },
        { id: "vector", label: "VECTOR SET", x: 62, y: 13, step: 4 },
        { id: "lexical", label: "LEXICAL SET", x: 62, y: 51, step: 5 },
        { id: "rank", label: "RANK", x: 79, y: 32, step: 6 },
        { id: "explain", label: "EXPLAIN", x: 93, y: 32, step: 7, accent: true },
      ],
      edges: [
        { from: "need", to: "attributes", step: 0 },
        { from: "attributes", to: "semantic", step: 1, label: "EMBED", path: "M 23 32 H 31 V 13 H 42" },
        { from: "attributes", to: "keyword", step: 2, label: "MATCH", path: "M 23 32 H 31 V 51 H 42" },
        { from: "semantic", to: "vector", step: 3 },
        { from: "keyword", to: "lexical", step: 4 },
        { from: "vector", to: "rank", step: 5, path: "M 62 13 H 70 V 32 H 79" },
        { from: "lexical", to: "rank", step: 6, path: "M 62 51 H 70 V 32 H 79" },
        { from: "rank", to: "explain", step: 7 },
      ],
    },
  },
  {
    id: "05",
    code: "TRACE—RUST",
    field: "OBSERVABILITY / LOCAL-FIRST",
    title: "PocketTrace",
    premise:
      "Application traces can stay local and still become searchable, reviewable execution evidence.",
    detail:
      "A single Rust binary ingests bounded trace snapshots, validates their references and payload limits, normalizes runs into execution trees and persists them atomically in SQLite/WAL. A local HTTP UI, search, CLI export and SSE updates expose the same evidence without uploading telemetry or introducing a cloud dependency.",
    stack: [
      "Rust",
      "SQLite / WAL",
      "rusqlite",
      "serde",
      "Local HTTP",
      "SSE",
      "CLI",
      "Security hardening",
    ],
    outcome: "Local trace evidence · zero cloud telemetry",
    graph: {
      nodes: [
        { id: "ingest", label: "SNAPSHOT", x: 7, y: 32, step: 0 },
        { id: "validate", label: "VALIDATE", x: 24, y: 32, step: 1, accent: true },
        { id: "normalize", label: "EXEC TREE", x: 43, y: 32, step: 2 },
        { id: "sqlite", label: "SQLITE/WAL", x: 62, y: 32, step: 3, accent: true },
        { id: "viewer", label: "LOCAL UI", x: 84, y: 13, step: 4 },
        { id: "search", label: "SEARCH", x: 84, y: 32, step: 5 },
        { id: "export", label: "EXPORT", x: 84, y: 51, step: 6 },
      ],
      edges: [
        { from: "ingest", to: "validate", step: 0, label: "SCHEMA" },
        { from: "validate", to: "normalize", step: 1 },
        { from: "normalize", to: "sqlite", step: 2, label: "ATOMIC" },
        { from: "sqlite", to: "viewer", step: 3, path: "M 62 32 H 73 V 13 H 84" },
        { from: "sqlite", to: "search", step: 4 },
        { from: "sqlite", to: "export", step: 5, path: "M 62 32 H 73 V 51 H 84" },
      ],
    },
  },
  {
    id: "06",
    code: "VOICE—ACP",
    field: "VOICE AI / REALTIME SYSTEMS",
    title: "Xarlatan",
    premise:
      "A text-oriented AI agent can gain realtime speech without moving its LLM, memory or tools into the voice runtime.",
    detail:
      "A Go voice gateway owns microphone capture, Silero VAD, wake and endpointing, persistent Whisper/OpenVINO STT, sentence-level Kokoro TTS and playback. ACP v1 keeps the external agent behind a clean wire boundary, while per-turn cancellation, stale-delta rejection and wake-qualified barge-in keep latency and interruption behavior deterministic.",
    stack: [
      "Go",
      "Silero VAD",
      "Whisper / OpenVINO",
      "ACP v1",
      "Kokoro TTS",
      "ALSA",
      "Turn cancellation",
      "Latency instrumentation",
    ],
    outcome: "Low-latency voice gateway · agent-agnostic boundary",
    graph: {
      nodes: [
        { id: "mic", label: "MIC", x: 6, y: 32, step: 0 },
        { id: "vad", label: "VAD / WAKE", x: 20, y: 32, step: 1, accent: true },
        { id: "stt", label: "STT", x: 37, y: 17, step: 2 },
        { id: "acp", label: "ACP v1", x: 55, y: 17, step: 3, accent: true },
        { id: "agent", label: "AGENT", x: 76, y: 17, step: 4 },
        { id: "cancel", label: "CANCEL", x: 37, y: 49, step: 5 },
        { id: "tts", label: "KOKORO", x: 56, y: 49, step: 6 },
        { id: "speaker", label: "SPEAKER", x: 78, y: 49, step: 7 },
      ],
      edges: [
        { from: "mic", to: "vad", step: 0 },
        { from: "vad", to: "stt", step: 1, label: "FINAL", path: "M 20 32 H 28 V 17 H 37" },
        { from: "stt", to: "acp", step: 2 },
        { from: "acp", to: "agent", step: 3, label: "PROMPT" },
        { from: "agent", to: "tts", step: 4, label: "CHUNKS", path: "M 76 17 H 66 V 49 H 56" },
        { from: "tts", to: "speaker", step: 5 },
        { from: "vad", to: "cancel", step: 6, label: "BARGE-IN", path: "M 20 32 H 28 V 49 H 37" },
        { from: "cancel", to: "acp", step: 7, label: "CANCEL", path: "M 37 49 H 46 V 17 H 55" },
        { from: "cancel", to: "tts", step: 8, label: "STOP" },
      ],
    },
  },
];
