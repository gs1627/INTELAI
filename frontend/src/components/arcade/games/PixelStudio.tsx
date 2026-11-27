import { useEffect, useState, type CSSProperties } from 'react';
import { GameChrome, useArcadeSession } from '../GameShell';

type Pixel = [number, number, string];
const art: { name: string; pixels: Pixel[] }[] = [
  { name: 'ORBIT', pixels: [[3,0,'c'],[2,1,'c'],[3,1,'w'],[4,1,'c'],[1,2,'c'],[2,2,'w'],[3,2,'w'],[4,2,'w'],[5,2,'c'],[1,3,'c'],[2,3,'w'],[3,3,'b'],[4,3,'w'],[5,3,'c'],[2,4,'c'],[3,4,'w'],[4,4,'c'],[3,5,'c']] },
  { name: 'PULSE', pixels: [[0,3,'p'],[1,3,'p'],[2,2,'p'],[3,4,'p'],[4,1,'p'],[5,5,'p'],[6,2,'p'],[7,3,'p'],[2,3,'w'],[3,3,'w'],[4,3,'w'],[5,3,'w']] },
  { name: 'NOVA', pixels: [[3,0,'y'],[3,1,'y'],[1,2,'c'],[2,2,'c'],[3,2,'y'],[4,2,'c'],[5,2,'c'],[2,3,'c'],[3,3,'w'],[4,3,'c'],[1,4,'c'],[2,4,'c'],[3,4,'c'],[4,4,'c'],[5,4,'c'],[3,5,'y']] },
];
const palette = [{id:'c',color:'#51dbff',name:'Cyan'},{id:'w',color:'#ecf8ff',name:'White'},{id:'b',color:'#8984ff',name:'Violet'},{id:'p',color:'#ff63c6',name:'Pink'},{id:'y',color:'#ffd46b',name:'Gold'}];

export default function PixelStudio({ onExit }: { onExit: () => void }) {
  const session = useArcadeSession('pixel-studio', 75);
  const [level,setLevel]=useState(0);
  const [color,setColor]=useState('c');
  const [painted,setPainted]=useState<Record<string,string>>({});
  const [message,setMessage]=useState('Rebuild the target using the light-grid.');
  const [submitted,setSubmitted]=useState(false);
  useEffect(()=>{if(session.status==='countdown'){setLevel(0);setPainted({});setColor('c');setSubmitted(false);setMessage('Rebuild the target using the light-grid.')}},[session.status]);
  const submit=()=>{
    if(submitted)return;
    setSubmitted(true);
    const expected=new Map(art[level].pixels.map(([x,y,c])=>[`${x}-${y}`,c]));
    let correct=0; let mistakes=0;
    expected.forEach((c,key)=>painted[key]===c?correct++:mistakes++);
    Object.keys(painted).forEach(key=>{if(!expected.has(key))mistakes++});
    const points=Math.max(0,correct*40-mistakes*12);
    session.setScore(score=>score+points);
    setMessage(`${correct} target pixels aligned - ${mistakes} stray or missing`);
    if(level+1===art.length){window.setTimeout(()=>session.complete(session.score+points),900);return}
    window.setTimeout(()=>{setLevel(current=>current+1);setPainted({});setSubmitted(false);setMessage('Next signal loaded. Keep the grid clean.')},900);
  };
  return <GameChrome title="Pixel Studio" subtitle="Compose a signal one pixel at a time." instructions={["Match the target glyph on the 8 x 8 display.", "Choose a color, then click or tap cells to paint.", "Submit three increasingly detailed signals before time runs out."]} session={session} onExit={onExit}>
    <div className="pixel-studio">
      <div className="pixel-target">
        <span>REFERENCE / {art[level]?.name}</span>
        <div>{Array.from({length:64},(_,i)=>{const key=`${i%8}-${Math.floor(i/8)}`;const hex=art[level]?.pixels.find(([x,y])=>`${x}-${y}`===key)?.[2];return <i key={key} style={{background:hex?palette.find(p=>p.id===hex)?.color:'transparent'}}/>})}</div>
        <small>REBUILD IN LIGHT</small>
      </div>
      <div className="pixel-editor">
        <div className="pixel-editor-head"><span>ARENA PIXEL CANVAS</span><span>FRAME {String(level+1).padStart(2,'0')} / 03</span></div>
        <div className="pixel-grid">{Array.from({length:64},(_,i)=>{const key=`${i%8}-${Math.floor(i/8)}`;const fill=palette.find(p=>p.id===painted[key])?.color;return <button key={key} aria-label={`Pixel ${key}`} className={fill?'filled':''} style={{background:fill??undefined}} onClick={()=>setPainted(current=>({...current,[key]:current[key]===color?'':color}))}/>})}</div>
        <div className="pixel-palette">{palette.map(item=><button key={item.id} title={item.name} aria-label={`Select ${item.name}`} className={color===item.id?'selected':''} style={{'--swatch':item.color} as CSSProperties} onClick={()=>setColor(item.id)}/>)}</div>
        <div className="pixel-feedback" aria-live="polite">{message}</div>
        <button className="arena-primary" disabled={submitted} onClick={submit}>SUBMIT FRAME <span>-&gt;</span></button>
      </div>
    </div>
    <p className="arena-disclaimer">Creative browser interaction. No graphics benchmark is run.</p>
  </GameChrome>;
}
