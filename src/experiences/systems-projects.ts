import type { SystemGraphDefinition } from "../graph/system-graph";

export type SystemProject = {
  id: string;
  code: string;
  field: string;
  title: string;
  premise: string;
  detail: string;
  stack: string[];
  outcome: string;
  graph: SystemGraphDefinition;
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
      direction: "LR",
      nodes: [
        { id: "request", label: "REQUEST", step: 0 },
        { id: "router", label: "ROUTER", step: 1 },
        { id: "reason", label: "REASON", step: 2, accent: true },
        { id: "tools", label: "TOOLS", step: 3 },
        { id: "verify", label: "VERIFY", step: 4 },
        { id: "reflect", label: "REFLECT", step: 5, accent: true },
        { id: "model", label: "LOCAL MODEL", step: 6 },
      ],
      edges: [
        { from: "request", to: "router", step: 0 },
        { from: "router", to: "reason", step: 1, label: "PLAN" },
        { from: "reason", to: "tools", step: 2 },
        { from: "tools", to: "verify", step: 3, label: "RESULT" },
        { from: "verify", to: "reflect", step: 4 },
        { from: "reflect", to: "reason", step: 5, label: "RETRY", kind: "feedback" },
        { from: "verify", to: "model", step: 6 },
        { from: "model", to: "reason", step: 7, kind: "feedback" },
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
      direction: "LR",
      nodes: [
        { id: "document", label: "DOCUMENT", step: 0 },
        { id: "segment", label: "SEGMENT", step: 1 },
        { id: "rank", label: "RANK", step: 2, accent: true },
        { id: "extract", label: "EXTRACT", step: 3 },
        { id: "validate", label: "VALIDATE", step: 4 },
        { id: "review", label: "REVIEW", step: 5 },
        { id: "evidence", label: "EVIDENCE", step: 6, accent: true },
      ],
      edges: [
        { from: "document", to: "segment", step: 0 },
        { from: "segment", to: "rank", step: 1 },
        { from: "rank", to: "extract", step: 2, label: "FIELD" },
        { from: "extract", to: "validate", step: 3 },
        { from: "segment", to: "review", step: 4 },
        { from: "review", to: "extract", step: 5, label: "UNCERTAIN" },
        { from: "validate", to: "evidence", step: 6 },
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
      direction: "LR",
      nodes: [
        { id: "question", label: "QUESTION", step: 0 },
        { id: "intent", label: "INTENT", step: 1, accent: true },
        { id: "schema", label: "SCHEMA", step: 2 },
        { id: "policy", label: "POLICY", step: 3 },
        { id: "planner", label: "PLANNER", step: 4 },
        { id: "sql", label: "GUARDED SQL", step: 5, accent: true },
      ],
      edges: [
        { from: "question", to: "intent", step: 0 },
        { from: "intent", to: "schema", step: 1, label: "GROUND" },
        { from: "intent", to: "policy", step: 2, label: "BOUND" },
        { from: "schema", to: "planner", step: 3 },
        { from: "policy", to: "planner", step: 4 },
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
      direction: "LR",
      nodes: [
        { id: "agent", label: "AGENT", step: 0 },
        { id: "contract", label: "TOOL CONTRACT", step: 1, accent: true },
        { id: "quote", label: "QUOTE", step: 2 },
        { id: "history", label: "HISTORY", step: 3 },
        { id: "signals", label: "SIGNALS", step: 4 },
        { id: "typed", label: "TYPED RESULT", step: 5 },
        { id: "evidence", label: "EVIDENCE", step: 6, accent: true },
      ],
      edges: [
        { from: "agent", to: "contract", step: 0 },
        { from: "contract", to: "quote", step: 1 },
        { from: "contract", to: "history", step: 2 },
        { from: "contract", to: "signals", step: 3 },
        { from: "quote", to: "typed", step: 4 },
        { from: "history", to: "typed", step: 5 },
        { from: "signals", to: "typed", step: 6 },
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
      direction: "LR",
      nodes: [
        { id: "need", label: "NEED", step: 0 },
        { id: "attributes", label: "ATTRIBUTES", step: 1, accent: true },
        { id: "semantic", label: "SEMANTIC", step: 2 },
        { id: "keyword", label: "KEYWORD", step: 3 },
        { id: "vector", label: "VECTOR SET", step: 4 },
        { id: "lexical", label: "LEXICAL SET", step: 5 },
        { id: "rank", label: "RANK", step: 6 },
        { id: "explain", label: "EXPLAIN", step: 7, accent: true },
      ],
      edges: [
        { from: "need", to: "attributes", step: 0 },
        { from: "attributes", to: "semantic", step: 1, label: "EMBED" },
        { from: "attributes", to: "keyword", step: 2, label: "MATCH" },
        { from: "semantic", to: "vector", step: 3 },
        { from: "keyword", to: "lexical", step: 4 },
        { from: "vector", to: "rank", step: 5 },
        { from: "lexical", to: "rank", step: 6 },
        { from: "rank", to: "explain", step: 7 },
      ],
    },
  },
];
