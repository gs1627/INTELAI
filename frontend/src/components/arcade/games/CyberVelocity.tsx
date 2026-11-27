import { useEffect, useRef, useState } from 'react';
import { moveLane } from '../gameLogic.js';
import { GameChrome, useArcadeSession } from '../GameShell';

type ObjectOnTrack = { lane: number; y: number; kind: 'drone' | 'energy'; passed: boolean };

export default function CyberVelocity({ onExit }: { onExit: () => void }) {
  const session = useArcadeSession('cyber-velocity', 60);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const laneRef = useRef(1);
  const healthRef = useRef(3);
  const distanceRef = useRef(0);
  const energyRef = useRef(0);
  const actionsRef = useRef(session);
  const endedRef = useRef(false);
  const [hud, setHud] = useState({ lane: 1, health: 3, distance: 0, energy: 0 });
  actionsRef.current = session;

  const steer = (direction: number) => {
    laneRef.current = moveLane(laneRef.current, direction);
    setHud(current => ({ ...current, lane: laneRef.current }));
  };

  useEffect(() => {
    if (session.status === 'countdown') {
      laneRef.current = 1; healthRef.current = 3; distanceRef.current = 0; energyRef.current = 0; endedRef.current = false;
      setHud({ lane: 1, health: 3, distance: 0, energy: 0 });
    }
  }, [session.status]);

  useEffect(() => {
    if (session.status !== 'playing') return;
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) { actionsRef.current.complete(0); return; }
    let width = 0, height = 0, last = performance.now(), spawn = 0, frame = 0;
    let objects: ObjectOnTrack[] = [];
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
      width = rect.width; height = rect.height;
      canvas.width = Math.max(1, Math.floor(width * ratio)); canvas.height = Math.max(1, Math.floor(height * ratio));
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };
    resize();
    const observer = new ResizeObserver(resize); observer.observe(canvas);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft' || event.key.toLowerCase() === 'a') { event.preventDefault(); steer(-1); }
      if (event.key === 'ArrowRight' || event.key.toLowerCase() === 'd') { event.preventDefault(); steer(1); }
    };
    window.addEventListener('keydown', onKey);
    const draw = (now: number) => {
      const dt = Math.min(42, now - last); last = now; distanceRef.current += dt * 0.015;
      const speed = 0.22 + Math.min(0.3, distanceRef.current / 800);
      spawn += dt;
      if (spawn > Math.max(430, 940 - distanceRef.current * 1.2)) {
        spawn = 0; objects.push({ lane: Math.floor(Math.random() * 3), y: -24, kind: Math.random() > 0.42 ? 'drone' : 'energy', passed: false });
      }
      context.clearRect(0, 0, width, height);
      const sky = context.createLinearGradient(0, 0, 0, height); sky.addColorStop(0, '#071223'); sky.addColorStop(1, '#10112b');
      context.fillStyle = sky; context.fillRect(0, 0, width, height);
      for (let i = 0; i < 55; i++) { const x = (i * 79 + frame * (i % 3 + 1) * 0.18) % width; const y = (i * 47 + frame * (i % 4 + 1) * 0.24) % height; context.fillStyle = `rgba(154,220,255,${0.18 + (i % 5) * 0.1})`; context.fillRect(x, y, 1.5, 1.5); }
      const horizon = height * 0.2;
      context.strokeStyle = 'rgba(68,190,255,.26)'; context.lineWidth = 1;
      for (let lane = 0; lane <= 3; lane++) { const bottomX = width * lane / 3; context.beginPath(); context.moveTo(width / 2 + (lane - 1.5) * 18, horizon); context.lineTo(bottomX, height); context.stroke(); }
      for (let row = 0; row < 13; row++) { const t = ((row / 13 + frame * 0.002) % 1); const y = horizon + (height - horizon) * t * t; context.beginPath(); context.moveTo(width * (0.29 - t * 0.29), y); context.lineTo(width * (0.71 + t * 0.29), y); context.stroke(); }
      objects.forEach(object => { object.y += dt * speed; const x = width * ((object.lane + 0.5) / 3); const scale = 0.38 + (object.y / height) * 1.1; const size = 22 * scale;
        if (object.kind === 'energy') { context.shadowBlur = 18; context.shadowColor = '#69f5ff'; context.fillStyle = '#9afaff'; context.beginPath(); context.arc(x, object.y, size * 0.5, 0, Math.PI * 2); context.fill(); context.shadowBlur = 0; }
        else { context.shadowBlur = 14; context.shadowColor = '#ff546f'; context.fillStyle = '#ff617b'; context.beginPath(); context.moveTo(x, object.y - size * 0.7); context.lineTo(x + size * 0.75, object.y); context.lineTo(x, object.y + size * 0.7); context.lineTo(x - size * 0.75, object.y); context.closePath(); context.fill(); context.shadowBlur = 0; }
        if (!object.passed && object.y > height - 88) { object.passed = true; if (object.lane === laneRef.current) { if (object.kind === 'energy') { energyRef.current += 1; actionsRef.current.setScore(score => score + 100); } else healthRef.current -= 1; setHud({ lane: laneRef.current, health: healthRef.current, distance: Math.floor(distanceRef.current), energy: energyRef.current }); } }
      });
      objects = objects.filter(object => object.y < height + 40);
      const playerX = width * ((laneRef.current + 0.5) / 3); const py = height - 52;
      context.shadowBlur = 22; context.shadowColor = '#56d9ff'; context.fillStyle = '#eafaff'; context.beginPath(); context.moveTo(playerX, py - 24); context.lineTo(playerX + 20, py + 16); context.lineTo(playerX, py + 8); context.lineTo(playerX - 20, py + 16); context.closePath(); context.fill(); context.shadowBlur = 0;
      frame += 1;
      if (healthRef.current <= 0 && !endedRef.current) { endedRef.current = true; actionsRef.current.complete(Math.floor(distanceRef.current) + energyRef.current * 100); return; }
      if (session.timeLeft > 0 && !endedRef.current) raf = requestAnimationFrame(draw);
    };
    let raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); observer.disconnect(); window.removeEventListener('keydown', onKey); };
  }, [session.status]);

  return <GameChrome title="Cyber Velocity" subtitle="Hold the neon lane. Dodge the drones. Catch the energy cells." instructions={["Steer through three lanes and avoid red drones.", "Collect cyan energy cells for score and travel farther to increase speed.", "Use ← → or A / D, or the touch controls. Three collisions end the run."]} session={session} onExit={onExit}>
    <div className="velocity-hud"><span>HULL <b>{'◆'.repeat(hud.health)}{'◇'.repeat(Math.max(0,3-hud.health))}</b></span><span>DISTANCE <b>{hud.distance} m</b></span><span>ENERGY <b>{hud.energy}</b></span></div><canvas className="velocity-canvas" ref={canvasRef} aria-label="Cyber Velocity game track"/><div className="velocity-controls"><button onClick={()=>steer(-1)} aria-label="Steer left">←</button><span>STEER / A · D</span><button onClick={()=>steer(1)} aria-label="Steer right">→</button></div><p className="arena-disclaimer">Arcade motion simulation. It is not a device performance benchmark.</p>
  </GameChrome>;
}
