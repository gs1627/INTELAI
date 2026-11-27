import { useEffect, useState } from 'react';
import { GameChrome, useArcadeSession } from '../GameShell';

const questions = [
  { q:'What does an NPU primarily accelerate?', choices:['AI workloads','Every display pixel','Wi-Fi reception','Keyboard input'], answer:0 },
  { q:'What proves a workload ran on an NPU?', choices:['The laptop has an NPU','A device scan found one','Verified runtime evidence for that run','A product badge'], answer:2 },
  { q:'Which detail is safest to omit from a public prompt?', choices:['The task topic','The requested format','A personal account number','The output length'], answer:2 },
  { q:'Why compare the same model and prompt?', choices:['It keeps the test more controlled','It makes every chip identical','It guarantees an NPU win','It removes all system variation'], answer:0 },
  { q:'What does the local high score represent?', choices:['A global leaderboard rank','A verified hardware score','A score saved in this browser','A retail rating'], answer:2 },
  { q:'If compatible benchmark history is missing, show…', choices:['A guessed score','A competitor average','Insufficient comparable data','An AI estimate'], answer:2 },
];

export default function InsightQuest({ onExit }: { onExit: () => void }) {
  const session=useArcadeSession('insight-quest',75); const [index,setIndex]=useState(0); const [selected,setSelected]=useState<number|null>(null); const [streak,setStreak]=useState(0); const [feedback,setFeedback]=useState('Choose the strongest answer.'); const [busy,setBusy]=useState(false);
  useEffect(()=>{if(session.status==='countdown'){setIndex(0);setSelected(null);setStreak(0);setBusy(false);setFeedback('Choose the strongest answer.')}},[session.status]);
  const current=questions[index];
  const answer=(choice:number)=>{
    if(selected!==null||busy||!current)return;
    setSelected(choice);setBusy(true);
    const correct=choice===current.answer; const points=correct?120+streak*20:0;
    if(correct){session.setScore(score=>score+points);setStreak(value=>value+1);setFeedback(`Correct · +${points} · ${streak+1} in a row`)}else{setStreak(0);session.setScore(score=>Math.max(0,score-35));setFeedback(`Answer: ${current.choices[current.answer]}`)}
    window.setTimeout(()=>{if(index+1===questions.length){session.complete(Math.max(0,session.score+(correct?points:-35)));return;}setIndex(value=>value+1);setSelected(null);setBusy(false);setFeedback('Next question. Trust the evidence.')},900);
  };
  return <GameChrome title="AI Insight Quest" subtitle="Learn what the hardware can do—and what proof actually means." instructions={["Answer six quick questions about AI PC features.", "Build a correct-answer streak for bonus points.", "This is an educational quiz, not a hardware test."]} session={session} onExit={onExit}>
    <div className="insight-board"><div className="insight-progress">{questions.map((item,i)=><i key={item.q} className={i<index?'done':i===index?'active':''}/>)}</div><div className="insight-question"><span>QUESTION {String(index+1).padStart(2,'0')} / 06</span><h2>{current?.q}</h2></div><div className="insight-choices">{current?.choices.map((choice,i)=><button key={choice} className={selected===i?i===current.answer?'correct':'incorrect':''} disabled={selected!==null} onClick={()=>answer(i)}><span>0{i+1}</span><b>{choice}</b><i>{selected===i?(i===current.answer?'✓':'×'):'↗'}</i></button>)}</div><p className="insight-feedback" aria-live="polite">{feedback}</p><p className="arena-disclaimer">Curated educational content. Scores are local and do not represent device performance.</p></div>
  </GameChrome>;
}
