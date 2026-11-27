import { useEffect, useRef, useState } from 'react';
import { addSequenceStep, memoryRoundScore } from '../gameLogic.js';
import { GameChrome, useArcadeSession } from '../GameShell';

export default function NeuralMemoryRush({ onExit }: { onExit: () => void }) {
  const session = useArcadeSession('neural-memory-rush', 60);
  const [sequence, setSequence] = useState([0, 4, 8]);
  const [step, setStep] = useState(0);
  const [level, setLevel] = useState(1);
  const [mistakes, setMistakes] = useState(0);
  const [activeTile, setActiveTile] = useState<number | null>(null);
  const [locked, setLocked] = useState(true);
  const [replay, setReplay] = useState(0);
  const timeoutIds = useRef<number[]>([]);

  useEffect(() => {
    if (session.status === 'countdown') {
      setSequence([0, 4, 8]);
      setLevel(1);
      setMistakes(0);
      setReplay(value => value + 1);
    }
  }, [session.status]);

  useEffect(() => {
    if (session.status !== 'playing') return;
    timeoutIds.current.forEach(window.clearTimeout);
    timeoutIds.current = [];
    setLocked(true);
    setStep(0);
    const speed = Math.max(220, 540 - level * 26);
    sequence.forEach((tile, index) => {
      const on = window.setTimeout(() => setActiveTile(tile), 500 + index * (speed + 130));
      const off = window.setTimeout(() => setActiveTile(null), 500 + index * (speed + 130) + speed);
      timeoutIds.current.push(on, off);
    });
    const unlock = window.setTimeout(() => setLocked(false), 560 + sequence.length * (speed + 130));
    timeoutIds.current.push(unlock);
    return () => { timeoutIds.current.forEach(window.clearTimeout); timeoutIds.current = []; };
  }, [session.status, sequence, level, replay]);

  const choose = (tile: number) => {
    if (session.status !== 'playing' || locked) return;
    setActiveTile(tile);
    window.setTimeout(() => setActiveTile(null), 120);
    if (sequence[step] !== tile) {
      const misses = mistakes + 1;
      setMistakes(misses);
      setStep(0);
      if (misses >= 3) session.complete(session.score);
      else { setLocked(true); setReplay(current => current + 1); }
      return;
    }
    if (step + 1 === sequence.length) {
      session.setScore(current => current + memoryRoundScore(level, session.timeLeft, mistakes));
      setLevel(current => current + 1);
      setSequence(current => addSequenceStep(current));
      setLocked(true);
    } else setStep(current => current + 1);
  };

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key >= '1' && event.key <= '9') choose(Number(event.key) - 1);
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  });

  return <GameChrome title="Neural Memory Rush" subtitle="Read the signal. Replay the pattern. Build a longer chain." instructions={["Watch the nine-node sequence, then repeat it.", "Each clear round adds one step and speeds up the signal.", "Three misses or the 60-second clock ends the run."]} session={session} onExit={onExit}>
    <div className="memory-board-wrap"><div className="memory-status"><span>SEQUENCE {level.toString().padStart(2, '0')}</span><b>{locked ? 'OBSERVE THE SIGNAL' : 'REPEAT THE PATTERN'}</b><span>MISSES {mistakes}/3</span></div><div className="memory-board">{Array.from({ length: 9 }, (_, tile) => <button aria-label={`Memory tile ${tile + 1}`} key={tile} className={`memory-tile memory-tile-${tile} ${activeTile === tile ? 'lit' : ''}`} onClick={() => choose(tile)}><i/><span>{String(tile + 1).padStart(2, '0')}</span></button>)}</div><div className="memory-progress"><i style={{ width: `${Math.min(100, (step / sequence.length) * 100)}%` }}/></div><small>KEYBOARD / 1–9 KEYS · TOUCH / CLICK TILES</small></div>
  </GameChrome>;
}
