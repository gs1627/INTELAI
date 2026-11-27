export function addSequenceStep(sequence: number[], random?: () => number): number[];
export function memoryRoundScore(level: number, secondsLeft: number, penalties?: number): number;
export function moveLane(current: number, direction: number, laneCount?: number): number;
export function logicOutput(gate: 'AND' | 'OR' | 'XOR' | 'NOT', a: boolean, b?: boolean): boolean;
export function arcadeTotal(scores: Record<string, number>): number;
