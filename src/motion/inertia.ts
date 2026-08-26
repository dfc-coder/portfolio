export const damp = (
  current: number,
  target: number,
  response: number,
  dt: number,
) => current + (target - current) * (1 - Math.exp(-response * dt));

export const frameDeltaSeconds = (time: number, previousTime: number) =>
  Math.min(0.05, Math.max(0.001, (time - previousTime) / 1000));
