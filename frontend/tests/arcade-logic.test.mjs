import test from 'node:test';
import assert from 'node:assert/strict';
import { addSequenceStep, arcadeTotal, logicOutput, memoryRoundScore, moveLane } from '../src/components/arcade/gameLogic.js';

test('memory sequence appends a deterministic tile within the 3x3 board', () => {
  assert.deepEqual(addSequenceStep([1, 4], () => 0.99), [1, 4, 8]);
  assert.deepEqual(addSequenceStep([], () => 0), [0]);
});

test('memory score rewards level and remaining time while applying miss penalties', () => {
  assert.equal(memoryRoundScore(3, 20, 0), 380);
  assert.equal(memoryRoundScore(1, 0, 8), 25);
});

test('spacecraft lane control stays inside three available lanes', () => {
  assert.equal(moveLane(1, -1), 0);
  assert.equal(moveLane(1, 1), 2);
  assert.equal(moveLane(0, -1), 0);
  assert.equal(moveLane(2, 1), 2);
});

test('logic puzzle evaluates each supported gate', () => {
  assert.equal(logicOutput('AND', true, false), false);
  assert.equal(logicOutput('OR', false, true), true);
  assert.equal(logicOutput('XOR', true, false), true);
  assert.equal(logicOutput('NOT', true), false);
});

test('arcade total sums browser records and ignores invalid entries', () => {
  assert.equal(arcadeTotal({ memory: 500, velocity: 140, invalid: NaN }), 640);
});
