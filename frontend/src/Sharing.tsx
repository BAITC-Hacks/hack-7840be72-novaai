import {tr} from './i18n';
import React, { useEffect, useState } from 'react';
export function SharedCard({ card }: any) { return <article className={'hero shared-card ' + card.style}><div className="card-top"><span>{tr("ЛИЧНЫЕ ДОСТИЖЕНИЯ")}</span></div><div className="avatar">{tr(card.style === 'anime' ? '✦' : '⚽')}</div><h2>{tr(card.alias)}</h2>{tr(card.achievements.length ? <ul>{tr(card.achievements.map((title: string, i: number) => <li key={i}>{tr(title)}</li>))}</ul> : <p>{tr("Мой образ в Career Quest")}</p>)}{tr(card.demo && <small>{tr("Демонстрационная карточка · результаты не подтверждены LMS")}</small>)}</article>; }
export function SharedView({ id, request, logout }: any) { const [card, setCard] = useState<any>(null); const [error, setError] = useState(''); useEffect(() => { let active = true; async function load() { try {
    const value = await request('shared/' + encodeURIComponent(id));
    if (active) {
        setCard(value);
        setError('');
    }
}
catch (e: any) {
    if (active) {
        setCard(null);
        setError(e.message);
    }
} } load(); const timer = setInterval(load, 10000); return () => { active = false; clearInterval(timer); }; }, [id]); return <main className="login"><h1>{tr("Карточка коллеги")}</h1>{tr(card && <SharedCard card={card}/>)}<p role="status">{tr(error)}</p><p className="hint">{tr("Доступ проверяется при открытии и каждые 10 секунд.")}</p><button onClick={logout}>{tr("Выйти")}</button></main>; }
export default function Sharing({ request, style, revision }: any) {
    const [options, setOptions] = useState<any>(null), [shares, setShares] = useState<any[]>([]);
    const [alias, setAlias] = useState('Мой герой'), [recipients, setRecipients] = useState(''), [selected, setSelected] = useState<string[]>([]);
    const [preview, setPreview] = useState<any>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
    async function load() { const [o, s] = await Promise.all([request('sharing/options'), request('sharing')]); setOptions(o); setShares(s.shares); }
    useEffect(() => { setPreview(null); setSelected([]); load().catch(e => setError(e.message)); }, [revision]);
    useEffect(() => { setPreview(null); }, [style]);
    function payload() { return { alias, style, achievement_ids: selected, recipients: recipients.split(',').map(s => s.trim()).filter(Boolean), expected_revision: options.revision }; }
    async function check() { setBusy(true); setError(''); setPreview(null); try {
        const value = payload();
        const response = await request('sharing/preview', 'POST', value);
        setPreview({ ...response, payload: value });
    }
    catch (e: any) {
        setError(e.message);
    }
    finally {
        setBusy(false);
    } }
    async function save() { setBusy(true); setError(''); try {
        await request('sharing', 'POST', preview.payload);
        setPreview(null);
        await load();
    }
    catch (e: any) {
        setError(e.message);
    }
    finally {
        setBusy(false);
    } }
    async function revoke(id: string) { setBusy(true); setError(''); try {
        await request('sharing/' + id, 'DELETE');
        await load();
    }
    catch (e: any) {
        setError(e.message);
    }
    finally {
        setBusy(false);
    } }
    return <section className="panel sharing"><p className="eyebrow">{tr("ТОЛЬКО ПО ТВОЕМУ ВЫБОРУ")}</p><h2>{tr("Поделиться карточкой")}</h2><p>{tr("Покажи образ и выбранные достижения конкретным коллегам. Навыки, оценки, пропуски, грейд и баланс останутся приватными.")}</p>
 <label>{tr("Псевдоним")}<input maxLength={40} value={alias} disabled={busy} onChange={e => { setAlias(e.target.value); setPreview(null); }}/></label>
 <label>{tr("ID получателей через запятую")}<input placeholder={tr("Например, E0029")} value={recipients} disabled={busy} onChange={e => { setRecipients(e.target.value); setPreview(null); }}/></label>
 <fieldset disabled={busy}><legend>{tr("Какие достижения показать")}</legend>{tr(options?.achievements.map((a: any) => <label className="check" key={a.id}><input type="checkbox" checked={selected.includes(a.id)} onChange={e => { setSelected(e.target.checked ? [...selected, a.id] : selected.filter(id => id !== a.id)); setPreview(null); }}/>{tr(a.title)}</label>))}{tr(options?.achievements.length === 0 && <p className="hint">{tr("Завершённых добровольных активностей пока нет. Можно поделиться только образом.")}</p>)}</fieldset>
 <button disabled={busy || !options || !alias.trim() || !recipients.trim()} onClick={check}>{tr("Предпросмотр")}</button>
 {tr(preview && <div className="import-preview"><h3>{tr("Коллеги увидят только это")}</h3><SharedCard card={preview.card}/><p>{tr("Получатели: ")}{tr(preview.recipients.join(', '))}</p><p className="hint">{tr("Новые достижения не добавятся автоматически. Вы сможете отозвать доступ. За показ карточки баллы не начисляются.")}</p><button disabled={busy} onClick={save}>{tr("Разрешить показ выбранным коллегам")}</button></div>)}
 {tr(!!shares.length && <div className="import-preview"><h3>{tr("Открытый доступ")}</h3>{tr(shares.map(s => <div className="share-item" key={s.id}><p>{tr("Для: ")}{tr(s.recipients.join(', '))}</p><a href={'/?card=' + s.id}>{tr("Открыть карточку")}</a><p className="hint">{tr("Ссылка работает только для выбранных аккаунтов. Можно скопировать адрес ссылки.")}</p><button disabled={busy} className="secondary" onClick={() => revoke(s.id)}>{tr("Отозвать доступ")}</button></div>))}</div>)}
 {tr(error && <p className="inline-error" role="alert">{tr(error)}</p>)}</section>;
}
