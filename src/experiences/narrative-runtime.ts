export type NarrativeScene = "hero" | "chapter" | "career" | "systems" | "gallery" | "agent";

export interface NarrativeState {
  physicalProgress: number;
  progress: number;
  node: number;
  scene: NarrativeScene;
}

type NarrativeListener = (state: NarrativeState) => void;

let state: NarrativeState = {
  physicalProgress: 0,
  progress: 0,
  node: 0,
  scene: "hero",
};

const listeners = new Set<NarrativeListener>();

export const narrativeRuntime = {
  getState(): NarrativeState {
    return state;
  },

  publish(next: NarrativeState): void {
    state = next;
    listeners.forEach((listener) => listener(state));
  },

  subscribe(listener: NarrativeListener, emitCurrent = true): () => void {
    listeners.add(listener);
    if (emitCurrent) listener(state);
    return () => listeners.delete(listener);
  },
};
