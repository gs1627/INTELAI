import test from 'node:test';
import assert from 'node:assert/strict';
import { ACTIVE_SESSION_KEY, clearActiveSession, elapsedSeconds, loadActiveSession, saveActiveSession } from '../src/sessionPersistence.js';

function memoryStorage() {
  const values = new Map();
  return {
    getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  };
}

test('session choices and timer anchor survive a simulated refresh', () => {
  const storage = memoryStorage();
  const session = { sessionId: 'session-123', stage: 'build', startedAt: 1_000_000, elapsed: 34, priority: 'Battery life' };
  assert.equal(saveActiveSession(storage, session), true);
  const restored = loadActiveSession(storage);
  assert.deepEqual(restored, session);
  assert.equal(elapsedSeconds(restored.startedAt, 1_012_000), 12);
  // Navigation and reload use the original startedAt anchor, so elapsed time does not restart.
  assert.equal(elapsedSeconds(restored.startedAt, 1_046_000), 46);
});

test('session storage failures are safely ignored and reset clears active state', () => {
  const storage = memoryStorage();
  saveActiveSession(storage, { stage: 'pick' });
  assert.equal(loadActiveSession(storage).stage, 'pick');
  clearActiveSession(storage);
  assert.equal(loadActiveSession(storage), null);
  assert.equal(saveActiveSession({ setItem() { throw new Error('quota'); } }, {}), false);
  assert.equal(loadActiveSession({ getItem() { throw new Error('blocked'); } }), null);
  assert.equal(ACTIVE_SESSION_KEY, 'arena.active-session');
});
