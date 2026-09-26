import { useEffect, useRef, useState } from 'react'

type Feedback = { id: string; category: string; message: string; created_at: string; read_at: string | null; context?: unknown; attachments?: { id: string }[] }
type Overview = { collection_started_at: string; cards: Record<string, number>; daily: { day: string; visits: number; analyses: number }[]; projects: { id: string; name: string; runs: number; latest_activity: string }[]; funnel: { visited: number; created_project: number; succeeded: number }; wizard: Record<string, number> }
const categories: Record<string, string> = { problem: 'Проблема', idea: 'Идея', praise: 'Понравилось', other: 'Другое' }
const labels: Record<string, string> = { visits:'Визиты', visitors:'Посетители', projects:'Создано проектов', launched:'Запущено анализов', succeeded:'Успешных анализов', failed:'Ошибок анализа', feedback:'Отзывы', unread:'Непрочитанные' }

export default function Admin() {
  const [csrf, setCsrf] = useState<string | null>(null)
  const [checking, setChecking] = useState(true)
  const [sessionUnavailable, setSessionUnavailable] = useState(false)
  const [sessionAttempt, setSessionAttempt] = useState(0)
  const [tab, setTab] = useState('overview')
  const [period, setPeriod] = useState('30')
  const [category, setCategory] = useState('')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [feedback, setFeedback] = useState<Feedback[]>([])
  const [nextOffset, setNextOffset] = useState<number | null>(null)
  const [detail, setDetail] = useState<Feedback | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const scope = `${csrf}|${tab}|${period}|${category}|${attempt}`
  const currentScope = useRef(scope)
  const reads = useRef(new AbortController())
  if (currentScope.current !== scope) { reads.current.abort(); reads.current = new AbortController(); currentScope.current = scope }
  async function api(path: string, method = 'GET', body?: object, signal?: AbortSignal) {
    signal = signal ? AbortSignal.any([signal, AbortSignal.timeout(10000)]) : AbortSignal.timeout(10000)
    const response = await fetch(`/api/admin/${path}`, { method, signal, headers: { 'Content-Type':'application/json', ...(csrf ? { 'X-CSRF-Token':csrf } : {}) }, ...(body ? { body:JSON.stringify(body) } : {}) })
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    if (!response.ok) {
      if (response.status === 401) { setCsrf(null); setOverview(null); setFeedback([]); setDetail(null) }
      throw Object.assign(new Error(response.status === 429 ? 'Слишком много попыток. Повторите позже.' : response.status === 401 ? 'Войдите снова или проверьте пароль.' : 'Не удалось выполнить запрос. Повторите попытку.'), { status: response.status })
    }
    const data = await response.json()
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    return data
  }
  useEffect(() => {
    const controller = new AbortController()
    setChecking(true); setSessionUnavailable(false)
    void api('session', 'GET', undefined, controller.signal).then(data => { if (!controller.signal.aborted) setCsrf(data.csrf) }).catch(error => {
      if (!controller.signal.aborted && error.status !== 401) { setSessionUnavailable(true); setError('Не удалось проверить сессию. Проверьте соединение и защищённый адрес сервера.') }
    }).finally(() => { if (!controller.signal.aborted) setChecking(false) })
    return () => controller.abort()
  }, [sessionAttempt])
  useEffect(() => {
    if (!csrf) return
    if (reads.current.signal.aborted) reads.current = new AbortController()
    const controller = reads.current
    setBusy(false); setError(''); setOverview(null); setFeedback([]); setDetail(null); setNextOffset(null)
    void api(tab === 'overview' ? `overview?period=${period}` : `feedback${category ? `?category=${category}` : ''}`, 'GET', undefined, controller.signal).then(data => {
      if (controller.signal.aborted) return
      if (tab === 'overview') setOverview(data)
      else { setFeedback(data.feedback); setNextOffset(data.next_offset) }
    }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [csrf, tab, period, category, attempt])
  async function mutate(action: () => Promise<void>) {
    const generation = currentScope.current
    setBusy(true); setError('')
    try { await action() } catch (error) { if (generation === currentScope.current) setError((error as Error).message) } finally { if (generation === currentScope.current) setBusy(false) }
  }
  const date = (value: string) => new Date(value).toLocaleString('ru-RU', { timeZone:'Europe/Moscow' })
  return <main className="admin-page"><header className="admin-heading"><div><img src="/team-logo.png" alt="17 мгновений ИИ" /><h1>Администрирование</h1></div>{csrf && <button type="button" className="secondary" disabled={busy} onClick={() => void mutate(async () => { await api('logout', 'POST'); setCsrf(null); setOverview(null); setFeedback([]); setDetail(null) })}>Выйти</button>}</header>
    {error && <p className="error" role="alert">{error} {csrf && <button type="button" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку</button>}</p>}
    {checking ? <p>Проверяем сессию…</p> : sessionUnavailable ? <button type="button" className="secondary" onClick={() => { setError(''); setSessionAttempt(value => value + 1) }}>Повторить проверку сессии</button> : !csrf ? <form className="panel admin-login" onSubmit={event => { event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); void mutate(async () => { const result = await api('login', 'POST', { login:data.get('login'), password:data.get('password') }); form.reset(); setCsrf(result.csrf) }) }}><h2>Вход владельца</h2><label className="field">Логин<input name="login" autoComplete="username" defaultValue="gorshenin-nik" required /></label><label className="field">Пароль<input name="password" type="password" autoComplete="current-password" maxLength={1024} required /></label><button className="primary" disabled={busy}>Войти</button></form> : <>
      <nav className="admin-tabs" aria-label="Разделы администрирования"><button aria-pressed={tab === 'overview'} onClick={() => setTab('overview')}>Обзор</button><button aria-pressed={tab === 'feedback'} onClick={() => setTab('feedback')}>Обратная связь</button></nav>
      {tab === 'overview' ? <section><label className="field">Период<select aria-label="Период" value={period} onChange={event => setPeriod(event.target.value)}><option value="7">7 дней</option><option value="30">30 дней</option><option value="all">Всё время</option></select></label><p>Дни по московскому времени. Посетители — браузеры, а не установленные личности. Визит начинается после 30 минут бездействия.</p>{overview ? <>
        <div className="admin-cards">{Object.entries(labels).map(([key,label]) => <div className="panel" key={key}><span>{label}</span><strong>{overview.cards[key]}</strong></div>)}</div>
        <p>Сбор посещений начат {date(overview.collection_started_at)}. Исторические обычные анализы включены в итог за всё время; без известной даты: {overview.cards.unknown_dates}. Они не приписываются новым посетителям. Успехи и ошибки относятся к запускам выбранного периода.</p>
        <h2>По дням</h2><div className="daily-charts">{(['visits','analyses'] as const).map(kind => <figure key={kind}><figcaption>{kind === 'visits' ? 'Визиты' : 'Анализы'}</figcaption>{overview.daily.length ? <div className="daily-bars">{overview.daily.map(day => <div className="daily-bar" key={day.day}><span>{day.day}</span><meter aria-label={`${day.day}: ${kind === 'visits' ? 'визиты' : 'анализы'}`} min={0} max={Math.max(1,...overview.daily.map(row => row[kind]))} value={day[kind]} /><strong>{day[kind]}</strong></div>)}</div> : <p>Данных пока нет.</p>}</figure>)}</div>
        <h2>Первое использование</h2><p>Браузеры с первым визитом в выбранном периоде; последующие шаги учитываются по серверным данным.</p><ol className="funnel"><li>Первый визит: <strong>{overview.funnel.visited}</strong></li><li>Создание проекта: <strong>{overview.funnel.created_project}</strong></li><li>Первый успешный анализ: <strong>{overview.funnel.succeeded}</strong></li></ol>
        <p>Знакомство: начато {overview.wizard.wizard_started ?? 0}, завершено {overview.wizard.wizard_completed ?? 0}, пропущено {overview.wizard.wizard_skipped ?? 0}.</p>
        <h2>Все проекты</h2><div className="admin-projects">{overview.projects.map(project => <article key={project.id}><h3>{project.name}</h3><p>Анализов: {project.runs} · Последняя активность: {date(project.latest_activity)}</p></article>)}{!overview.projects.length && <p>Проектов пока нет.</p>}</div>
      </> : !error && <p>Загружаем статистику…</p>}</section> : <section><label className="field">Категория<select aria-label="Категория" value={category} onChange={event => setCategory(event.target.value)}><option value="">Все категории</option>{Object.entries(categories).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label><div className="admin-feedback"><div>{feedback.map(item => <button className="feedback-row" key={item.id} disabled={busy} onClick={() => void mutate(async () => { const controller = reads.current; const data = await api(`feedback/${item.id}/open`, 'POST', undefined, controller.signal); if (controller.signal.aborted) return; setDetail(data); setFeedback(current => current.map(row => row.id === item.id ? { ...row, read_at:data.read_at } : row)) })}><strong>{categories[item.category]}{!item.read_at ? ' · Новый' : ''}</strong><time>{date(item.created_at)}</time><span>{item.message}</span></button>)}{!feedback.length && <p>Отзывов пока нет.</p>}{nextOffset !== null && <button disabled={busy} onClick={() => void mutate(async () => { const controller = reads.current; const data = await api(`feedback?offset=${nextOffset}${category ? `&category=${category}` : ''}`, 'GET', undefined, controller.signal); if (controller.signal.aborted) return; setFeedback(current => [...current,...data.feedback]); setNextOffset(data.next_offset) })}>Показать ещё</button>}</div>{detail && <article className="panel feedback-detail"><h2>{categories[detail.category]}</h2><time>{date(detail.created_at)}</time><p>{detail.message}</p><h3>Контекст</h3><dl>{Object.entries(detail.context && typeof detail.context === 'object' && !Array.isArray(detail.context) ? detail.context : {}).map(([key,value]) => <div key={key}><dt>{({ pathname:'Страница',project_id:'Проект',analysis_id:'Анализ' } as Record<string,string>)[key]}</dt><dd>{typeof value === 'string' ? value : 'Некорректный сохранённый контекст'}</dd></div>)}</dl><div className="feedback-previews">{detail.attachments?.map((image,index) => <a key={image.id} href={`/api/admin/attachments/${image.id}`} target="_blank" rel="noreferrer"><img src={`/api/admin/attachments/${image.id}`} alt={`Изображение ${index + 1} к отзыву`} /></a>)}</div></article>}</div></section>}
      <details className="panel admin-password"><summary>Сменить пароль</summary><p>Не менее 8 символов. После изменения все сессии завершатся.</p><form onSubmit={event => { event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); if (data.get('new_password') !== data.get('confirm_password')) { setError('Новые пароли не совпадают.'); return }; void mutate(async () => { await api('password','POST',{ current_password:data.get('current_password'),new_password:data.get('new_password') }); form.reset(); setCsrf(null); setOverview(null); setFeedback([]); setDetail(null) }) }}><label className="field">Текущий пароль<input name="current_password" type="password" autoComplete="current-password" maxLength={1024} required /></label><label className="field">Новый пароль<input name="new_password" type="password" autoComplete="new-password" minLength={8} maxLength={1024} required /></label><label className="field">Повторите новый пароль<input name="confirm_password" type="password" autoComplete="new-password" minLength={8} maxLength={1024} required /></label><button className="primary" disabled={busy}>Сохранить пароль</button></form></details>
    </>}
  </main>
}
