import React, {useEffect, useState} from 'react';
const names = ['employees.json', 'events.json', 'skills.json', 'activity_history.csv'];
export default function HrDashboard({request,logout}:any){
 const [summary,setSummary]=useState<any>(null);
 const [files,setFiles]=useState<Record<string,string>>({});
 const [preview,setPreview]=useState<any>(null);
 const [error,setError]=useState(''); const [notice,setNotice]=useState('');
 const [busy,setBusy]=useState(false);
 async function load(){setSummary(await request('hr/summary'));}
 useEffect(()=>{load().catch(e=>setError(e.message));},[]);
 async function select(list:FileList|null){
  setPreview(null);setError('');setNotice('');setFiles({});
  if(!list)return;
  const selected=Array.from(list);
  if(selected.length!==4 || names.some(n=>!selected.some(f=>f.name===n))){setError('Выберите ровно четыре файла: '+names.join(', '));return;}
  if(selected.reduce((sum,f)=>sum+f.size,0)>12*1024*1024){setError('Суммарный размер файлов не должен превышать 12 MiB.');return;}
  setBusy(true);
  try{const pairs=await Promise.all(selected.map(async f=>[f.name,await f.text()]));setFiles(Object.fromEntries(pairs));}
  catch{setError('Не удалось прочитать файлы.');}finally{setBusy(false);}
 }
 async function check(){setBusy(true);setError('');setNotice('');setPreview(null);try{setPreview(await request('hr/import/preview','POST',{files}));}catch(e:any){setError(e.message);}finally{setBusy(false);}}
 async function apply(){setBusy(true);setError('');try{await request('hr/import','POST',{files,digest:preview.digest,expected_revision:preview.revision});setPreview(null);setFiles({});setNotice('Датасет загружен. Аналитика пересчитана.');await load();}catch(e:any){setError(e.message);setPreview(null);}finally{setBusy(false);}}
 return <main><section className="intro"><div><p className="eyebrow">КОМАНДА В РАЗВИТИИ</p><h1>Картина компетенций</h1><p>Агрегированная аналитика без персональных траекторий.</p></div><button className="secondary" onClick={logout}>Выйти</button></section>
 {summary&&<><div className="metrics"><article className="panel"><span>Сотрудников</span><strong>{summary.employee_count}</strong></article><article className="panel"><span>Без следующего шага</span><strong>{summary.without_recommendations}</strong></article><article className="panel"><span>Завершено активностей</span><strong>{summary.participation.completed}</strong></article></div>
 <div className="hr-grid"><section className="panel"><h2>Дефициты навыков</h2><p className="hint">Количество профилей с разрывом до следующего грейда.</p>{Object.entries(summary.skill_deficits).sort((a:any,b:any)=>b[1]-a[1]).map(([skill,count]:any)=><div className="skill" key={skill}><div><span>{skill.replace('SK_','').replaceAll('_',' ')}</span><b>{count}</b></div><progress value={count} max={summary.employee_count}/></div>)}{Object.keys(summary.skill_deficits).length===0&&<p>Дефицитов не найдено.</p>}</section>
 <section className="panel"><h2>Участие в активностях</h2>{Object.entries(summary.participation).map(([key,value]:any)=><p key={key}>{({completed:'Завершено',skipped:'Пропущено',declined:'Отклонено'} as any)[key]}: <b>{value}</b></p>)}<p className="hint">Пропуск сам по себе не свидетельствует о риске увольнения.</p></section></div></>}
 <section className="panel import"><p className="eyebrow">ПРОВЕРКА ДАТАСЕТА</p><h2>Загрузить JSON / CSV</h2><p>Выберите четыре файла по схеме README. Сначала проверим формат, затем покажем состав загрузки.</p><label htmlFor="dataset">Файлы датасета<input id="dataset" type="file" accept=".json,.csv" multiple disabled={busy} onChange={e=>select(e.target.files)}/></label><p className="hint">{names.join(' · ')}</p><button disabled={busy||Object.keys(files).length!==4} onClick={check}>{busy?'Обработка…':'Проверить файлы'}</button>
 {preview&&<div className="import-preview"><h3>Готово к загрузке</h3><p>Профилей: {preview.counts.employees} · Событий: {preview.counts.events} · Навыков: {preview.counts.skills} · Записей истории: {preview.counts.history}</p>{preview.warnings.map((w:string)=><p key={w} className="warning">{w}</p>)}<p><b>Импорт полностью заменит текущий датасет и накопленный прогресс.</b> Повреждённые файлы не изменяют данные.</p><button disabled={busy} onClick={apply}>Заменить датасет</button></div>}
 {error&&<pre className="inline-error" role="alert">{error}</pre>}{notice&&<p className="success" role="status">{notice}</p>}</section>
 <footer>Доступ HR · Синтетические данные · Версия датасета {summary?.revision}</footer></main>;
}
