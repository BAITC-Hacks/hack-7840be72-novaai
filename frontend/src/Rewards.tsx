import React, {useEffect, useRef, useState} from 'react';
import {tr} from './i18n';
const categories=[['all','Все награды'],['work','Для работы'],['self','Для себя'],['family','Для семьи и детей']];
export default function Rewards({request,revision}:any){
 const [wallet,setWallet]=useState<any>(null),[category,setCategory]=useState('all');
 const [selected,setSelected]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const epoch=useRef(0);
 useEffect(()=>{const version=++epoch.current;request('store').then((w:any)=>{if(version===epoch.current)setWallet(w);}).catch((e:any)=>{if(version===epoch.current)setError(e.message);});return()=>{epoch.current++;};},[revision]);
 async function redeem(){
  if(busy||!selected)return;
  const version=epoch.current;setBusy(true);setError('');
  try{const result=await request('store/redeem','POST',{item_id:selected.item.id,request_id:selected.key,expected_epoch:wallet.epoch});
   if(version===epoch.current){setWallet(result.wallet);setSelected(null);setNotice('Демо-обмен завершён. Настоящий сертификат не выдаётся.');}
  }catch(e:any){if(version===epoch.current)setError(e.message);}
  finally{if(version===epoch.current)setBusy(false);}
 }
 async function reload(){setError('');setSelected(null);const version=epoch.current;try{const w=await request('store');if(version===epoch.current)setWallet(w);}catch(e:any){if(version===epoch.current)setError(e.message);}}
 return <section className="rewards"><div className="store-banner"><div><p className="eyebrow">{tr('ТВОЙ РОСТ — ТВОИ ВОЗМОЖНОСТИ')}</p><h2>{tr('Профессиональный рост. Радость для близких.')}</h2><p>{tr('Закрывай разрывы в навыках и выбирай личные награды.')}</p></div><div className="coin-balance"><span>◈</span><strong>{wallet?.balance??'—'}</strong><span>Halyk Coins</span></div></div>
 <p className="warning">{tr('Демо-магазин: цены и награды условные. Реальные бонусы банк ещё не согласовал.')}</p>
 <p className="hint">{tr('100 Coins за каждый закрытый уровень разрыва в добровольной активности. Обязательное обучение не приносит Coins. В деморежиме завершение имитируется.')}</p>
 {notice&&<p role="status" className="panel">{tr(notice)}</p>}
 {error&&<div role="alert" className="inline-error">{tr(error)} <button className="secondary" onClick={reload} disabled={busy}>{tr('Обновить магазин')}</button></div>}
 {!wallet&&!error&&<p role="status">{tr('Загрузка…')}</p>}
 {wallet&&<><div className="reward-tabs" aria-label={tr('Категории наград')}>{categories.map(([id,label])=><button className="secondary" aria-pressed={category===id} key={id} onClick={()=>setCategory(id)}>{tr(label)}</button>)}</div>
 {selected&&<section className="panel reward-confirm" aria-label={tr('Подтверждение обмена')}><h3>{tr(selected.item.title)}</h3><p>{tr('Будет списано:')} {selected.item.cost} Halyk Coins</p><p>{tr('Останется:')} {wallet.balance-selected.item.cost} Halyk Coins</p><button disabled={busy} onClick={redeem}>{tr(busy?'Обработка…':'Подтвердить демо-обмен')}</button> <button className="secondary" disabled={busy} onClick={()=>{setSelected(null);setError('');}}>{tr('Отмена')}</button></section>}
 <div className="reward-grid">{wallet.catalog.filter((item:any)=>category==='all'||item.category===category).map((item:any)=><article className="panel reward-card" key={item.id}><div className={'reward-art '+item.category} aria-hidden="true">{item.icon}</div><small>{tr(categories.find(c=>c[0]===item.category)?.[1])}</small><h3>{tr(item.title)}</h3><strong>{item.cost} <small>Halyk Coins</small></strong><button disabled={busy||!!selected||!wallet.redemption_enabled||wallet.balance<item.cost} onClick={()=>{setSelected({item,key:crypto.randomUUID()});setNotice('');setError('');}}>{tr(!wallet.redemption_enabled?'Демо-обмен отключён':wallet.balance<item.cost?'Недостаточно Coins':'Выбрать награду')}</button></article>)}</div>
 <section className="panel"><h2>{tr('История Coins')}</h2><p className="hint">{tr('Последние 100 операций. Начальный баланс — 0; импортированная история не начисляет Coins.')}</p>{!wallet.history.length?<p>{tr('Пока нет операций. Начни с добровольного шага в своей траектории.')}</p>:wallet.history.map((row:any)=><div className="coin-row" key={row.id}><span>{row.amount>0?tr('Развитие навыка'):tr('Демо-обмен')}<small>{row.event_id||tr(wallet.catalog.find((item:any)=>item.id===row.item_id)?.title)} · {row.created} UTC</small></span><b>{row.amount>0?'+':''}{row.amount}</b></div>)}</section></>}
 </section>;
}
