export const galleryItems = [
  {
    src: "/studio/bench-detail.png",
    title: "Quiet Joinery",
    type: "Furniture system",
    meta: "Oak · leather · structural detail",
  },
  {
    src: "/studio/mortar.png",
    title: "Domestic Ritual",
    type: "Object design",
    meta: "Stone · timber · material contrast",
  },
  {
    src: "/studio/radios.png",
    title: "Portable Frequency",
    type: "Product language",
    meta: "CMF · retro-futurism · series",
  },
  {
    src: "/studio/bench.png",
    title: "Linear Rest",
    type: "Furniture design",
    meta: "Structure · proportion · restraint",
  },
  {
    src: "/studio/lounge-mint.png",
    title: "Soft Landscape",
    type: "Seating concept",
    meta: "Textile · tubular steel · comfort",
  },
  {
    src: "/studio/interior-shadow.png",
    title: "Shadow Room",
    type: "Spatial direction",
    meta: "Light · texture · atmosphere",
  },
  {
    src: "/studio/interior-blue.png",
    title: "Blue Alcove",
    type: "Interior visualisation",
    meta: "Materiality · composition · mood",
  },
  {
    src: "/studio/chairs.png",
    title: "Primary Structure",
    type: "Furniture family",
    meta: "Modularity · colour · assembly",
  },
  {
    src: "/studio/kempu.png",
    title: "Kempu",
    type: "Art direction",
    meta: "Campaign · typography · image",
  },
  {
    src: "/studio/magnolias.png",
    title: "Magnolias",
    type: "Visual identity",
    meta: "Editorial · type system · artwork",
  },
] as const;

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
      <div class="ref-gallery-focus__image-wrap"><img class="ref-gallery-focus__image" alt="" /></div>
      <figcaption class="ref-gallery-focus__caption">
        <div class="ref-gallery-focus__signal"><span></span><i></i><b>VISUAL ARCHIVE</b></div>
        <h2></h2>
        <p class="ref-gallery-focus__type"></p>
        <p class="ref-gallery-focus__meta"></p>
      </figcaption>
    </figure>
  `;
  gallery.append(focus);

  const focusImage = focus.querySelector<HTMLImageElement>(".ref-gallery-focus__image");
  const focusTitle = focus.querySelector<HTMLElement>(".ref-gallery-focus__caption h2");
  const focusType = focus.querySelector<HTMLElement>(".ref-gallery-focus__type");
  const focusMeta = focus.querySelector<HTMLElement>(".ref-gallery-focus__meta");
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
    if (!item || !focusImage || !focusTitle || !focusType || !focusMeta || !focusIndex) return;

    focusImage.src = item.src;
    focusImage.alt = item.title;
    focusTitle.textContent = item.title;
    focusType.textContent = item.type;
    focusMeta.textContent = item.meta;
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
