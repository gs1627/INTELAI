export const ACTIVE_SESSION_KEY: string;
export function loadActiveSession(storage: Storage): any;
export function saveActiveSession(storage: Storage, session: unknown): boolean;
export function clearActiveSession(storage: Storage): void;
export function elapsedSeconds(startedAt: number, now?: number): number;
