export type Experience = {
  period: string;
  role: string;
  company: string;
  summary: string;
  focus: string[];
};

export const experiences: Experience[] = [
  {
    period: "JAN 2024 — NOW",
    role: "AI Engineer / Full-Stack Developer",
    company: "Freelance · AI / Backend",
    summary:
      "Freelance AI and backend work running in parallel through Apr 2026 and becoming the primary professional activity from May 2026, spanning insurance RAG, financial MCP tooling, semantic product search and Python/FastAPI services.",
    focus: ["RAG", "MCP", "Python / FastAPI", "Semantic Search"],
  },
  {
    period: "DEC 2025 — APR 2026",
    role: "AI Engineer",
    company: "AiRoss · AI Systems",
    summary:
      "Agentic NL-to-SQL, local-first document extraction for sensitive banking documents and AI recruiting workflows with validation, security guardrails, auditability and reusable automation modules.",
    focus: ["NL→SQL", "Document AI", "Local-first", "AI Workflows"],
  },
  {
    period: "JAN 2023 — SEP 2025",
    role: "Software Engineer",
    company: "FK Tech · Backend / Full-Stack",
    summary:
      "Multi-agent RAG over internal knowledge bases, CI/CD automation and legacy-system refactoring, with measurable improvements in onboarding, debugging, deployment time, production incidents and execution performance.",
    focus: ["RAG", "CI/CD", "Refactoring", "Backend"],
  },
];
