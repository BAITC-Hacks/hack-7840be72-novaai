import {tr,setLocale,Locale} from './i18n';
import React, { useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import HrDashboard from './HrDashboard';
import { SharedView } from './Sharing';
import EmployeeWorkspace from './EmployeeWorkspace';
function App() {
 const [language,setLanguage]=useState<Locale>(()=>{const saved=localStorage.getItem('cq-language');return saved==='kk'||saved==='en'?saved:'ru';});
 setLocale(language);
    const cardId = new URLSearchParams(window.location.search).get("card");
    const authEpoch=useRef(0);
    const [role, setRole] = useState('');
    const [token, setToken] = useState('');
    const [input, setInput] = useState('');
    const [profile, setProfile] = useState<any>(null);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const [style, setStyle] = useState(localStorage.getItem('cq-style') || 'anime');
    async function api(path: string, method = 'GET', body?: any) {
        const r = await fetch('/api/' + path, { method, headers: { Authorization: 'Bearer ' + token, ...(body ? { 'Content-Type': 'application/json' } : {}) }, body: body ? JSON.stringify(body) : undefined });
        if (!r.ok) {
            let message = 'Не удалось выполнить запрос.';
            try {
                const data = await r.json();
                message = Array.isArray(data.detail) ? data.detail.map((e: any) => (e.path || e.loc?.join('.') || '') + ': ' + (e.message || e.msg)).join('\n') : data.detail || message;
            }
            catch { }
            throw new Error(message);
        }
        return r.json();
    }
    async function refresh() { const epoch=authEpoch.current; setBusy(true); setError(''); try {
        const session = await api('session');
        if(epoch!==authEpoch.current)return;
        setRole(session.role);
        if (session.role === 'employee' && !cardId) {
            const p = await api('me');
            const r = await api('recommendations');
            if (p.revision !== r.revision)
                throw new Error('Данные изменились. Обновите профиль.');
            if(epoch!==authEpoch.current)return;
            setProfile(p);
            setResult(r);
        }
    }
    catch (e: any) {
        if(epoch===authEpoch.current)setError(e.message);
    }
    finally {
        if(epoch===authEpoch.current)setBusy(false);
    } }
    useEffect(() => { if (token)
        refresh(); }, [token]);
    async function finish(id: string) { const epoch=authEpoch.current; setBusy(true); setError(''); try {
        await api('activities/' + id + '/complete', 'POST', { expected_revision: profile.revision });
        if(epoch===authEpoch.current)await refresh();
    }
    catch (e: any) {
        if(epoch===authEpoch.current){setError(e.message);setBusy(false);}
    } }
    function logout() { authEpoch.current++; setBusy(false); setToken(''); setRole(''); setProfile(null); setResult(null); setInput(''); setError(''); }
    function theme(value: string) { setStyle(value); localStorage.setItem('cq-style', value); }
    return <div className={profile && !cardId ? "app-shell" : "shell"}><div className="language-switch"><label><span>Қазақша / Русский / English</span><select aria-label="Language / Тіл / Язык" value={language} onChange={e=>setLanguage(e.target.value as Locale)}><option value="kk">Қазақша</option><option value="ru">Русский</option><option value="en">English</option></select></label></div><header className={profile && !cardId ? "legacy-header" : ""}><a href="/" className="brand">{tr("CQ")}<span>{tr("CAREER QUEST")}</span></a><span className="private">{tr("Личное пространство · NovaAI")}</span></header>
 {tr(role === 'employee' && cardId ? <SharedView id={cardId} request={api} logout={logout}/> : (role === 'hr' || role === 'manager') ? <HrDashboard request={api} logout={logout} role={role}/> : !profile ? <main className="login"><p className="eyebrow">{tr("ТВОЯ СЛЕДУЮЩАЯ ГЛАВА")}</p><h1>{tr("Расти в профессии.")}<br />{tr("Развивай своего героя.")}</h1><p>{tr("Осмысленные шаги к следующему грейду.")}</p><form onSubmit={e => { e.preventDefault(); if (token === input)
        refresh();
    else
        setToken(input); }}><label>{tr("Токен доступа (сотрудник, HR или руководитель)")}<input type="password" required value={input} onChange={e => setInput(e.target.value)}/></label><button disabled={busy}>{tr("Войти →")}</button></form></main> : <EmployeeWorkspace profile={profile} result={result} style={style} theme={theme} api={api} finish={finish} busy={busy} logout={logout}/>)}

 {tr(error && <div className="error" role="alert">{tr(error)}<button onClick={refresh}>{tr("Повторить")}</button></div>)}</div>;
}
createRoot(document.getElementById('root')!).render(<App />);
