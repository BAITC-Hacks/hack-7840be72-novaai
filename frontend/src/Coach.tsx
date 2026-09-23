import React,{useEffect,useRef,useState} from 'react';
import {tr,getLocale} from './i18n';
type Turn={role:'user'|'assistant';content:string;mode?:string;evidence?:any;fallback?:string};
export default function Coach({request,revision}:any){
 const [turns,setTurns]=useState<Turn[]>([]),[question,setQuestion]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const [status,setStatus]=useState<any>(null);
 const generation=useRef(0),bottom=useRef<HTMLDivElement>(null);
 useEffect(()=>{const epoch=++generation.current;setTurns([]);setError('');setBusy(false);setStatus(null);request('coach/status').then((s:any)=>{if(epoch===generation.current)setStatus(s);}).catch((e:any)=>{if(epoch===generation.current)setError(e.message);});return()=>{generation.current++;};},[revision]);
 useEffect(()=>{bottom.current?.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});},[turns,busy]);
 async function ask(text=question){
  const clean=text.trim();if(!clean||busy||!status)return;
  const epoch=generation.current;const old=turns;setBusy(true);setError('');setQuestion('');
  setTurns([...old,{role:'user',content:clean}]);
  try{const response=await request('coach','POST',{message:clean,language:getLocale(),history:old.slice(-6).map(t=>({role:t.role,content:t.content.slice(0,4000)}))});
   if(epoch===generation.current)setTurns([...old,{role:'user',content:clean},{role:'assistant',content:response.answer,mode:response.mode,evidence:response.evidence,fallback:response.fallback_reason}]);
  }catch(e:any){if(epoch===generation.current){setTurns(old);setQuestion(clean);setError(e.message);}}finally{if(epoch===generation.current)setBusy(false);}
 }
 function clear(){generation.current++;setTurns([]);setError('');setQuestion('');setBusy(false);}
 return <section className="coach-panel panel"><div className="section-title"><div><p className="eyebrow">{tr('ТВОЙ ПЕРСОНАЛЬНЫЙ НАСТАВНИК')}</p><h2>{tr('Разберём следующий шаг вместе')}</h2></div><button className="secondary" onClick={clear} disabled={busy||!turns.length}>{tr('Очистить диалог')}</button></div>
 <p className="coach-mode">{status?.mode==='llm'?tr('LLM настроена — доступ проверяется при запросе'):tr('Режим по правилам — LLM не подключена')}</p>
 <p className="hint">{tr('Наставник видит только твой профиль. Он не может менять навыки, начислять баллы или подтверждать обучение.')}</p>
 {status?.external_processing&&<p className="warning">{tr('При отправке вопрос и ограниченный контекст рекомендаций будут переданы настроенному AI-провайдеру. Не вводи конфиденциальные данные.')}</p>}
 <div className="coach-suggestions">{['Что мне сделать для следующего грейда?','Почему System Design, а не Public Speaking?','Как найти подходящего ментора?'].map(q=><button key={q} disabled={busy||!status} onClick={()=>ask(tr(q))}>{tr(q)}</button>)}</div>
 <div className="chat-log" role="log" aria-live="polite" aria-label={tr('Диалог с наставником')}>
 {!turns.length&&<div className="chat-empty"><span>✧</span><h3>{tr('С чего начнём?')}</h3><p>{tr('Спроси о карьерной цели, разрывах в навыках или причинах рекомендаций.')}</p></div>}
 {turns.map((turn,i)=><article className={'chat-message '+turn.role} key={i}><small>{turn.role==='user'?tr('Ты'):tr('Наставник')}{turn.mode&&' · '+(turn.mode==='llm'?'LLM':tr('По правилам'))}</small><p>{turn.content}</p>{turn.fallback==='provider_unavailable'&&<p className="hint">{tr('Провайдер недоступен. Показан резервный ответ по данным.')}</p>}{turn.evidence&&<details><summary>{tr('Факты, на которых основан ответ')}</summary><p>{tr('Целевой грейд:')} {turn.evidence.target_grade}</p>{turn.evidence.recommendations.map((r:any)=><div className="reason" key={r.event_id}><b>{tr(r.title)}</b>{r.factors.map((f:any)=><p key={f.skill}>{f.skill}: {f.current} → {f.required} · {tr('Прирост:')} {f.effective_gain} · {tr('Завершено:')} {f.completed_count}/{f.history_count}</p>)}</div>)}</details>}</article>)}
 {busy&&<p role="status">{tr('Готовлю ответ…')}</p>}<div ref={bottom}/></div>
 {error&&<p className="inline-error" role="alert">{tr(error)}</p>}
 <form className="chat-form" onSubmit={e=>{e.preventDefault();ask();}}><label>{tr('Твой вопрос')}<textarea value={question} onChange={e=>setQuestion(e.target.value)} maxLength={2000} rows={3} disabled={busy} placeholder={tr('Например: какой навык развивать следующим?')}/></label><div><span className="hint">{question.length}/2000</span><button disabled={busy||!status||!question.trim()}>{tr('Отправить')} ↗</button></div></form>
 <p className="hint">{tr('Диалог хранится только на этом экране и очищается при выходе из раздела. Ответ модели может ошибаться — сверяйся с фактами.')}</p></section>;
}
