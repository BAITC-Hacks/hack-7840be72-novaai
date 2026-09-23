import {tr} from './i18n';
import React, { useEffect, useState } from 'react';
const names = ['employees.json', 'events.json', 'skills.json', 'activity_history.csv'];
export default function HrDashboard({ request, logout, role }: any) {
    const [onlyStagnation, setOnlyStagnation] = useState(false);
    const [proposal, setProposal] = useState<any>(null);
    const [people, setPeople] = useState<any[]>([]);
    const [onlyMissing, setOnlyMissing] = useState(false);
    const [summary, setSummary] = useState<any>(null);
    const [files, setFiles] = useState<Record<string, string>>({});
    const [preview, setPreview] = useState<any>(null);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [busy, setBusy] = useState(false);
    async function support(id: string) { setBusy(true); setError(''); setProposal(null); try {
        setProposal(await request('hr/employees/' + encodeURIComponent(id) + '/support-proposal', 'POST'));
    }
    catch (e: any) {
        setError(e.message);
    }
    finally {
        setBusy(false);
    } }
    async function load() { const [s, p] = await Promise.all([request('hr/summary'), request('hr/employees')]); if (s.revision !== p.revision)
        throw new Error('Данные обновились. Повторите загрузку.'); setSummary(s); setPeople(p.employees); setProposal(null); }
    useEffect(() => { load().catch(e => setError(e.message)); }, []);
    async function select(list: FileList | null) {
        setPreview(null);
        setError('');
        setNotice('');
        setFiles({});
        if (!list)
            return;
        const selected = Array.from(list);
        if (selected.length !== 4 || names.some(n => !selected.some(f => f.name === n))) {
            setError('Выберите ровно четыре файла: ' + names.join(', '));
            return;
        }
        if (selected.reduce((sum, f) => sum + f.size, 0) > 12 * 1024 * 1024) {
            setError('Суммарный размер файлов не должен превышать 12 MiB.');
            return;
        }
        setBusy(true);
        try {
            const pairs = await Promise.all(selected.map(async (f) => [f.name, await f.text()]));
            setFiles(Object.fromEntries(pairs));
        }
        catch {
            setError('Не удалось прочитать файлы.');
        }
        finally {
            setBusy(false);
        }
    }
    async function check() { setBusy(true); setError(''); setNotice(''); setPreview(null); try {
        setPreview(await request('hr/import/preview', 'POST', { files }));
    }
    catch (e: any) {
        setError(e.message);
    }
    finally {
        setBusy(false);
    } }
    async function apply() { setBusy(true); setError(''); try {
        await request('hr/import', 'POST', { files, digest: preview.digest, expected_revision: preview.revision });
        setPreview(null);
        setFiles({});
        setNotice('Датасет загружен. Аналитика пересчитана.');
        await load();
    }
    catch (e: any) {
        setError(e.message);
        setPreview(null);
    }
    finally {
        setBusy(false);
    } }
    return <main><section className="intro"><div><p className="eyebrow">{tr("КОМАНДА В РАЗВИТИИ")}</p><h1>{tr("Картина компетенций")}</h1><p>{tr(role === 'manager' ? 'Служебные данные и аналитика только вашей команды.' : 'Служебные данные сотрудников и общая аналитика.')}</p></div><button className="secondary" onClick={logout}>{tr("Выйти")}</button></section>
 {tr(summary && <><div className="metrics"><article className="panel"><span>{tr("Сотрудников")}</span><strong>{tr(summary.employee_count)}</strong></article><article className="panel"><span>{tr("Без следующего шага")}</span><strong>{tr(summary.without_recommendations)}</strong></article><article className="panel"><span>{tr("Завершено активностей")}</span><strong>{tr(summary.participation.completed)}</strong></article></div>
 <div className="hr-grid"><section className="panel"><h2>{tr("Дефициты навыков")}</h2><p className="hint">{tr("Количество профилей с разрывом до следующего грейда.")}</p>{tr(Object.entries(summary.skill_deficits).sort((a: any, b: any) => b[1] - a[1]).map(([skill, count]: any) => <div className="skill" key={skill}><div><span>{tr(skill.replace('SK_', '').replaceAll('_', ' '))}</span><b>{tr(count)}</b></div><progress value={count} max={summary.employee_count}/></div>))}{tr(Object.keys(summary.skill_deficits).length === 0 && <p>{tr("Дефицитов не найдено.")}</p>)}</section>
 <section className="panel"><h2>{tr("Участие в активностях")}</h2>{tr(Object.entries(summary.participation).map(([key, value]: any) => <p key={key}>{tr(({ completed: 'Завершено', skipped: 'Пропущено', declined: 'Отклонено' } as any)[key])}{tr(": ")}<b>{tr(value)}</b></p>))}<p className="hint">{tr("Пропуск сам по себе не свидетельствует о риске увольнения.")}</p></section></div></>)}
 <section className="panel insight-panel"><p className="eyebrow">{tr("ИНСАЙТЫ ДЛЯ ПОДДЕРЖКИ")}</p><h2>{tr("Кому помочь со следующим шагом")}</h2><p><b>{tr(people.filter(p => p.stagnation?.flagged).length)}</b>{tr(" — сотрудников с наблюдаемыми признаками стагнации.")}</p><p className="hint">{tr("Правила по истории, не прогноз увольнения. Отсутствие записей не доказывает отсутствие обучения. Пропуски рекомендаций учитываются только при наличии явной отметки в данных.")}</p><label className="check"><input type="checkbox" checked={onlyStagnation} onChange={e => setOnlyStagnation(e.target.checked)}/>{tr("Сотрудники в зоне стагнации")}</label></section>
 {tr(proposal && <section className="panel proposal" aria-live="polite"><p className="eyebrow">{tr("ПЕРСОНАЛЬНОЕ ПРЕДЛОЖЕНИЕ")}</p><h2>{tr(proposal.employee_id)}{tr(" → ")}{tr(proposal.target_grade)}</h2><p>{tr("Черновик по правилам. Ничего не отправлено сотруднику.")}</p><p>{tr("Предложите обсудить карьерную цель и удобный формат обучения, затем выбрать один из подходящих шагов.")}</p>{tr(proposal.activities.length ? <ul>{tr(proposal.activities.map((a: any) => <li key={a.id}>{tr(a.title)}{tr(" · ")}{tr(a.format)}</li>))}</ul> : <p>{tr("Подходящих активностей нет. Уточните цель и дополните каталог.")}</p>)}<h3>{tr("Запрос на ментора")}</h3><p>{tr(proposal.mentor_request.focus_skills.join(', ') || 'Уточнить область развития')}</p><p className="hint">{tr("Каталог менторов пока не подключён. Конкретный ментор не назначен.")}</p><button className="secondary" onClick={() => setProposal(null)}>{tr("Закрыть предложение")}</button></section>)}
 <section className="panel"><p className="eyebrow">{tr("СЛУЖЕБНЫЙ ДОСТУП")}</p><h2>{tr(role === 'manager' ? 'Моя команда' : 'Сотрудники')}</h2><p className="hint">{tr("Профиль, наличие следующего шага и обязательное обучение. Личные навыки и добровольная история скрыты.")}</p><label className="check"><input type="checkbox" checked={onlyMissing} onChange={e => setOnlyMissing(e.target.checked)}/>{tr("Только без рекомендованного шага")}</label>
 <div className="table-scroll"><table><thead><tr><th>{tr("ID / Роль")}</th><th>{tr("Грейд")}</th><th>{tr("Следующий шаг")}</th><th>{tr("Обязательное обучение")}</th><th>{tr("Поддержка развития")}</th></tr></thead><tbody>{tr(people.filter(p => (!onlyMissing || p.recommendation_state !== 'available') && (!onlyStagnation || p.stagnation?.flagged)).map(p => <tr key={p.employee_id}><td><b>{tr(p.employee_id)}</b><br />{tr(p.role)}</td><td>{tr(p.grade)}</td><td>{tr(({ available: 'Есть рекомендация', requirements_met: 'Требования по навыкам выполнены', catalog_gap: 'Нужно дополнить каталог активностей' } as any)[p.recommendation_state])}</td><td>{tr(p.mandatory_training.length === 0 ? 'Нет назначений' : p.mandatory_training.map((t: any) => <div className="training" key={t.event_id}><b>{tr(t.title)}</b><br />{tr(({ completed: 'Завершено', pending: 'Ожидает прохождения', overdue: 'Срок прошёл' } as any)[t.status])}{tr(" · ")}{tr(t.due_date || 'Без срока')}</div>))}</td><td>{tr(p.stagnation?.reasons.map((reason: string) => <p key={reason} className="risk-reason">{tr(reason === 'no_completion_six_months' ? 'Нет завершений более 6 месяцев' : 'Пропущены 3+ рекомендации подряд')}</p>))}{tr(p.stagnation?.insufficient_history && <p className="hint">{tr("Недостаточно истории для вывода.")}</p>)}<button disabled={busy} onClick={() => support(p.employee_id)}>{tr("Сформировать предложение")}</button></td></tr>))}</tbody></table></div>{tr(people.filter(p => (!onlyMissing || p.recommendation_state !== 'available') && (!onlyStagnation || p.stagnation?.flagged)).length === 0 && <p>{tr("Нет сотрудников по выбранному фильтру.")}</p>)}</section>
 {tr(role === 'hr' && <section className="panel import"><p className="eyebrow">{tr("ПРОВЕРКА ДАТАСЕТА")}</p><h2>{tr("Загрузить JSON / CSV")}</h2><p>{tr("Выберите четыре файла по схеме README. Сначала проверим формат, затем покажем состав загрузки.")}</p><label htmlFor="dataset">{tr("Файлы датасета")}<input id="dataset" type="file" accept=".json,.csv" multiple disabled={busy} onChange={e => select(e.target.files)}/></label><p className="hint">{tr(names.join(' · '))}</p><button disabled={busy || Object.keys(files).length !== 4} onClick={check}>{tr(busy ? 'Обработка…' : 'Проверить файлы')}</button>
 {tr(preview && <div className="import-preview"><h3>{tr("Готово к загрузке")}</h3><p>{tr("Профилей: ")}{tr(preview.counts.employees)}{tr(" · Событий: ")}{tr(preview.counts.events)}{tr(" · Навыков: ")}{tr(preview.counts.skills)}{tr(" · Записей истории: ")}{tr(preview.counts.history)}</p>{tr(preview.warnings.map((w: string) => <p key={w} className="warning">{tr(w)}</p>))}<p><b>{tr("Импорт полностью заменит текущий датасет и накопленный прогресс.")}</b>{tr(" Повреждённые файлы не изменяют данные.")}</p><button disabled={busy} onClick={apply}>{tr("Заменить датасет")}</button></div>)}
 {tr(notice && <p className="success" role="status">{tr(notice)}</p>)}</section>)}{tr(error && <div className="inline-error" role="alert"><pre>{tr(error)}</pre><button onClick={() => load().then(() => setError('')).catch(e => setError(e.message))}>{tr("Повторить загрузку")}</button></div>)}
 <footer>{tr(role === 'manager' ? 'Доступ руководителя' : 'Доступ HR')}{tr(" · Синтетические данные · Версия датасета ")}{tr(summary?.revision)}</footer></main>;
}
