export function addSequenceStep(sequence, random = Math.random) {
  return [...sequence, Math.floor(random() * 9)];
}

export function memoryRoundScore(level, secondsLeft, penalties = 0) {
  return Math.max(25, level * 100 + Math.max(0, secondsLeft) * 4 - penalties * 35);
}

export function moveLane(current, direction, laneCount = 3) {
  return Math.min(laneCount - 1, Math.max(0, current + direction));
}

export function logicOutput(gate, a, b = false) {
  if (gate === 'AND') return a && b;
  if (gate === 'OR') return a || b;
  if (gate === 'XOR') return a !== b;
  if (gate === 'NOT') return !a;
  return false;
}

export function arcadeTotal(scores) {
  return Object.values(scores).reduce((total, score) => total + (Number.isFinite(score) ? score : 0), 0);
}
