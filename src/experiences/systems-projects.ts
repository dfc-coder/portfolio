import type { GraphDiagramDefinition } from "../graph/model";

export type SystemProject = {
  id: string;
  code: string;
  field: string;
  title: string;
  premise: string;
  detail: string;
  stack: string[];
  outcome: string;
  graph: GraphDiagramDefinition;
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
      kind: "graph",
      direction: "LR",
      nodes: [
        { id: "request", label: "REQUEST" },
        { id: "router", label: "ROUTER" },
        { id: "reason", label: "REASON", kind: "accent" },
        { id: "tools", label: "TOOLS" },
        { id: "verify", label: "VERIFY" },
        { id: "reflect", label: "REFLECT", kind: "accent" },
        { id: "model", label: "LOCAL MODEL" },
      ],
      edges: [
        { from: "request", to: "router" },
        { from: "router", to: "reason", label: "PLAN" },
        { from: "reason", to: "tools" },
        { from: "tools", to: "verify", label: "RESULT" },
        { from: "verify", to: "reflect" },
        { from: "reflect", to: "reason", label: "RETRY", kind: "feedback" },
        { from: "verify", to: "model" },
        { from: "model", to: "reason", kind: "feedback" },
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
      kind: "graph",
      direction: "LR",
      nodes: [
        { id: "document", label: "DOCUMENT" },
        { id: "segment", label: "SEGMENT" },
        { id: "rank", label: "RANK", kind: "accent" },
        { id: "extract", label: "EXTRACT" },
        { id: "validate", label: "VALIDATE" },
        { id: "review", label: "REVIEW" },
        { id: "evidence", label: "EVIDENCE", kind: "accent" },
      ],
      edges: [
        { from: "document", to: "segment" },
        { from: "segment", to: "rank" },
        { from: "rank", to: "extract", label: "FIELD" },
        { from: "extract", to: "validate" },
        { from: "segment", to: "review" },
        { from: "review", to: "extract", label: "UNCERTAIN" },
        { from: "validate", to: "evidence" },
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
      kind: "graph",
      direction: "LR",
      nodes: [
        { id: "question", label: "QUESTION" },
        { id: "intent", label: "INTENT", kind: "accent" },
        { id: "schema", label: "SCHEMA" },
        { id: "policy", label: "POLICY" },
        { id: "planner", label: "PLANNER" },
        { id: "sql", label: "GUARDED SQL", kind: "accent" },
      ],
      edges: [
        { from: "question", to: "intent" },
        { from: "intent", to: "schema", label: "GROUND" },
        { from: "intent", to: "policy", label: "BOUND" },
        { from: "schema", to: "planner" },
        { from: "policy", to: "planner" },
        { from: "planner", to: "sql" },
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
      kind: "graph",
      direction: "LR",
      nodes: [
        { id: "agent", label: "AGENT" },
        { id: "contract", label: "TOOL CONTRACT", kind: "accent" },
        { id: "quote", label: "QUOTE" },
        { id: "history", label: "HISTORY" },
        { id: "signals", label: "SIGNALS" },
        { id: "typed", label: "TYPED RESULT" },
        { id: "evidence", label: "EVIDENCE", kind: "accent" },
      ],
      edges: [
        { from: "agent", to: "contract" },
        { from: "contract", to: "quote" },
        { from: "contract", to: "history" },
        { from: "contract", to: "signals" },
        { from: "quote", to: "typed" },
        { from: "history", to: "typed" },
        { from: "signals", to: "typed" },
        { from: "typed", to: "evidence" },
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
      kind: "graph",
      direction: "LR",
      nodes: [
        { id: "need", label: "NEED" },
        { id: "attributes", label: "ATTRIBUTES", kind: "accent" },
        { id: "semantic", label: "SEMANTIC" },
        { id: "keyword", label: "KEYWORD" },
        { id: "vector", label: "VECTOR SET" },
        { id: "lexical", label: "LEXICAL SET" },
        { id: "rank", label: "RANK" },
        { id: "explain", label: "EXPLAIN", kind: "accent" },
      ],
      edges: [
        { from: "need", to: "attributes" },
        { from: "attributes", to: "semantic", label: "EMBED" },
        { from: "attributes", to: "keyword", label: "MATCH" },
        { from: "semantic", to: "vector" },
        { from: "keyword", to: "lexical" },
        { from: "vector", to: "rank" },
        { from: "lexical", to: "rank" },
        { from: "rank", to: "explain" },
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
      kind: "graph",
      direction: "LR",
      nodes: [
        { id: "ingest", label: "SNAPSHOT" },
        { id: "validate", label: "VALIDATE", kind: "accent" },
        { id: "normalize", label: "EXEC TREE" },
        { id: "sqlite", label: "SQLITE/WAL", kind: "accent" },
        { id: "viewer", label: "LOCAL UI" },
        { id: "search", label: "SEARCH" },
        { id: "export", label: "EXPORT" },
      ],
      edges: [
        { from: "ingest", to: "validate", label: "SCHEMA" },
        { from: "validate", to: "normalize" },
        { from: "normalize", to: "sqlite", label: "ATOMIC" },
        { from: "sqlite", to: "viewer" },
        { from: "sqlite", to: "search" },
        { from: "sqlite", to: "export" },
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
      kind: "graph",
      direction: "LR",
      nodes: [
        { id: "mic", label: "MIC" },
        { id: "vad", label: "VAD / WAKE", kind: "accent" },
        { id: "stt", label: "STT" },
        { id: "acp", label: "ACP v1", kind: "accent" },
        { id: "agent", label: "AGENT" },
        { id: "cancel", label: "CANCEL" },
        { id: "tts", label: "KOKORO" },
        { id: "speaker", label: "SPEAKER" },
      ],
      edges: [
        { from: "mic", to: "vad" },
        { from: "vad", to: "stt", label: "FINAL" },
        { from: "stt", to: "acp" },
        { from: "acp", to: "agent", label: "PROMPT" },
        { from: "agent", to: "tts", label: "CHUNKS" },
        { from: "tts", to: "speaker" },
        { from: "vad", to: "cancel", label: "BARGE-IN" },
        { from: "cancel", to: "acp", label: "CANCEL" },
        { from: "cancel", to: "tts", label: "STOP" },
      ],
    },
  },
];
