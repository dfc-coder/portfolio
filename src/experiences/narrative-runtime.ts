export type NarrativeScene = "hero" | "chapter" | "career" | "systems" | "gallery" | "agent";

export interface NarrativeState {
  physicalProgress: number;
  progress: number;
  node: number;
  // Stable scene ownership also gates scene-local interaction listeners. A
  // handoff may keep adjacent runtimes mounted, but only this scene owns input.
  scene: NarrativeScene;
}

type NarrativeListener = (state: NarrativeState) => void;

const NARRATIVE_EPSILON = 0.0001;

let state: NarrativeState = {
  physicalProgress: 0,
  progress: 0,
  node: 0,
  scene: "hero",
};

const listeners = new Set<NarrativeListener>();

const nearlyEqual = (left: number, right: number) =>
  Math.abs(left - right) < NARRATIVE_EPSILON;

export const narrativeRuntime = {
  getState(): NarrativeState {
    return state;
  },

  publish(next: NarrativeState): void {
    if (
      next.scene === state.scene &&
      nearlyEqual(next.physicalProgress, state.physicalProgress) &&
      nearlyEqual(next.progress, state.progress)
    ) {
      return;
    }

    state = next;
    listeners.forEach((listener) => listener(state));
  },

  subscribe(listener: NarrativeListener, emitCurrent = true): () => void {
    listeners.add(listener);
    if (emitCurrent) listener(state);
    return () => listeners.delete(listener);
  },
};