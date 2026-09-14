export type GalleryItem = {
  src: string;
  title: string;
  type: string;
  description: string;
  alt: string;
};

const DEFAULT_IMAGE_WIDTHS = [320, 480, 640, 800, 960] as const;

export const galleryImageUrl = (src: string, width: number, quality = 80) => {
  if (import.meta.env.DEV) return src;

  const params = new URLSearchParams({
    url: src,
    w: String(width),
    q: String(quality),
  });

  return `/.netlify/images?${params.toString()}`;
};

export const galleryImageSrcSet = (
  src: string,
  widths: readonly number[] = DEFAULT_IMAGE_WIDTHS,
  quality = 80,
) => widths.map((width) => `${galleryImageUrl(src, width, quality)} ${width}w`).join(", ");

export const galleryItems: GalleryItem[] = [
  {
    src: "/studio/bench-detail.png",
    title: "Bench Detail",
    type: "Furniture / Detail Study",
    description:
      "Close study of the bench construction, focusing on joinery, material transitions and the relationship between the timber frame and leather surface.",
    alt: "Close-up of a timber bench showing joinery and leather seating detail.",
  },
  {
    src: "/studio/mortar.png",
    title: "Mortar & Pestle",
    type: "Object / Material Study",
    description:
      "Material study pairing stone and timber in a compact domestic object, with emphasis on weight, grip and tactile contrast.",
    alt: "Stone mortar and timber pestle presented as a material study.",
  },
  {
    src: "/studio/radios.png",
    title: "Portable Radio Series",
    type: "Product / CMF Study",
    description:
      "A portable radio family exploring repeated product geometry, physical controls and variations in colour, material and finish.",
    alt: "Series of portable radios with varied colours, materials and physical controls.",
  },
  {
    src: "/studio/bench.png",
    title: "Timber Bench",
    type: "Furniture / Seating Study",
    description:
      "Minimal bench study built around a clear structural frame, restrained proportions and a continuous upholstered seat.",
    alt: "Minimal timber bench with a continuous upholstered seat.",
  },
  {
    src: "/studio/lounge-mint.png",
    title: "Mint Lounge Chair",
    type: "Furniture / Seating Study",
    description:
      "Lounge seating concept combining soft upholstery with a visible tubular frame and an intentionally light visual profile.",
    alt: "Mint upholstered lounge chair with a visible tubular frame.",
  },
  {
    src: "/studio/interior-shadow-v3.webp",
    title: "Shadow Interior",
    type: "Interior / Spatial Study",
    description:
      "Interior composition centred on contrast, shadow and surface texture to create depth with a restrained material palette.",
    alt: "Interior scene with two lounge chairs under a dark arch, warm framed artwork and strong leaf shadows across textured green walls.",
  },
  {
    src: "/studio/interior-blue.png",
    title: "Blue Interior",
    type: "Interior / Spatial Study",
    description:
      "Interior study using saturated blue surfaces, furniture placement and controlled lighting to shape a compact spatial composition.",
    alt: "Blue interior study with furniture and controlled architectural lighting.",
  },
  {
    src: "/studio/chairs.png",
    title: "Chair Series",
    type: "Furniture / Product Family",
    description:
      "A family of chairs developed around repeatable structural logic, colour variation and a consistent approach to assembly.",
    alt: "Series of chairs sharing a common structural language with colour variations.",
  },
  {
    src: "/studio/kempu.png",
    title: "Kempu",
    type: "Brand / Art Direction",
    description:
      "Brand direction study combining campaign imagery, typography and a controlled graphic system into a single visual language.",
    alt: "Kempu brand composition combining campaign imagery and typography.",
  },
  {
    src: "/studio/magnolias.png",
    title: "Magnolias",
    type: "Brand / Editorial Identity",
    description:
      "Identity and editorial composition combining typography with botanical artwork to create a flexible visual system.",
    alt: "Magnolias identity composition combining typography and botanical artwork.",
  },
];
