import React, {useState, useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import HrDashboard from './HrDashboard';
import Sharing,{SharedView} from './Sharing';
function App(){
 const cardId=new URLSearchParams(window.location.search).get("card");
 const [role,setRole]=useState(''); const [token,setToken]=useState(''); const [input,setInput]=useState('');
 const [profile,setProfile]=useState<any>(null); const [result,setResult]=useState<any>(null);
 const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
 const [style,setStyle]=useState(localStorage.getItem('cq-style') || 'anime');
 async function api(path:string,method='GET',body?:any){
  const r=await fetch('/api/'+path,{method,headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});
  if(!r.ok){let message='Не удалось выполнить запрос.';try{const data=await r.json();message=Array.isArray(data.detail)?data.detail.map((e:any)=>(e.path||e.loc?.join('.')||'')+': '+(e.message||e.msg)).join('\n'):data.detail||message;}catch{}throw new Error(message);}return r.json();
 }
 async function refresh(){setBusy(true);setError('');try{const session=await api('session');setRole(session.role);if(session.role==='employee'&&!cardId){const p=await api('me');const r=await api('recommendations');if(p.revision!==r.revision)throw new Error('Данные изменились. Обновите профиль.');setProfile(p);setResult(r);}}catch(e:any){setError(e.message);}finally{setBusy(false);}}
 useEffect(()=>{if(token)refresh();},[token]);
 async function finish(id:string){setBusy(true);setError('');try{await api('activities/'+id+'/complete','POST',{expected_revision:profile.revision});await refresh();}catch(e:any){setError(e.message);setBusy(false);}}
 function logout(){setToken('');setRole('');setProfile(null);setResult(null);setInput('');setError('');}
 function theme(value:string){setStyle(value);localStorage.setItem('cq-style',value);}
 return <div className="shell"><header><a href="/" className="brand">CQ<span>CAREER QUEST</span></a><span className="private">Личное пространство · NovaAI</span></header>
 {role==='employee'&&cardId?<SharedView id={cardId} request={api} logout={logout}/>:(role==='hr'||role==='manager')?<HrDashboard request={api} logout={logout} role={role}/>:!profile?<main className="login"><p className="eyebrow">ТВОЯ СЛЕДУЮЩАЯ ГЛАВА</p><h1>Расти в профессии.<br/>Развивай своего героя.</h1><p>Осмысленные шаги к следующему грейду.</p><form onSubmit={e=>{e.preventDefault();if(token===input)refresh();else setToken(input);}}><label>Токен доступа (сотрудник, HR или руководитель)<input type="password" required value={input} onChange={e=>setInput(e.target.value)} /></label><button disabled={busy}>Войти →</button></form></main>:<main>
 <section className="intro"><div><p className="eyebrow">ТВОЯ КАРЬЕРА. ТВОЙ СЦЕНАРИЙ.</p><h1>Следующий уровень<br/>начинается с тебя.</h1><p>Каждый шаг имеет значение. Выбери свой следующий.</p></div><button className="secondary" onClick={logout}>Выйти</button></section>
 <div className="layout"><aside><div className={'hero '+style}><div className="card-top"><span>{profile.employee.grade}</span><span>ЛИЧНЫЙ ГЕРОЙ</span></div><div className="avatar" aria-label="Стилизованный символ персонажа">{style==='anime'?'✦':'⚽'}</div><p>{style==='anime'?'АРХИТЕКТОР БУДУЩЕГО':'СОЗДАТЕЛЬ ИГРЫ'}</p><h2>{profile.employee.role}</h2><div className="hero-footer"><strong>{profile.readiness}%</strong><span>готовность к {profile.target_grade}<br/>по требованиям навыков</span></div></div>
 <div className="styles"><button aria-pressed={style==='anime'} onClick={()=>theme('anime')}>✦ Аниме</button><button aria-pressed={style==='football'} onClick={()=>theme('football')}>⚽ Футбол</button></div><p className="hint">Стиль меняется. Твой прогресс сохраняется между перезапусками.</p></aside>
 <section><div className="section-title"><h2>Твоя траектория</h2><span>{profile.employee.grade} → {profile.target_grade}</span></div><div className="panel">{Object.entries(profile.requirements).map(([skill,required]:any)=><div className="skill" key={skill}><div><span>{skill.replaceAll('SK_','').replaceAll('_',' ')}</span><b>{profile.employee.skills[skill]||0} / {required}</b></div><progress max={required||5} value={Math.min(profile.employee.skills[skill]||0,required)}/></div>)}</div>
 <div className="section-title"><h2>Следующие шаги</h2><span>Подобраны для тебя</span></div>
 {result?.recommendations.length===0&&<div className="panel">Подходящих активностей пока нет. Требования могут быть выполнены либо каталог нужно дополнить.</div>}
 {result?.recommendations.map((r:any,i:number)=><article className="recommendation" key={r.event.id}><div className="tag">{i===0?'ПРИОРИТЕТНЫЙ ШАГ':'ДОСТУПНЫЙ ШАГ'} · {r.event.type}</div><h3>{r.event.title}</h3><details><summary>Почему именно это?</summary>{r.factors.map((f:any)=><div className="reason" key={f.skill}><p><b>Цель:</b> {r.target_grade} требует {f.required} по {f.skill.replace('SK_','')}; вес критичности — {f.criticality}.</p><p><b>Разрыв:</b> сейчас {f.current}; активность закрывает {f.effective_gain} из {f.gap} уровней.</p><p><b>История:</b> завершено {f.completed_count} из {f.history_count} связанных активностей. Оценка принятия с учётом формата: {Math.round(f.acceptance*100)}%. {f.history_count===0?'Истории навыка пока нет; используется сглаженная оценка.':''}</p></div>)}{i>0&&<p>Почему не первый выбор: оценка {r.score}; у первого варианта — {result.recommendations[0].score}. При равенстве оценок порядок определяется ID события.</p>}</details><button disabled={busy||!profile.demo_mode} onClick={()=>finish(r.event.id)}>{profile.demo_mode?"Демо: отметить выполненным ↗":"Требуется подтверждение обучения"}</button></article>)}
 <section className="panel"><h2>Обязательное обучение</h2><p className="hint">Отдельно от добровольного развития. Без игровых наград.</p>{profile.mandatory_training?.length?profile.mandatory_training.map((t:any)=><div className="training" key={t.event_id}><h3>{t.title}</h3><p>{({completed:'Завершено',pending:'Ожидает прохождения',overdue:'Срок прошёл'} as any)[t.status]} · {t.due_date||'Без срока'}</p></div>):<p>Нет назначенных курсов.</p>}</section><Sharing request={api} style={style} revision={profile.revision}/><div className="panel history"><h3>История участия</h3>{profile.history.map((h:any,i:number)=><p key={i}>{h.date} · {h.event_id} · {h.status}</p>)}</div></section></div>
 <footer>Демонстрационные данные · Объяснения по проверяемым правилам · Без публичных рейтингов</footer></main>}
 {error&&<div className="error" role="alert">{error}<button onClick={refresh}>Повторить</button></div>}</div>
}
createRoot(document.getElementById('root')!).render(<App/>);
