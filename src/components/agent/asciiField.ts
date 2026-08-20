/**
 * asciiField.ts — non-anthropomorphic ASCII fluid for AGENT OS (section 05).
 *
 * The field is a scalar density function sampled on a character grid and
 * rendered with Canvas 2D. It is NOT a particle system and NOT a face: the
 * shape is an aperture (a vertical elliptical shell) that breathes, warps
 * through a flow field, and is perturbed by impulses coming from the chat.
 *
 * Chat coupling — the whole point of the piece:
 *   setState()     idle | listening | thinking | speaking  → envelope targets
 *   pulse(x, y)    a message lands / a token streams       → travelling ripple
 *   setOccluders() message panels                          → glyphs are pushed
 *                                                            aside and dimmed
 *   setPointer()   cursor                                  → local displacement
 *
 * Canvas 2D on purpose: at 30fps and ~3k visible glyphs this stays under 4ms
 * per frame, and the scene already runs a three.js canvas underneath. A WebGL
 * port buys nothing here and costs the crisp text rasterisation.
 */

export type FieldState = 'idle' | 'listening' | 'thinking' | 'speaking'

export interface Occluder {
  /** normalised 0..1 rect, relative to the canvas box */
  x: number
  y: number
  w: number
  h: number
}

interface Ripple {
  x: number
  y: number
  born: number
  strength: number
  speed: number
}

interface Envelope {
  flow: number
  turbulence: number
  brightness: number
  aperture: number
  drift: number
  breath: number
}

const ENVELOPES: Record<FieldState, Envelope> = {
  //        flow  turb  bright  aperture  drift  breath
  idle: { flow: 0.16, turbulence: 0.34, brightness: 0.72, aperture: 1.0, drift: 0.0, breath: 0.34 },
  listening: { flow: 0.21, turbulence: 0.4, brightness: 0.84, aperture: 0.95, drift: 0.1, breath: 0.5 },
  thinking: { flow: 0.36, turbulence: 0.62, brightness: 1.0, aperture: 0.82, drift: -0.55, breath: 1.0 },
  speaking: { flow: 0.27, turbulence: 0.46, brightness: 0.96, aperture: 1.06, drift: 0.42, breath: 0.72 },
}

/** Density ramp. Letters in the upper half give the "data exhaust" texture. */
const RAMP = '.,:;-=+cxoXOA8R%#@'

/** Warm stops: bronze → gold → paper. Matches --ref-accent-ish portfolio palette. */
const BRONZE: [number, number, number] = [122, 100, 52]
const GOLD: [number, number, number] = [205, 182, 117]
const PAPER: [number, number, number] = [242, 237, 224]

const BUCKETS = 7
const TARGET_FPS = 30
const FRAME_MS = 1000 / TARGET_FPS

/* ---------------------------------------------------------------- noise --- */

const hash = (x: number, y: number): number => {
  const n = Math.sin(x * 127.1 + y * 311.7) * 43758.5453123
  return n - Math.floor(n)
}

const smooth = (t: number): number => t * t * (3 - 2 * t)

const valueNoise = (x: number, y: number): number => {
  const xi = Math.floor(x)
  const yi = Math.floor(y)
  const xf = smooth(x - xi)
  const yf = smooth(y - yi)
  const a = hash(xi, yi)
  const b = hash(xi + 1, yi)
  const c = hash(xi, yi + 1)
  const d = hash(xi + 1, yi + 1)
  return (a + (b - a) * xf) * (1 - yf) + (c + (d - c) * xf) * yf
}

const fbm = (x: number, y: number): number =>
  valueNoise(x, y) * 0.55 + valueNoise(x * 2.03, y * 2.03) * 0.29 + valueNoise(x * 4.11, y * 4.11) * 0.16

/* ----------------------------------------------------------------- util --- */

const clamp01 = (v: number): number => (v < 0 ? 0 : v > 1 ? 1 : v)

const approach = (current: number, target: number, rate: number, dt: number): number =>
  current + (target - current) * (1 - Math.exp(-rate * dt))

const mix = (a: number, b: number, t: number): number => a + (b - a) * t

const rampColor = (d: number): string => {
  const t = clamp01(d)
  let r: number
  let g: number
  let b: number
  if (t < 0.55) {
    const k = t / 0.55
    r = mix(BRONZE[0], GOLD[0], k)
    g = mix(BRONZE[1], GOLD[1], k)
    b = mix(BRONZE[2], GOLD[2], k)
  } else {
    const k = (t - 0.55) / 0.45
    r = mix(GOLD[0], PAPER[0], k)
    g = mix(GOLD[1], PAPER[1], k)
    b = mix(GOLD[2], PAPER[2], k)
  }
  return `${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}`
}

/* ---------------------------------------------------------------- field --- */

export class AsciiField {
  private readonly canvas: HTMLCanvasElement
  private readonly ctx: CanvasRenderingContext2D

  private state: FieldState = 'idle'
  private env: Envelope = { ...ENVELOPES.idle }

  private ripples: Ripple[] = []
  private occluders: Occluder[] = []

  private pointerX = -10
  private pointerY = -10
  private pointerEnergy = 0

  private raf = 0
  private running = false
  private paused = false
  private reduced = false

  private clock = 0
  private lastTs = 0
  private sinceDraw = 0

  private cssW = 0
  private cssH = 0
  private dpr = 1

  /** Pre-allocated draw buckets, reused every frame to avoid GC churn. */
  private readonly glyphs: string[][] = Array.from({ length: BUCKETS }, () => [])
  private readonly coords: number[][] = Array.from({ length: BUCKETS }, () => [])

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) throw new Error('AsciiField: 2D context unavailable')
    this.ctx = ctx
    this.reduced = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  }

  /* --------------------------------------------------------- lifecycle --- */

  start(): void {
    if (this.running) return
    this.running = true
    this.lastTs = performance.now()
    this.raf = requestAnimationFrame(this.loop)
  }

  stop(): void {
    this.running = false
    cancelAnimationFrame(this.raf)
  }

  /** Freeze without tearing down — used when section 05 is off-screen. */
  setPaused(paused: boolean): void {
    this.paused = paused
    if (!paused) this.lastTs = performance.now()
  }

  destroy(): void {
    this.stop()
    this.ripples.length = 0
    this.occluders.length = 0
  }

  /* ------------------------------------------------------------ inputs --- */

  setState(next: FieldState): void {
    this.state = next
  }

  /** Impulse at a normalised point. Strength ~0.3 for a token, ~1 for a message. */
  pulse(x: number, y: number, strength = 1): void {
    if (this.reduced) return
    if (this.ripples.length > 22) this.ripples.shift()
    this.ripples.push({
      x: (x - 0.5) * 2,
      y: (y - 0.5) * 2,
      born: this.clock,
      strength,
      speed: 0.55 + strength * 0.25,
    })
  }

  setOccluders(rects: Occluder[]): void {
    this.occluders = rects
  }

  setPointer(x: number, y: number, active: boolean): void {
    this.pointerX = (x - 0.5) * 2
    this.pointerY = (y - 0.5) * 2
    this.pointerEnergy = active ? 1 : 0
  }

  /* ------------------------------------------------------------- frame --- */

  private loop = (ts: number): void => {
    if (!this.running) return
    this.raf = requestAnimationFrame(this.loop)
    if (this.paused) {
      this.lastTs = ts
      return
    }

    const dt = Math.min(0.05, (ts - this.lastTs) / 1000)
    this.lastTs = ts

    // Fixed-rate redraw: the quantised refresh reads as a terminal, not as lag.
    this.sinceDraw += dt * 1000
    this.clock += this.reduced ? 0 : dt
    this.integrate(dt)
    if (this.sinceDraw < FRAME_MS) return
    this.sinceDraw = 0
    this.draw()
  }

  private integrate(dt: number): void {
    const target = ENVELOPES[this.state]
    this.env.flow = approach(this.env.flow, target.flow, 3.2, dt)
    this.env.turbulence = approach(this.env.turbulence, target.turbulence, 3.2, dt)
    this.env.brightness = approach(this.env.brightness, target.brightness, 4.5, dt)
    this.env.aperture = approach(this.env.aperture, target.aperture, 2.6, dt)
    this.env.drift = approach(this.env.drift, target.drift, 3.0, dt)
    this.env.breath = approach(this.env.breath, target.breath, 2.4, dt)

    if (this.ripples.length) {
      const now = this.clock
      this.ripples = this.ripples.filter((r) => now - r.born < 2.8)
    }
  }

  private resize(): boolean {
    const rect = this.canvas.getBoundingClientRect()
    if (rect.width < 2 || rect.height < 2) return false
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    const w = Math.round(rect.width * dpr)
    const h = Math.round(rect.height * dpr)
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w
      this.canvas.height = h
    }
    this.cssW = rect.width
    this.cssH = rect.height
    this.dpr = dpr
    return true
  }

  private draw(): void {
    if (!this.resize()) return

    const { ctx } = this
    const w = this.cssW
    const h = this.cssH
    const t = this.clock

    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    ctx.clearRect(0, 0, w, h)

    // Cell size drives glyph size. ~11px columns keeps the mockup's density.
    const cell = w < 640 ? 9.5 : w < 1024 ? 10.5 : 11.5
    const cols = Math.max(28, Math.floor(w / cell))
    const rows = Math.max(18, Math.floor(h / (cell * 1.24)))
    const stepX = w / cols
    const stepY = h / rows
    const aspect = w / h

    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.font = `${Math.max(7, stepY * 0.82)}px "DM Mono", ui-monospace, SFMono-Regular, Menlo, monospace`

    for (let i = 0; i < BUCKETS; i += 1) {
      this.glyphs[i].length = 0
      this.coords[i].length = 0
    }

    const env = this.env
    const breathe = Math.sin(t * 0.62) * 0.035 + Math.sin(t * 0.23 + 1.7) * 0.022
    const apertureR = env.aperture * (1 + breathe * env.breath)
    const flowT = t * 0.11

    for (let row = 0; row < rows; row += 1) {
      const ny = (row + 0.5) / rows
      const py = (ny - 0.5) * 2

      for (let col = 0; col < cols; col += 1) {
        const nx = (col + 0.5) / cols
        const px = (nx - 0.5) * 2 * aspect

        // --- flow advection: sample the shape at a warped position ---------
        const fx = (fbm(px * 1.35 + flowT, py * 1.35) - 0.5) * env.flow * 2
        const fy = (fbm(px * 1.35 + 7.3, py * 1.35 - flowT) - 0.5) * env.flow * 2
        const sx = px + fx
        const sy = py + fy

        // --- aperture ------------------------------------------------------
        // A vertical elliptical shell with a carved core, then warped by
        // angular noise so the outline never settles into a symmetric ring.
        // Symmetry is what makes an aperture read as an iris; this breaks it.
        const ex = sx / (0.42 * apertureR)
        const ey = (sy + 0.05) / (0.66 * apertureR)
        let r = Math.sqrt(ex * ex + ey * ey)

        const angle = Math.atan2(ey, ex)
        r += (fbm(Math.cos(angle) * 1.45 + t * 0.09, Math.sin(angle) * 1.45) - 0.5) * 0.62

        const shell = Math.exp(-Math.pow((r - 1.08) * 2.7, 2))
        const cloud = Math.exp(-Math.pow((r - 1.55) * 1.2, 2)) * 0.46
        const core = -Math.exp(-Math.pow(r * 1.5, 2)) * 1.35
        const body = (shell + cloud + core) * 0.86

        // Turbulence is masked by the body so no glyphs stray into the black.
        const dust = (fbm(sx * 2.8 - flowT * 1.4, sy * 2.8 + flowT) - 0.44) * env.turbulence

        let density =
          body + dust * clamp01(body * 2.4) - Math.max(0, r - 2) * 0.85 - Math.max(0, py) * 0.2

        // --- chat impulses --------------------------------------------------
        let dx = 0
        let dy = 0
        for (let k = 0; k < this.ripples.length; k += 1) {
          const rip = this.ripples[k]
          const age = t - rip.born
          const ddx = px - rip.x * aspect
          const ddy = py - rip.y
          const dist = Math.sqrt(ddx * ddx + ddy * ddy)
          const front = age * rip.speed
          if (dist > front + 0.55 || dist < front - 0.55) continue
          const decay = Math.exp(-age * 1.5) * Math.exp(-dist * 0.9)
          const wave = Math.sin((dist - front) * 11) * decay * rip.strength
          density += wave * 0.55
          if (dist > 0.001) {
            dx += (ddx / dist) * wave * 0.16
            dy += (ddy / dist) * wave * 0.16
          }
        }

        // --- state drift: inward while thinking, outward while speaking ----
        if (r > 0.001) {
          const dirX = ex / r
          const dirY = ey / r
          dx += dirX * env.drift * 0.035
          dy += dirY * env.drift * 0.035
        }

        // --- pointer --------------------------------------------------------
        if (this.pointerEnergy > 0) {
          const ddx = px - this.pointerX * aspect
          const ddy = py - this.pointerY
          const dist2 = ddx * ddx + ddy * ddy
          const infl = Math.exp(-dist2 * 9) * this.pointerEnergy
          density += infl * 0.28
          dx += ddx * infl * 0.5
          dy += ddy * infl * 0.5
        }

        if (density < 0.09) continue

        // Stable dither: coverage is proportional to density, but the
        // threshold is fixed per cell, so glyphs fade in and out instead of
        // strobing. This is what gives the scattered, granular texture.
        if (hash(col * 0.37, row * 0.71) > clamp01(density) * 1.05) continue

        let x = nx * w + dx * stepX * 9
        let y = ny * h + dy * stepY * 9
        let alphaScale = 1

        // --- message panels physically part the field -----------------------
        if (this.occluders.length) {
          let skip = false
          for (let k = 0; k < this.occluders.length; k += 1) {
            const o = this.occluders[k]
            const m = 0.018
            const cxN = x / w
            const cyN = y / h
            const insideX = cxN > o.x - m && cxN < o.x + o.w + m
            const insideY = cyN > o.y - m && cyN < o.y + o.h + m
            if (!insideX || !insideY) continue
            if (cxN > o.x && cxN < o.x + o.w && cyN > o.y && cyN < o.y + o.h) {
              skip = true
              break
            }
            // in the feather band: push outward from the panel, dim
            const ocx = o.x + o.w / 2
            const ocy = o.y + o.h / 2
            const nxo = cxN - ocx
            const nyo = cyN - ocy
            const len = Math.hypot(nxo, nyo) || 1
            x += (nxo / len) * stepX * 1.6
            y += (nyo / len) * stepY * 1.6
            alphaScale = Math.min(alphaScale, 0.42)
          }
          if (skip) continue
        }

        const d = clamp01(density)
        const glyph = RAMP[Math.min(RAMP.length - 1, Math.floor(d * RAMP.length))]
        const bucket = Math.min(BUCKETS - 1, Math.floor(d * BUCKETS))

        this.glyphs[bucket].push(glyph)
        this.coords[bucket].push(x, y)
        if (alphaScale < 1) {
          // encode the dim by demoting one bucket instead of a per-glyph fill
          const demoted = Math.max(0, bucket - 3)
          if (demoted !== bucket) {
            this.glyphs[bucket].pop()
            this.coords[bucket].pop()
            this.coords[bucket].pop()
            this.glyphs[demoted].push(glyph)
            this.coords[demoted].push(x, y)
          }
        }
      }
    }

    // --- batched paint: one fillStyle per bucket, not per glyph ------------
    for (let b = 0; b < BUCKETS; b += 1) {
      const list = this.glyphs[b]
      if (!list.length) continue
      const d = (b + 0.5) / BUCKETS
      const alpha = Math.min(0.96, (0.1 + d * 0.9) * env.brightness)
      ctx.fillStyle = `rgba(${rampColor(d)}, ${alpha.toFixed(3)})`
      const pts = this.coords[b]
      for (let i = 0; i < list.length; i += 1) {
        ctx.fillText(list[i], pts[i * 2], pts[i * 2 + 1])
      }
    }
  }
}
