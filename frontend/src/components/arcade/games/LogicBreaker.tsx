import { useEffect, useState } from 'react';
import { logicOutput } from '../gameLogic.js';
import { GameChrome, useArcadeSession } from '../GameShell';

const circuits = [
  { a: true, b: true, gate: 'AND' as const, result: true },
  { a: true, b: false, gate: 'XOR' as const, result: true },
  { a: false, b: true, gate: 'OR' as const, result: true },
  { a: true, b: false, gate: 'NOT' as const, result: false },
  { a: false, b: false, gate: 'XOR' as const, result: false },
  { a: true, b: true, gate: 'OR' as const, result: true },
];

export default function LogicBreaker({ onExit }: { onExit: () => void }) {
  const session = useArcadeSession('logic-breaker', 90);
  const [level, setLevel] = useState(0);
  const [selected, setSelected] = useState('');
  const [message, setMessage] = useState('Choose the gate that creates the target output.');
  const [hintUsed, setHintUsed] = useState(false);
  useEffect(() => {
    if (session.status === 'countdown') { setLevel(0); setSelected(''); setHintUsed(false); setMessage('Choose the gate that creates the target output.'); }
  }, [session.status]);
  const puzzle = circuits[level];
  const selectGate = (gate: string) => {
    if (!puzzle || selected) return;
    setSelected(gate);
    const output = logicOutput(gate as typeof puzzle.gate, puzzle.a, puzzle.b);
    if (output === puzzle.result) {
      const points = Math.max(60, 180 - session.timeLeft + (hintUsed ? -60 : 0));
      session.setScore(score => score + points);
      setMessage(`PATH VERIFIED · +${points} points`);
      window.setTimeout(() => {
        if (level + 1 >= circuits.length) session.complete(session.score + points);
        else { setLevel(current => current + 1); setSelected(''); setHintUsed(false); setMessage('Next circuit loaded.'); }
      }, 650);
    } else {
      session.setScore(score => Math.max(0, score - 25));
      setMessage(`That path returns ${Number(output)}. Re-route the circuit.`);
      window.setTimeout(() => setSelected(''), 650);
    }
  };
  const useHint = () => {
    setHintUsed(true);
    setSessionPenalty();
    setMessage(puzzle?.gate === 'NOT' ? 'Hint: invert A without using input B.' : 'Hint: trace the only path that produces the illuminated output.');
  };
  function setSessionPenalty() { session.setScore(score => Math.max(0, score - 50)); }

  return <GameChrome title="Logic Breaker" subtitle="Route a clean signal through the right gate." instructions={["Read the binary input values and target output.", "Select AND, OR, XOR or NOT to complete the circuit.", "Hints reveal direction but cost points. Clear six circuits."]} session={session} onExit={onExit}>
    <div className="logic-console"><div className="logic-board-head"><span>CIRCUIT {String(level + 1).padStart(2, '0')} / 06</span><span>OUTPUT TARGET <b>{Number(puzzle?.result ?? false)}</b></span></div><div className="logic-circuit"><div className="logic-inputs"><span><i className={puzzle?.a ? 'on' : ''}/><b>INPUT A</b><strong>{Number(puzzle?.a ?? false)}</strong></span>{puzzle?.gate !== 'NOT'&&<span><i className={puzzle?.b ? 'on' : ''}/><b>INPUT B</b><strong>{Number(puzzle?.b ?? false)}</strong></span>}</div><div className="logic-wires"><i/><i/></div><div className="logic-gates">{(['AND','OR','XOR','NOT'] as const).map(gate=><button key={gate} className={selected===gate?'selected':''} onClick={()=>selectGate(gate)} disabled={Boolean(selected)}><span>{gate}</span><small>LOGIC GATE</small></button>)}</div><div className="logic-wires output"><i/></div><div className="logic-output"><b>{selected?Number(logicOutput(selected as typeof puzzle.gate,puzzle.a,puzzle.b)):'?'}</b><span>RESULT</span></div></div><div className="logic-feedback" aria-live="polite">{message}</div><button className="arena-text-button" onClick={useHint} disabled={hintUsed}>REQUEST TRACE HINT / -50 PTS</button></div>
  </GameChrome>;
}
