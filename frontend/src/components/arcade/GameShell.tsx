import { useEffect, useRef, useState, type ReactNode } from 'react';

export type GameStatus = 'intro' | 'countdown' | 'playing' | 'over';

export function useArcadeSession(gameId: string, duration = 60) {
  const [status, setStatus] = useState<GameStatus>('intro');
  const [timeLeft, setTimeLeft] = useState(duration);
  const [score, setScoreState] = useState(0);
  const [highScore, setHighScore] = useState(() => { try { return Number(localStorage.getItem(`arena.arcade.${gameId}`) ?? 0); } catch { return 0; } });
  const scoreRef = useRef(0);
  const [countdown, setCountdown] = useState(3);
  const completedRef = useRef(false);
  const setScore = (next: number | ((current: number) => number)) => {
    setScoreState(current => {
      const value = typeof next === 'function' ? next(current) : next;
      scoreRef.current = value;
      return value;
    });
  };
  const complete = (finalScore = scoreRef.current) => {
    if (completedRef.current) return;
    completedRef.current = true;
    setScore(finalScore);
    setStatus('over');
    setHighScore(current => {
      const best = Math.max(current, finalScore);
      try { localStorage.setItem(`arena.arcade.${gameId}`, String(best)); } catch { /* local score is optional */ }
      return best;
    });
  };
  const start = () => {
    scoreRef.current = 0;
    setScoreState(0);
    setTimeLeft(duration);
    setCountdown(3);
    completedRef.current = false;
    setStatus('countdown');
  };
  const reset = () => {
    scoreRef.current = 0;
    setScoreState(0);
    setTimeLeft(duration);
    setStatus('intro');
  };
  useEffect(() => {
    if (status !== 'countdown') return;
    setCountdown(3);
    const timer = window.setInterval(() => {
      setCountdown(current => {
        if (current <= 1) { setStatus('playing'); return 1; }
        return current - 1;
      });
    }, 800);
    return () => window.clearInterval(timer);
  }, [status]);
  useEffect(() => {
    if (status !== 'playing') return;
    const timer = window.setInterval(() => {
      setTimeLeft(current => {
        if (current <= 1) {
          window.setTimeout(() => complete(scoreRef.current), 0);
          return 0;
        }
        return current - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [status]);
  return { status, timeLeft, score, highScore, countdown, setScore, start, reset, complete };
}

export function GameChrome({ title, subtitle, instructions, session, onExit, children }: {
  title: string;
  subtitle: string;
  instructions: string[];
  session: ReturnType<typeof useArcadeSession>;
  onExit: () => void;
  children: ReactNode;
}) {
  const { status, score, timeLeft, highScore, countdown, start, reset } = session;
  return <section className="arcade-game" aria-label={`${title} game`}>
    <header className="arcade-game-head"><button className="arena-text-button" onClick={onExit}>← ARCADE</button><span className="arcade-live-mark"><i/> LOCAL GAME / NO BENCHMARK</span><button className="arena-text-button" onClick={reset}>RESET</button></header>
    <div className="arcade-game-title"><div><span className="arena-eyebrow">ARENA ARCADE / PLAY SESSION</span><h1>{title}</h1><p>{subtitle}</p></div>{status === 'playing' && <div className="arcade-game-stats"><span>SCORE <b>{score}</b></span><span>TIME <b className={timeLeft <= 10 ? 'time-critical' : ''}>{timeLeft}s</b></span><span>LOCAL BEST <b>{highScore}</b></span></div>}</div>
    {status === 'intro' && <div className="game-intro"><div className="game-intro-art"><span>ARENA</span><b>{title.split(' ').map(word => word[0]).join('')}</b><i>SIMULATION / INTERACTIVE</i></div><div><h2>Ready when you are.</h2><ul>{instructions.map(item => <li key={item}>{item}</li>)}</ul><button className="arena-primary" onClick={start}>START GAME <span>→</span></button><p className="arena-disclaimer">Runs locally in your browser. Scores stay on this device.</p></div></div>}
    {status === 'countdown' && <div className="game-countdown" aria-live="polite"><span>GET READY</span><b>{countdown}</b><small>SET YOUR PACE</small></div>}
    {status === 'playing' && <><div className="game-playfield">{children}</div><div className="game-virtual-keys"><span>ON-SCREEN CONTROLS</span>{['←','A','1','2','3','4','5','6','7','8','9','D','→'].map(key=><button key={key} onClick={()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:key==='←'?'ArrowLeft':key==='→'?'ArrowRight':key,bubbles:true}))}>{key}</button>)}<small>Mouse / touch and physical keyboard also work</small></div></>}
    {status === 'over' && <div className="game-over"><span>SESSION COMPLETE</span><h2>{score > 0 ? 'Nice run.' : 'Ready for another run?'}</h2><p>Final local score</p><strong>{score.toLocaleString()}</strong><small>{score >= highScore && score > 0 ? 'NEW PERSONAL BEST' : `PERSONAL BEST / ${highScore}`}</small><div><button className="arena-primary" onClick={start}>PLAY AGAIN <span>↻</span></button><button className="arena-secondary" onClick={onExit}>BACK TO ARCADE</button></div></div>}
  </section>;
}
