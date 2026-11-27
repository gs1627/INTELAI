export const ACTIVE_SESSION_KEY = 'arena.active-session';

export function loadActiveSession(storage) {
  try {
    const raw = storage.getItem(ACTIVE_SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveActiveSession(storage, session) {
  try {
    storage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(session));
    return true;
  } catch {
    return false;
  }
}

export function clearActiveSession(storage) {
  try {
    storage.removeItem(ACTIVE_SESSION_KEY);
  } catch {
    // Storage may be disabled by browser policy.
  }
}

export function elapsedSeconds(startedAt, now = Date.now()) {
  return startedAt > 0 ? Math.floor(Math.max(0, now - startedAt) / 1000) : 0;
}
