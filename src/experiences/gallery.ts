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
    src: "/studio/interior-shadow.png",
    title: "Shadow Interior",
    type: "Interior / Spatial Study",
    description:
      "Interior composition centred on contrast, shadow and surface texture to create depth with a restrained material palette.",
    alt: "Interior composition defined by strong shadows, texture and a restrained material palette.",
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

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

type CardMetric = {
  centerX: number;
  centerY: number;
  depth: number;
};

export const mountGalleryGel = () => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return () => undefined;

  const stage = document.querySelector<HTMLElement>(".ref-stage");
  const gallery = document.querySelector<HTMLElement>(".ref-scene--gallery");
  const galleryStage = gallery?.querySelector<HTMLElement>(".ref-gallery-stage");
  const cards = galleryStage
    ? Array.from(galleryStage.querySelectorAll<HTMLElement>(".ref-art-card"))
    : [];

  if (!stage || !gallery || !galleryStage || cards.length === 0) {
    return () => undefined;
  }

  gallery.classList.add("ref-gallery-gel-ready");

  cards.forEach((card, index) => {
    card.dataset.gelIndex = String(index);
    const label = document.createElement("span");
    label.className = "ref-art-card__label";
    label.textContent = galleryItems[index]?.title ?? `Artwork ${index + 1}`;
    card.append(label);
  });

  const focus = document.createElement("div");
  focus.className = "ref-gallery-focus";
  focus.setAttribute("role", "dialog");
  focus.setAttribute("aria-modal", "true");
  focus.setAttribute("aria-hidden", "true");
  focus.innerHTML = `
    <button class="ref-gallery-focus__close" type="button" aria-label="Close artwork">CLOSE</button>
    <figure class="ref-gallery-focus__figure">
      <div class="ref-gallery-focus__image-wrap"><img class="ref-gallery-focus__image" alt="" decoding="async" /></div>
      <figcaption class="ref-gallery-focus__caption">
        <div class="ref-gallery-focus__signal"><span></span><i></i><span class="ref-gallery-focus__signal-label">VISUAL ARCHIVE</span></div>
        <h3></h3>
        <p class="ref-gallery-focus__type"></p>
        <p class="ref-gallery-focus__meta"></p>
      </figcaption>
    </figure>
  `;
  gallery.append(focus);

  const focusImage = focus.querySelector<HTMLImageElement>(".ref-gallery-focus__image");
  const focusTitle = focus.querySelector<HTMLElement>(".ref-gallery-focus__caption h3");
  const focusType = focus.querySelector<HTMLElement>(".ref-gallery-focus__type");
  const focusDescription = focus.querySelector<HTMLElement>(".ref-gallery-focus__meta");
  const focusIndex = focus.querySelector<HTMLElement>(".ref-gallery-focus__signal span");
  const closeButton = focus.querySelector<HTMLButtonElement>(".ref-gallery-focus__close");

  let selectedIndex = 0;
  let isOpen = false;
  let pointerFrame = 0;
  let pointerX = innerWidth * 0.5;
  let pointerY = innerHeight * 0.5;
  let cardMetrics: CardMetric[] = [];

  const galleryIsVisible = () => stage.dataset.scene === "gallery";

  const setSelected = (index: number) => {
    selectedIndex = (index + cards.length) % cards.length;
    cards.forEach((card, cardIndex) => {
      card.classList.toggle("is-key-active", cardIndex === selectedIndex);
    });
  };

  const renderFocus = () => {
    const item = galleryItems[selectedIndex];
    if (
      !item ||
      !focusImage ||
      !focusTitle ||
      !focusType ||
      !focusDescription ||
      !focusIndex
    ) return;

    focusImage.src = galleryImageUrl(item.src, 1600, 82);
    focusImage.srcset = galleryImageSrcSet(item.src, [960, 1280, 1600, 2048], 82);
    focusImage.sizes = "(max-width: 980px) 90vw, 72vw";
    focusImage.alt = item.alt;
    focusTitle.textContent = item.title;
    focusType.textContent = item.type;
    focusDescription.textContent = item.description;
    focusIndex.textContent = String(selectedIndex + 1).padStart(2, "0");
  };

  const openFocus = (index: number) => {
    if (!galleryIsVisible()) return;

    setSelected(index);
    renderFocus();
    isOpen = true;
    gallery.classList.add("is-gallery-focus-open");
    focus.classList.add("is-open");
    focus.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => closeButton?.focus({ preventScroll: true }));
  };

  const closeFocus = () => {
    if (!isOpen) return;
    isOpen = false;
    gallery.classList.remove("is-gallery-focus-open");
    focus.classList.remove("is-open");
    focus.setAttribute("aria-hidden", "true");
    if (galleryIsVisible()) cards[selectedIndex]?.focus({ preventScroll: true });
  };

  const onGalleryClick = (event: MouseEvent) => {
    if (!galleryIsVisible() && !isOpen) return;

    const target = event.target as Element | null;
    const card = target?.closest<HTMLElement>(".ref-art-card");
    if (card) {
      event.preventDefault();
      openFocus(Number(card.dataset.gelIndex ?? 0));
      return;
    }

    if (target === focus || target?.closest(".ref-gallery-focus__close")) {
      event.preventDefault();
      closeFocus();
    }
  };

  const onKeydown = (event: KeyboardEvent) => {
    if (!galleryIsVisible() && !isOpen) return;

    if (event.key === "Escape" && isOpen) {
      event.preventDefault();
      closeFocus();
      return;
    }

    if (!["ArrowRight", "ArrowLeft", "Home", "End", "Enter", " "].includes(event.key)) return;

    event.preventDefault();
    if (event.key === "ArrowRight") setSelected(selectedIndex + 1);
    if (event.key === "ArrowLeft") setSelected(selectedIndex - 1);
    if (event.key === "Home") setSelected(0);
    if (event.key === "End") setSelected(cards.length - 1);
    if (event.key === "Enter" || event.key === " ") openFocus(selectedIndex);
    if (isOpen) renderFocus();
  };

  const measureCards = () => {
    const stageRect = galleryStage.getBoundingClientRect();
    cardMetrics = cards.map((card, index) => ({
      centerX: stageRect.left + card.offsetLeft + card.offsetWidth * 0.5,
      centerY: stageRect.top + card.offsetTop + card.offsetHeight * 0.5,
      depth: 0.72 + (index % 5) * 0.11,
    }));
  };

  const renderPointerField = () => {
    pointerFrame = 0;
    if (!galleryIsVisible() || isOpen) return;
    if (cardMetrics.length !== cards.length) measureCards();

    cards.forEach((card, index) => {
      const metric = cardMetrics[index];
      if (!metric) return;

      const dx = pointerX - metric.centerX;
      const dy = pointerY - metric.centerY;
      const influence = clamp(1 - Math.hypot(dx, dy) / 620, 0, 1);
      card.style.setProperty("--gel-x", `${(dx * 0.018 * metric.depth * influence).toFixed(2)}px`);
      card.style.setProperty("--gel-y", `${(dy * 0.014 * metric.depth * influence).toFixed(2)}px`);
      card.style.setProperty("--gel-rx", `${(-dy * 0.006 * influence).toFixed(2)}deg`);
      card.style.setProperty("--gel-ry", `${(dx * 0.006 * influence).toFixed(2)}deg`);
    });
  };

  const schedulePointerField = () => {
    if (pointerFrame !== 0) return;
    pointerFrame = requestAnimationFrame(renderPointerField);
  };

  const onPointerMove = (event: PointerEvent) => {
    if (!galleryIsVisible() || isOpen) return;
    pointerX = event.clientX;
    pointerY = event.clientY;
    schedulePointerField();
  };

  const onResize = () => {
    cardMetrics = [];
    if (galleryIsVisible() && !isOpen) schedulePointerField();
  };

  const onFocusPointerDown = (event: PointerEvent) => {
    if (event.target === focus) closeFocus();
  };

  gallery.addEventListener("click", onGalleryClick, true);
  focus.addEventListener("pointerdown", onFocusPointerDown);
  addEventListener("keydown", onKeydown, true);
  addEventListener("pointermove", onPointerMove, { passive: true });
  addEventListener("resize", onResize, { passive: true });

  return () => {
    if (pointerFrame !== 0) cancelAnimationFrame(pointerFrame);
    gallery.removeEventListener("click", onGalleryClick, true);
    focus.removeEventListener("pointerdown", onFocusPointerDown);
    removeEventListener("keydown", onKeydown, true);
    removeEventListener("pointermove", onPointerMove);
    removeEventListener("resize", onResize);
    focus.remove();
    gallery.classList.remove("ref-gallery-gel-ready", "is-gallery-focus-open");
    cards.forEach((card) => {
      card.classList.remove("is-key-active");
      card.querySelector(".ref-art-card__label")?.remove();
      ["--gel-x", "--gel-y", "--gel-rx", "--gel-ry"].forEach((name) =>
        card.style.removeProperty(name),
      );
    });
  };
};
