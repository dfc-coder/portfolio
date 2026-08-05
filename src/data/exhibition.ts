export type ExhibitKind = "system" | "material" | "study";

export type Exhibit = {
  id: string;
  title: string;
  discipline: string;
  year: string;
  kind: ExhibitKind;
  summary: string;
  role: string;
  technologies: string[];
  image?: string;
};

export type NarrativeBeat = {
  id: string;
  from: number;
  to: number;
  eyebrow: string;
  title: string;
  body: string;
  position: "left" | "right" | "bottom";
};

export const exhibits: Exhibit[] = [
  {
    id: "01",
    title: "Secure Document Extractor",
    discipline: "AI product / banking",
    year: "2026",
    kind: "system",
    summary:
      "A private document-intelligence pipeline that turns sensitive financial files into traceable structured data without external APIs.",
    role: "Product architecture, extraction pipeline, validation and human-review experience.",
    technologies: ["Python", "Local LLM", "Docling", "Schemas", "Audit trail"],
  },
  {
    id: "02",
    title: "Natural Language to SQL",
    discipline: "Agents / data security",
    year: "2026",
    kind: "system",
    summary:
      "A guarded agent that resolves business language against a changing schema and refuses unsafe or ambiguous queries.",
    role: "Agent orchestration, schema retrieval, policy layer and interaction design.",
    technologies: ["Python", "RAG", "SQL", "Policy rules", "Evaluation"],
  },
  {
    id: "03",
    title: "Financial MCP Server",
    discipline: "Fintech / agent tools",
    year: "2025",
    kind: "system",
    summary:
      "A reusable market-tool layer with strict contracts, identifiable sources and outputs designed for coordinated agents.",
    role: "Tool contracts, signal processing, orchestration and explanatory output.",
    technologies: ["MCP", "Python", "Market data", "Tool schemas", "Agents"],
  },
  {
    id: "04",
    title: "Semantic Shopping Assistant",
    discipline: "Search / commerce",
    year: "2025",
    kind: "system",
    summary:
      "A conversational search system that translates incomplete human intent into comparable, explainable product results.",
    role: "Retrieval architecture, semantic ranking, conversation and evaluation.",
    technologies: ["TypeScript", "Embeddings", "Vector search", "Catalog API", "Metrics"],
  },
  {
    id: "05",
    title: "Quiet Joinery",
    discipline: "Furniture system",
    year: "2025",
    kind: "material",
    summary: "A continuous timber structure reduced to a small number of legible joints.",
    role: "Concept, modeling and visualization.",
    technologies: ["Proportion", "Joinery", "Oak", "Leather", "Rendering"],
    image: "/studio/bench-detail.png",
  },
  {
    id: "06",
    title: "Domestic Ritual",
    discipline: "Object design",
    year: "2025",
    kind: "material",
    summary: "An everyday tool treated as a tactile study of weight, grip and temperature.",
    role: "Object concept, CMF and 3D visualization.",
    technologies: ["Ergonomics", "Stone", "Timber", "CMF", "3D"],
    image: "/studio/mortar.png",
  },
  {
    id: "07",
    title: "Portable Frequency",
    discipline: "Product language",
    year: "2025",
    kind: "material",
    summary: "A compact radio family rebuilt through repetition, softness and contemporary color logic.",
    role: "Form language, product family and campaign visualization.",
    technologies: ["Series design", "CMF", "Product form", "Composition"],
    image: "/studio/radios.png",
  },
  {
    id: "08",
    title: "Linear Rest",
    discipline: "Furniture design",
    year: "2025",
    kind: "material",
    summary: "A public bench articulated through exposed structure and a restrained construction rhythm.",
    role: "Furniture concept and detailing.",
    technologies: ["Structure", "Scale", "Assembly", "Visualization"],
    image: "/studio/bench.png",
  },
  {
    id: "09",
    title: "Soft Landscape",
    discipline: "Seating concept",
    year: "2025",
    kind: "material",
    summary: "An upholstered landscape held by a precise tubular frame.",
    role: "Concept, textile study and surface modeling.",
    technologies: ["Textile", "Tubular steel", "Comfort", "Surface model"],
    image: "/studio/lounge-mint.png",
  },
  {
    id: "10",
    title: "Shadow Room",
    discipline: "Spatial direction",
    year: "2025",
    kind: "material",
    summary: "Arches, mineral surfaces and directional light compose a quiet cinematic room.",
    role: "Interior concept, lighting and image direction.",
    technologies: ["Space", "Light", "Texture", "Atmosphere"],
    image: "/studio/interior-shadow.png",
  },
  {
    id: "11",
    title: "Blue Alcove",
    discipline: "Interior visualization",
    year: "2025",
    kind: "material",
    summary: "A colder material study that changes the same architectural grammar through light and density.",
    role: "Spatial styling and visualization.",
    technologies: ["Materiality", "Composition", "Lighting", "Rendering"],
    image: "/studio/interior-blue.png",
  },
  {
    id: "12",
    title: "Primary Structure",
    discipline: "Furniture family",
    year: "2025",
    kind: "material",
    summary: "A chair system assembled from repeated linear parts and flexible braces.",
    role: "System design, construction logic and CMF.",
    technologies: ["Modularity", "Assembly", "Color system", "Stability"],
    image: "/studio/chairs.png",
  },
  {
    id: "13",
    title: "Kempu",
    discipline: "Visual direction",
    year: "2025",
    kind: "material",
    summary: "Oversized typography becomes architecture around an image with rhythmic intensity.",
    role: "Art direction, typography and layout.",
    technologies: ["Typography", "Campaign", "Image", "Editorial rhythm"],
    image: "/studio/kempu.png",
  },
  {
    id: "14",
    title: "Magnolias",
    discipline: "Visual identity",
    year: "2025",
    kind: "material",
    summary: "An editorial identity built around display type and an intimate photographic atmosphere.",
    role: "Identity, editorial system and artwork.",
    technologies: ["Identity", "Type system", "Image treatment", "Editorial"],
    image: "/studio/magnolias.png",
  },
  {
    id: "15",
    title: "Magnetic Circuit Study",
    discipline: "Electronics / object interaction",
    year: "2026",
    kind: "study",
    summary:
      "A physical interaction study where a magnet becomes the visible gesture that closes an electrical circuit.",
    role: "Interaction concept, mechanism research and rapid prototyping.",
    technologies: ["Reed switch", "LED", "Magnets", "Prototype", "Safety"],
  },
  {
    id: "16",
    title: "FDM Form Studies",
    discipline: "3D printing / fabrication",
    year: "2026",
    kind: "study",
    summary:
      "A series of printable objects developed through structural economy, assembly constraints and material finish.",
    role: "Parametric modeling, print preparation and physical iteration.",
    technologies: ["OpenSCAD", "FDM", "PLA+", "PETG", "Iteration"],
  },
];

export const narrativeBeats: NarrativeBeat[] = [
  {
    id: "threshold",
    from: 0,
    to: 0.14,
    eyebrow: "DIEGO CANO / DIGITAL EXHIBITION / 2026",
    title: "SYSTEMS\nWITH A\nHUMAN EDGE.",
    body: "Scroll to move through a practice where software, intelligence and physical matter share the same space.",
    position: "bottom",
  },
  {
    id: "premise",
    from: 0.12,
    to: 0.28,
    eyebrow: "01 / A WAY OF SEEING",
    title: "ENGINEERING\nIS ALSO\nCOMPOSITION.",
    body: "I think in systems, but I observe through proportion, texture, behavior and consequence.",
    position: "left",
  },
  {
    id: "intelligence",
    from: 0.25,
    to: 0.48,
    eyebrow: "02 / SIGNAL",
    title: "MAKE THE\nINVISIBLE\nLEGIBLE.",
    body: "AI and software become useful when uncertainty, evidence and limits remain visible to the person using them.",
    position: "right",
  },
  {
    id: "matter",
    from: 0.45,
    to: 0.7,
    eyebrow: "03 / MATTER",
    title: "IDEAS\nACQUIRE\nMASS.",
    body: "Furniture, objects, spaces and images are not a separate discipline. They are another way to test a system against reality.",
    position: "left",
  },
  {
    id: "workshop",
    from: 0.67,
    to: 0.86,
    eyebrow: "04 / THE WORKSHOP",
    title: "CODE\nENTERS THE\nPHYSICAL WORLD.",
    body: "Electronics, IoT and additive manufacturing close the distance between an abstract rule and a tangible behavior.",
    position: "right",
  },
  {
    id: "exit",
    from: 0.83,
    to: 1,
    eyebrow: "05 / CONTINUE THE CONVERSATION",
    title: "THE LAST\nINTERFACE IS\nA CONVERSATION.",
    body: "The exhibition ends here. The work continues through collaboration, questions and prototypes.",
    position: "bottom",
  },
];
