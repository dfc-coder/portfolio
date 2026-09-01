export type AgentVisualPhase = "idle" | "listening" | "thinking" | "speaking" | "error";

export type AgentVisualTone = "calm" | "curious" | "focused" | "confident" | "uncertain";

export type AgentVisualSignals = {
  phase: AgentVisualPhase;
  tone: AgentVisualTone;
  mode: number;
  toneMode: number;
  time: number;
  activity: number;
  speech: number;
  interaction: number;
  thinkingBlend: number;
  pointerX: number;
  pointerY: number;
  pointerForce: number;
  pointerVelocity: number;
};

type ControllerState = AgentVisualSignals & {
  activityTarget: number;
  speechTarget: number;
  interactionTarget: number;
  pointerForceTarget: number;
  pointerVelocityTarget: number;
};

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const damp = (current: number, target: number, response: number, dt: number) =>
  current + (target - current) * (1 - Math.exp(-response * dt));

const phaseMode = (phase: AgentVisualPhase): number => {
  if (phase === "listening") return 1;
  if (phase === "thinking") return 2;
  if (phase === "speaking") return 3;
  if (phase === "error") return 4;
  return 0;
};

const phaseTone = (phase: AgentVisualPhase): AgentVisualTone => {
  if (phase === "listening") return "curious";
  if (phase === "thinking") return "focused";
  if (phase === "speaking") return "confident";
  if (phase === "error") return "uncertain";
  return "calm";
};

const toneMode = (tone: AgentVisualTone): number => {
  if (tone === "curious") return 1;
  if (tone === "focused") return 2;
  if (tone === "confident") return 3;
  if (tone === "uncertain") return 4;
  return 0;
};

const baseActivity = (phase: AgentVisualPhase): number => {
  if (phase === "listening") return 0.18;
  if (phase === "thinking") return 0.34;
  if (phase === "speaking") return 0.18;
  if (phase === "error") return 0.38;
  return 0.10;
};

const lifeRate = (phase: AgentVisualPhase): number => {
  if (phase === "thinking") return 0.72;
  if (phase === "speaking") return 0.46;
  if (phase === "listening") return 0.38;
  if (phase === "error") return 0.55;
  return 0.30;
};

const state: ControllerState = {
  phase: "idle",
  tone: "calm",
  mode: 0,
  toneMode: 0,
  time: 0,
  activity: 0.10,
  speech: 0,
  interaction: 0,
  thinkingBlend: 0,
  pointerX: 0,
  pointerY: 0,
  pointerForce: 0,
  pointerVelocity: 0,
  activityTarget: 0.10,
  speechTarget: 0,
  interactionTarget: 0,
  pointerForceTarget: 0,
  pointerVelocityTarget: 0,
};

export const setAgentVisualPhase = (phase: AgentVisualPhase): void => {
  state.phase = phase;
  state.tone = phaseTone(phase);
  if (phase !== "speaking") state.speechTarget = 0;
};

export const pulseAgentVisual = (strength = 0.3): void => {
  state.activityTarget = Math.max(state.activityTarget, clamp01(strength));
};

export const pulseAgentSpeech = (strength = 0.6): void => {
  state.speechTarget = Math.max(state.speechTarget, clamp01(strength));
};

export const pulseAgentInteraction = (strength = 0.75): void => {
  state.interactionTarget = Math.max(state.interactionTarget, clamp01(strength));
};

export const setAgentPointer = (
  x: number,
  y: number,
  velocity: number,
  force: number,
): void => {
  state.pointerX = Math.max(-1, Math.min(1, x));
  state.pointerY = Math.max(-1, Math.min(1, y));
  state.pointerVelocityTarget = Math.max(state.pointerVelocityTarget, clamp01(velocity));
  state.pointerForceTarget = clamp01(force);
};

export const updateAgentVisual = (dt: number): AgentVisualSignals => {
  const base = baseActivity(state.phase);
  const excess = Math.max(0, state.activityTarget - base);
  state.activityTarget = base + excess * Math.exp(-6.8 * dt);
  state.activity = damp(state.activity, state.activityTarget, 8.0, dt);

  state.speechTarget *= Math.exp(-6.0 * dt);
  const speechResponse = state.speechTarget > state.speech ? 22.0 : 6.2;
  state.speech = damp(state.speech, state.speechTarget, speechResponse, dt);
  if (state.phase !== "speaking") state.speech *= Math.exp(-12.0 * dt);

  state.interactionTarget *= Math.exp(-7.8 * dt);
  const interactionResponse = state.interactionTarget > state.interaction ? 18.0 : 6.0;
  state.interaction = damp(state.interaction, state.interactionTarget, interactionResponse, dt);

  state.pointerForce = damp(state.pointerForce, state.pointerForceTarget, 8.0, dt);
  state.pointerVelocity = damp(state.pointerVelocity, state.pointerVelocityTarget, 12.0, dt);
  state.pointerVelocityTarget *= Math.exp(-8.0 * dt);

  state.mode = damp(state.mode, phaseMode(state.phase), 5.0, dt);
  state.toneMode = damp(state.toneMode, toneMode(state.tone), 2.4, dt);
  state.thinkingBlend = damp(state.thinkingBlend, state.phase === "thinking" ? 1 : 0, 4.8, dt);
  state.time += dt * lifeRate(state.phase);

  return {
    phase: state.phase,
    tone: state.tone,
    mode: state.mode,
    toneMode: state.toneMode,
    time: state.time,
    activity: state.activity,
    speech: state.speech,
    interaction: state.interaction,
    thinkingBlend: state.thinkingBlend,
    pointerX: state.pointerX,
    pointerY: state.pointerY,
    pointerForce: state.pointerForce,
    pointerVelocity: state.pointerVelocity,
  };
};
