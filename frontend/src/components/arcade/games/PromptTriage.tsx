import { useEffect, useState } from 'react';
import { GameChrome, useArcadeSession } from '../GameShell';

const briefs = [
  { title:'Turn class notes into a revision outline.', safe:['topic','notes','format'], cards:[['topic','Cell biology'],['notes','Lecture notes'],['format','Three-bullet outline'],['identity','Student name'],['credential','Campus password']] },
  { title:'Draft a project update for your team.', safe:['goal','progress','tone'], cards:[['goal','Milestone summary'],['progress','Tasks completed'],['tone','Concise and clear'],['private','Teammate medical leave'],['credential','Private login token']] },
  { title:'Find the key themes in a creative brief.', safe:['brief','audience','output'], cards:[['brief','Campaign brief'],['audience','Intended audience'],['output','Three visual themes'],['identity','Client personal phone'],['private','Unreleased personal records']] },
  { title:'Organize a weekly household checklist.', safe:['tasks','schedule','format'], cards:[['tasks','Chores to remember'],['schedule','Saturday morning'],['format','Tick-box list'],['identity','Home access code'],['private','Personal account number']] },
];

export default function PromptTriage({ onExit }: { onExit: () => void }) {
  const session=useArcadeSession('prompt-triage',65); const [round,setRound]=useState(0); const [selected,setSelected]=useState<string[]>([]); const [locked,setLocked]=useState(false); const [message,setMessage]=useState('Select only the context the task needs.');
  useEffect(()=>{if(session.status==='countdown'){setRound(0);setSelected([]);setLocked(false);setMessage('Select only the context the task needs.')}},[session.status]);
  const brief=briefs[round];
  const submit=()=>{
    if(locked||!brief)return;
    setLocked(true);
    const expected=new Set(brief.safe); const chosen=new Set(selected);
    const hits=[...expected].filter(item=>chosen.has(item)).length;
    const leaks=[...chosen].filter(item=>!expected.has(item)).length;
    const points=Math.max(0,hits*90-leaks*120);
    session.setScore(score=>score+points);
    setMessage(`${hits} relevant details kept · ${leaks} unnecessary detail${leaks===1?'':'s'} included · +${points}`);
    window.setTimeout(()=>{
      if(round+1===briefs.length){session.complete(session.score+points);return;}
      setRound(value=>value+1);setSelected([]);setLocked(false);setMessage('Next brief ready. Keep context lean.');
    },850);
  };
  return <GameChrome title="Prompt Triage" subtitle="Shape a useful prompt with only the context it needs." instructions={["Read each task brief and select the useful context cards.", "Avoid identity, credentials or unrelated private details.", "Four rounds. This is a privacy exercise; no AI model is called."]} session={session} onExit={onExit}>
    <div className="triage-board"><div className="triage-label"><span>PRIVACY FIRST / LOCAL INTERACTIVE SIMULATION</span><b>ROUND {String(round+1).padStart(2,'0')} / 04</b></div><div className="triage-request"><small>YOUR TASK</small><h2>{brief?.title}</h2></div><div className="triage-cards">{brief?.cards.map(([id,label])=><button key={id} disabled={locked} className={`triage-card ${selected.includes(id)?'chosen':''} ${id==='identity'||id==='credential'||id==='private'?'sensitive':''}`} onClick={()=>setSelected(current=>current.includes(id)?current.filter(item=>item!==id):[...current,id])}><i>{selected.includes(id)?'✓':id==='identity'||id==='credential'||id==='private'?'!':'+'}</i><span>{label}</span><small>{selected.includes(id)?'IN PROMPT':'TAP TO INCLUDE'}</small></button>)}</div><div className="triage-actions"><p aria-live="polite">{message}</p><button className="arena-primary" onClick={submit} disabled={locked}>CHECK PROMPT <span>→</span></button></div><p className="arena-disclaimer">Rule-based game scoring only. No text is sent to a model or service.</p></div>
  </GameChrome>;
}
