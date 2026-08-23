import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

// One GSAP runtime and one ScrollTrigger registration for the whole portfolio.
gsap.registerPlugin(ScrollTrigger);

export { gsap, ScrollTrigger };
