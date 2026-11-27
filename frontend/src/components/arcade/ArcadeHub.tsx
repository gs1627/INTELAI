import { useEffect, useState } from 'react';
import { BrainCircuit, Fingerprint, Gamepad2, Palette, Rocket, ShieldCheck, Waypoints } from 'lucide-react';
import { arcadeTotal } from './gameLogic.js';

const games = [
  { id:'neural-memory-rush', title:'Neural Memory Rush', type:'PATTERN / FOCUS', difficulty:'ADAPTIVE', description:'Read a growing signal chain and replay it before the next pulse.', icon:BrainCircuit, color:'cyan', tag:'SIGNAL RECALL' },
  { id:'cyber-velocity', title:'Cyber Velocity', type:'ARCADE / REFLEX', difficulty:'RAMPING', description:'Thread three lanes, avoid drones and collect energy through the neon run.', icon:Rocket, color:'blue', tag:'LANE SURVIVAL' },
  { id:'logic-breaker', title:'Logic Breaker', type:'PUZZLE / CIRCUITS', difficulty:'6 CIRCUITS', description:'Route binary signals through AND, OR, XOR and NOT gates.', icon:Waypoints, color:'violet', tag:'CIRCUIT TRACE' },
  { id:'prompt-triage', title:'Prompt Triage', type:'AI / PRIVACY', difficulty:'4 BRIEFS', description:'Keep useful context. Leave private details out of the prompt.', icon:ShieldCheck, color:'mint', tag:'PRIVACY FIRST' },
  { id:'pixel-studio', title:'Pixel Studio', type:'CREATIVE / VISUALS', difficulty:'3 FRAMES', description:'Rebuild glowing signal art one pixel at a time.', icon:Palette, color:'pink', tag:'LIGHT CANVAS' },
  { id:'insight-quest', title:'AI Insight Quest', type:'KNOWLEDGE / AI PC', difficulty:'6 QUESTIONS', description:'Separate real AI PC capabilities from assumptions and marketing.', icon:Fingerprint, color:'gold', tag:'PROOF CHECK' },
];

export type GameId = typeof games[number]['id'];
export default function ArcadeHub({ onPlay, onExit }: { onPlay: (id: GameId) => void; onExit: () => void }) {
  const [scores,setScores]=useState<Record<string,number>>({});
  useEffect(()=>{const next:Record<string,number>={};games.forEach(game=>{try{next[game.id]=Number(localStorage.getItem(`arena.arcade.${game.id}`)??0)}catch{next[game.id]=0}});setScores(next)},[]);
  const total=arcadeTotal(scores);
  return <section className="arcade-hub"><header className="arena-section-head"><div><span className="arena-eyebrow">ARENA OS / INTERACTIVE ARCADE</span><h1>Choose your next run.</h1><p>Six quick, local games. Every score belongs to this browser—no global leaderboard, no hardware claims.</p></div><button className="arena-secondary" onClick={onExit}>← BACK TO DESKTOP</button></header><div className="arcade-overview"><div><span>LOCAL ARCADE SCORE</span><b>{total.toLocaleString()}</b><small>SUM OF PERSONAL BESTS</small></div><div><span>PERSONAL RECORDS</span><b>{Object.values(scores).filter(Boolean).length}<small> / 06</small></b><small>SAVED ON THIS DEVICE</small></div><div><span>ACHIEVEMENTS</span><b>{Object.values(scores).filter(score=>score>=500).length}<small> / 06</small></b><small>500 POINTS IN A GAME</small></div></div><div className="arcade-cards">{games.map((game,index)=>{const Icon=game.icon;return <article className={`arcade-card accent-${game.color}`} key={game.id}><div className="arcade-card-top"><span>0{index+1} / {game.tag}</span><Icon size={23}/></div><div className="arcade-card-glyph"><i/><i/><i/><b>{String(index+1).padStart(2,'0')}</b></div><div className="arcade-card-body"><span>{game.type} <i/> {game.difficulty}</span><h2>{game.title}</h2><p>{game.description}</p><div><span>PERSONAL BEST</span><strong>{scores[game.id]?.toLocaleString()??'—'}</strong></div><button onClick={()=>onPlay(game.id)}>OPEN GAME <b>↗</b></button></div></article>})}</div><p className="arcade-footnote"><Gamepad2 size={15}/> Every game runs locally. No data leaves this screen. Scores are not AI benchmark measurements.</p></section>;
}
