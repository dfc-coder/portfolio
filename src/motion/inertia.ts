export type SpringState = {
  value: number;
  velocity: number;
};

export type SpringConfig = {
  frequency: number;
  damping: number;
  maxVelocity?: number;
};

const PARALLAX_TIME_SCALE = 0.72;
const PARALLAX_VELOCITY_SCALE = 0.78;

export const damp = (
  current: number,
  target: number,
  response: number,
  dt: number,
) => current + (target - current) * (1 - Math.exp(-response * dt));

export const springStep = (
  state: SpringState,
  target: number,
  config: SpringConfig,
  dt: number,
): SpringState => {
  // Run the scroll-linked springs deliberately slower than physical time.
  // The lower natural frequency preserves the small overshoot while giving
  // foreground/background layers enough time to separate perceptually.
  const omega =
    Math.max(0.01, config.frequency) * Math.PI * 2 * PARALLAX_TIME_SCALE;
  const damping = Math.max(0.05, config.damping);
  const steps = Math.max(1, Math.ceil(dt / 0.008));
  const h = dt / steps;
  const maxVelocity =
    (config.maxVelocity ?? Number.POSITIVE_INFINITY) * PARALLAX_VELOCITY_SCALE;

  let value = state.value;
  let velocity = state.velocity;

  for (let index = 0; index < steps; index += 1) {
    const acceleration =
      (target - value) * omega * omega -
      2 * damping * omega * velocity;

    velocity += acceleration * h;
    velocity = Math.min(maxVelocity, Math.max(-maxVelocity, velocity));
    value += velocity * h;
  }

  return { value, velocity };
};

export const frameDeltaSeconds = (time: number, previousTime: number) =>
  Math.min(0.05, Math.max(0.001, (time - previousTime) / 1000));
