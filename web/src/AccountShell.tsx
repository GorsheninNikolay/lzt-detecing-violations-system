import TeamLogo from './TeamLogo'
import { useEffect, useState, useRef, type ReactNode, type FormEvent } from 'react'
import { Theme } from '@radix-ui/themes'
import { randomUUID } from './randomUUID'
import './account.css'
import { AccountIdentity } from './AccountIdentity'
import PasswordField from './PasswordField'
import AssistantChat from './AssistantChat'
import { TutorialProvider, TutorialStart, TutorialPage } from './Tutorial'

export type User = { id: string; email: string; name: string; theme: 'light' | 'dark' | 'system'; verified: boolean }
const ACCOUNT_ERRORS: Record<string,string> = {
  owner_immutable: 'Права владельца нельзя изменить.', deletion_active_work: 'Дождитесь завершения обработки перед удалением.', deletion_publishing_submission: 'Дождитесь завершения отправки перед удалением.', run_not_found: 'Анализ не найден.',
  invalid_credentials: 'Неверная почта или пароль.', email_unavailable: 'Этот адрес почты недоступен для регистрации.', email_already_registered: 'Аккаунт с этой почтой уже существует.',
  insufficient_project_role: 'Для этого действия нужны права владельца или редактора.', project_read_only: 'У вас доступ только для просмотра.', owner_required: 'Это действие доступно владельцу проекта.',
  invalid_origin: 'Не удалось проверить источник запроса. Обновите страницу и повторите.', authentication_required: 'Войдите в аккаунт.', invalid_theme: 'Выберите доступную тему.',
  recipient_not_registered: 'Получатель должен сначала зарегистрироваться.', invitation_unavailable: 'Приглашение недоступно, отозвано или срок его действия истёк.', invitation_not_found: 'Приглашение недоступно.',
  rate_limited: 'Слишком много попыток. Повторите позже.', password_too_short: 'Пароль должен содержать не менее 9 символов.', invalid_password: 'Пароль должен содержать от 9 до 1024 символов.', project_not_found: 'Проект не найден или у вас нет доступа.',
}
export function apiAssetUrl(path: string) { return /^\/(?:trial\/photos\/|projects\/[^/]+\/trial\/photos\/)/.test(path) ? `/api${path}` : path }
export function accountError(data: Record<string, any>) { const code = typeof data.detail === 'string' ? data.detail : data.code; return ACCOUNT_ERRORS[code] ?? 'Обратитесь к администратору' }
export async function accountRequest<T = Record<string, any>>(path: string, method = 'GET', body?: object | FormData, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, { method, signal, credentials: 'same-origin', headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json', ...(path === '/trial/import' ? { 'Idempotency-Key': randomUUID() } : {}) }, ...(body ? { body: body instanceof FormData ? body : JSON.stringify(body) } : {}) }).catch(() => { throw new Error('Обратитесь к администратору') })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(response.status >= 500 ? 'Обратитесь к администратору' : accountError(data))
  return data
}
export function useAppearance(preference: User['theme']) {
  const [dark, setDark] = useState(false)
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)')
    const update = () => { const value = preference === 'dark' || (preference === 'system' && media.matches); setDark(value); document.documentElement.dataset.appearance = value ? 'dark' : 'light' }
    update(); media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [preference])
  return dark ? 'dark' : 'light'
}
function savedTheme(): User['theme'] { try { const value = localStorage.getItem('account-theme'); return value === 'light' || value === 'dark' ? value : 'system' } catch { return 'system' } }
function useScopeFence(scope: string) {
  const state = useRef({ scope, generation: 0 })
  if (state.current.scope !== scope) state.current = { scope, generation: state.current.generation + 1 }
  useEffect(() => () => { state.current.generation++ }, [])
  return () => { const generation = state.current.generation; return () => state.current.generation === generation }
}
type PendingImport = { key: string; body?: Blob; contentType?: string; filename?: string }
export default function AccountShell({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null), [loaded, setLoaded] = useState(false), [error, setError] = useState(''), [theme, setTheme] = useState(savedTheme)
  const returnTo = useRef('/'), authGeneration = useRef(0), themeGeneration = useRef(0), imports = useRef(new Map<string, PendingImport>())
  const [path, setPath] = useState(location.pathname), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false)
  const appearance = useAppearance(theme)
  const accountMenu = useRef<HTMLDetailsElement>(null)
  const header = useRef<HTMLElement>(null)
  useEffect(() => {
    const closeOutside = (event: PointerEvent) => { header.current?.querySelectorAll<HTMLDetailsElement>('details[open]').forEach(menu => { if (!menu.contains(event.target as Node)) menu.open = false }) }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [])
  useEffect(() => { if (accountMenu.current) accountMenu.current.open = false }, [path, user?.id])
  const navigate = (next: string, rememberInvitation = true) => { if (!dispatchEvent(new Event('account-navigation', { cancelable: true }))) return false; if (rememberInvitation && path.startsWith('/invite/') && /^\/(login|register)$/.test(next)) returnTo.current = path; else if (!/^\/(login|register)$/.test(next)) returnTo.current = '/'; history.pushState(null, '', next); setPath(next); dispatchEvent(new PopStateEvent('popstate')); setError(''); setNotice(''); return true }
  useEffect(() => { const generation = authGeneration.current; const update = () => setPath(location.pathname); addEventListener('popstate', update); addEventListener('workspace-navigation', update); void accountRequest('/account/session').then(data => { if (generation !== authGeneration.current) return; setUser(data.user); if (data.user) setTheme(data.user.theme) }).catch(reason => { if (generation === authGeneration.current) setError(reason.message) }).finally(() => { if (generation === authGeneration.current) setLoaded(true) }); return () => { authGeneration.current++; removeEventListener('popstate', update); removeEventListener('workspace-navigation', update) } }, [])
  const updateTheme = async (value: User['theme']) => {
    const generation = authGeneration.current, request = ++themeGeneration.current
    setTheme(value); try { localStorage.setItem('account-theme', value) } catch {}
    if (user) try { const data = await accountRequest('/account/profile', 'PATCH', { theme: value }); if (generation === authGeneration.current && request === themeGeneration.current) setUser(data.user) } catch (reason) { if (generation === authGeneration.current && request === themeGeneration.current) setError((reason as Error).message) }
  }
  async function logout() {
    if (!dispatchEvent(new Event('account-navigation', { cancelable: true }))) return
    const generation = ++authGeneration.current
    returnTo.current = '/'; setUser(null); setBusy(false)
    try { await accountRequest('/account/logout', 'POST'); if (generation !== authGeneration.current) return; setUser(null); navigate('/login', false) } catch (reason) { if (generation === authGeneration.current) setError((reason as Error).message) }
  }
  const special = /^\/(login|register|account|invite\/)/.test(path)
  const route = special ? path.split('/')[1] : 'login'
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const generation = route === 'login' || route === 'register' ? ++authGeneration.current : authGeneration.current; setBusy(true); setError(''); setNotice('')
    const fields = Object.fromEntries(new FormData(event.currentTarget)); const token = fields.token
    const endpoint = { login: 'login', register: 'register', account: 'profile' }[route]
    if (!endpoint) { setBusy(false); return }
    const body = Object.fromEntries(Object.entries({ ...fields, ...(token ? { token } : {}) }).filter(([, value]) => value !== ''))
    try { const data = await accountRequest(`/account/${endpoint}`, route === 'account' ? 'PATCH' : 'POST', body); if (generation !== authGeneration.current) return; if (data.user) { setUser(data.user); setTheme(data.user.theme); if (route === 'login' || route === 'register') { const destination = returnTo.current; returnTo.current = '/'; navigate(destination) } } else if (route === 'register') { navigate('/login'); setNotice('Аккаунт создан. Войдите с указанными почтой и паролем.') } else setNotice('Готово.') } catch (reason) { if (generation === authGeneration.current) setError((reason as Error).message) } finally { if (generation === authGeneration.current) setBusy(false) }
  }
  return <Theme appearance={appearance} accentColor="purple" className="with-account-header">
    {import.meta.env.MODE === 'demo' && <aside className="preview-version-notice" role="status">Открыт старый предпросмотр с временными данными и без модели помощника. <a href="http://127.0.0.1:5190/">Перейти в рабочую версию</a></aside>}
    <TutorialProvider key={user?.id ?? "anonymous"} account={user?.id ?? "anonymous"} navigate={navigate}><header className="account-header" ref={header}><div className="account-header-inner">
      <a className="account-brand" href="/" aria-label="Проекты" onClick={event => { event.preventDefault(); navigate('/') }}><TeamLogo /><span>Контроль строительства<small>17 мгновений ИИ</small></span></a>
      <nav className="account-actions" aria-label="Сервис и аккаунт">
        {user && <TutorialStart />}
        <a className="header-action" href="/examples" aria-current={path === '/examples' ? 'page' : undefined} onClick={event => { event.preventDefault(); navigate('/examples') }}>Примеры</a>
        {user && <>
          {path.match(/^\/projects\/([^/]+)/)?.[1] && <Collaboration key={`members:${user.id}:${path.match(/^\/projects\/([^/]+)/)?.[1]}`} kind="members" currentUserId={user.id} projectId={path.match(/^\/projects\/([^/]+)/)?.[1]} navigate={navigate} />}
          <Collaboration key={`notifications:${user.id}`} kind="notifications" currentUserId={user.id} navigate={navigate} />
        </>}
        <details className="account-menu" ref={accountMenu} onKeyDown={event => { if (event.key === 'Escape' && accountMenu.current) { accountMenu.current.open = false; accountMenu.current.querySelector('summary')?.focus() } }}>
          <summary aria-label={user ? 'Меню аккаунта' : 'Настройки темы'}>{user ? <><span className="account-avatar" aria-hidden="true">{user.name.trim().charAt(0).toUpperCase()}</span><span className="account-name">{user.name}</span></> : <span>Тема</span>}<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg></summary>
          <div className="account-menu-panel">
            {user && <><p className="account-menu-email">{user.email}</p><a className="account-menu-link" href="/account" onClick={event => { event.preventDefault(); navigate('/account') }}>Личный кабинет</a></>}
            <fieldset className="theme-picker"><legend>Тема оформления</legend><div>{([['light','Светлая'],['dark','Тёмная'],['system','Системная']] as const).map(([value,label]) => <button key={value} type="button" aria-pressed={theme === value} onClick={() => void updateTheme(value)}>{label}</button>)}</div><p>Системная следует настройкам устройства.</p></fieldset>
            {user && <button type="button" className="account-logout" onClick={() => void logout()}>Выйти</button>}
          </div>
        </details>
        {!user && <a className="header-action" href="/login" onClick={event => { event.preventDefault(); navigate('/login') }}>Войти</a>}
      </nav>
    </div></header>
    {error && <p role="alert" className="error">{error}</p>}
    {!loaded ? <p role="status">Проверяем вход…</p> : path === '/examples' ? <Examples key={user?.id ?? "anonymous"} authenticated={!!user} pendingStore={imports.current} accountId={user?.id ?? "anonymous"} navigate={navigate} /> : route === 'invite' && special ? <Invitation token={path.split('/')[2]} authenticated={!!user} navigate={navigate} /> : special || !user ? <main className="page account-page"><h1>{{ login: 'Вход', register: 'Регистрация', account: 'Аккаунт' }[route]}</h1>{notice && <p role="status">{notice}</p>}<form key={route} onSubmit={submit}>{route === 'register' && <p>Это демонстрационная версия. Не используйте пароль от личных аккаунтов. Минимум 9 символов.</p>}
      {(route === 'register' || route === 'account') && <label>Имя<input name="name" required defaultValue={user?.name} maxLength={120} autoComplete="name" /></label>}
      {['login','register','account'].includes(route) && <label>Почта<input name="email" type="email" required defaultValue={user?.email} autoComplete="email" /></label>}
      {['login','register','account'].includes(route) && <label>{route === 'account' ? 'Новый пароль (необязательно)' : 'Пароль'}<PasswordField name="password" required={route !== 'account'} minLength={route === 'login' ? 1 : 9} maxLength={1024} autoComplete={route === 'login' ? 'current-password' : 'new-password'} /></label>}
      {route === 'account' && <label>Текущий пароль для смены почты или пароля<PasswordField name="current_password" autoComplete="current-password" /></label>}
      <button className="primary" disabled={busy}>{busy ? 'Сохраняем…' : route === 'account' ? 'Сохранить' : 'Продолжить'}</button></form><nav className="account-links">{[['/login','Войти'],['/register','Создать аккаунт']].map(([href,label]) => <a key={href} href={href} onClick={event => { event.preventDefault(); navigate(href) }}>{label}</a>)}</nav></main> : <AccountIdentity.Provider key={user.id} value={user.id}>{path.match(/^\/projects\/([^/]+)\/learn\/(photos|result|signals)$/) ? <TutorialPage key={`${user.id}:${path}`} projectId={path.split("/")[2]} page={path.split("/")[4]} request={accountRequest} /> : children}</AccountIdentity.Provider>}
    <AssistantChat accountId={user?.id ?? "anonymous"} request={accountRequest} key={`${user?.id ?? "anonymous"}:${path.match(/^\/projects\/([^/]+)/)?.[1] ?? "general"}`} projectId={user ? path.match(/^\/projects\/([^/]+)/)?.[1] : undefined} />
    </TutorialProvider>
  </Theme>
}
function Invitation({ token, authenticated, navigate }: { token: string; authenticated: boolean; navigate: (path: string) => void }) {
  const [preview,setPreview] = useState<any>(), [error,setError] = useState(''), [busy,setBusy] = useState(false)
  useEffect(() => { if (authenticated) void accountRequest(`/invitations/${encodeURIComponent(token)}`).then(setPreview).catch(reason => setError(reason.message)) }, [token,authenticated])
  return <main className="page"><h1>Приглашение в проект</h1>{error && <p role="alert">{error}</p>}{!authenticated ? <p>Войдите в аккаунт и снова откройте ссылку приглашения.</p> : preview && <><p>{preview.project_name} · {preview.role === 'viewer' ? 'Просмотр' : 'Редактирование'}</p><p>Действует до {new Date(preview.expires_at).toLocaleString('ru')}</p><button disabled={busy} onClick={() => { setBusy(true); void accountRequest('/invitations/accept','POST',{token}).then(data => navigate(`/projects/${data.project_id}`)).catch(reason => setError(reason.message)).finally(() => setBusy(false)) }}>Принять приглашение</button></>}</main>
}
const roleLabels: Record<string,string> = {owner:'Владелец',editor:'Редактор',viewer:'Наблюдатель'}
function Collaboration({ projectId, navigate, currentUserId, kind }: { kind: 'members' | 'notifications'; currentUserId: string; projectId?: string; navigate: (path: string) => void }) {
  const [busy, setBusy] = useState(false)
  const actionLock = useRef(false)
  const [open,setOpen] = useState(false), [members,setMembers] = useState<any[]>([]), [invites,setInvites] = useState<any[]>([]), [notifications,setNotifications] = useState<any[]>([]), [error,setError] = useState(''), [link,setLink] = useState('')
  const capture = useScopeFence(`${currentUserId}:${projectId}`)
  async function refresh() { const current = capture(); try { if (kind === 'notifications') { const data = await accountRequest('/notifications'); if (!current()) return; setNotifications(data.notifications) } if (projectId && kind === 'members') { const data = await accountRequest(`/projects/${projectId}/members`); if (!current()) return; setMembers(data.members); try { const data = await accountRequest(`/projects/${projectId}/invitations`); if (current()) setInvites(data.invitations) } catch { if (current()) setInvites([]) } } } catch(reason) { if (current()) setError((reason as Error).message) } }
  useEffect(() => { setError(''); setMembers([]); setInvites([]); setLink(''); if(open) void refresh() }, [open, projectId])
  async function act(path: string, method = 'POST', body?: object) {
    if (actionLock.current) return
    const current = capture(); actionLock.current = true; setBusy(true); setError('')
    try { await accountRequest(path,method,body); if (current()) await refresh() }
    catch(reason) { if (current()) setError((reason as Error).message) }
    finally { actionLock.current = false; if (current()) setBusy(false) }
  }
  return <details open={open} onToggle={event => setOpen(event.currentTarget.open)} className="collaboration" onKeyDown={event => { if (event.key === 'Escape') { setOpen(false); event.currentTarget.querySelector('summary')?.focus() } }}><summary>{kind === 'notifications' && <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></svg>}<span>{kind === 'members' ? 'Участники' : 'Уведомления'}</span></summary><div className="collaboration-panel">{error && <p role="alert">{error}</p>}{kind === 'notifications' && <><h2>Уведомления</h2>{!notifications.length && <p>Пока нет уведомлений.</p>}{notifications.map(item => <section key={item.id}><p>{item.project_name} · {roleLabels[item.role] ?? item.role}</p>{item.actionable && <button onClick={() => { const current = capture(); void accountRequest('/invitations/accept','POST',{invitation_id:item.invitation_id}).then(data => { if (current()) navigate(`/projects/${data.project_id}`) }).catch(reason => { if (current()) setError(reason.message) }) }}>Принять</button>}{!item.read && <button onClick={() => void act(`/notifications/${item.id}/read`)}>Прочитано</button>}</section>)}</>}{projectId && kind === 'members' && <><h2>Участники проекта</h2>{members.map(item => <p key={item.user_id}>{item.name} · {item.email} · {roleLabels[item.role] ?? item.role}{members.some(member => member.user_id === currentUserId && member.role === 'owner') && item.role !== 'owner' && <><label>Роль {item.name}<select aria-label={`Роль ${item.name}`} value={item.role} disabled={busy} onChange={event => void act(`/projects/${projectId}/members/${item.user_id}`, 'PATCH', { role: event.target.value })}><option value="viewer">Наблюдатель</option><option value="editor">Редактор</option></select></label><button disabled={busy} onClick={() => void act(`/projects/${projectId}/members/${item.user_id}`,'DELETE')}>Удалить доступ</button></>}</p>)}{members.some(member => member.user_id === currentUserId && member.role === 'owner') && <form onSubmit={event => { event.preventDefault(); const current = capture(); const fields = Object.fromEntries(new FormData(event.currentTarget)); void accountRequest(`/projects/${projectId}/invitations`,'POST',{role:fields.role,...(fields.email ? {email:fields.email} : {})}).then(data => { if (!current()) return; setLink(new URL(data.url,location.origin).href); void refresh() }).catch(reason => { if (current()) setError(reason.message) }) }}><label>Почта получателя (необязательно)<input type="email" name="email" /></label><label>Права<span className="collaboration-select"><select name="role"><option value="viewer">Просмотр</option><option value="editor">Редактирование</option></select><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg></span></label><button className="primary" type="submit">Создать приглашение</button></form>}{link && <p>Скопируйте ссылку: <a href={link}>{link}</a></p>}{invites.map(item => <p key={item.id}>{item.email ?? 'Общая ссылка'} · {roleLabels[item.role] ?? item.role} · {item.revoked ? 'Отозвано' : new Date(item.expires_at).toLocaleDateString('ru')}{!item.revoked && <button onClick={() => void act(`/projects/${projectId}/invitations/${item.id}`,'DELETE')}>Отозвать</button>}</p>)}</>}</div></details>
}
function Examples({ authenticated, navigate, pendingStore, accountId }: { authenticated: boolean; navigate: (path: string) => void; pendingStore: Map<string, PendingImport>; accountId: string }) {
  const [preview,setPreview] = useState<any>(), [error,setError] = useState(''), [busy,setBusy] = useState(false), [pending,setPending] = useState(() => pendingStore.get(accountId))
  const capture = useScopeFence(accountId)
  useEffect(() => { const current = capture(); void accountRequest('/trial/preview').then(data => { if(current()) setPreview(data) }).catch(reason => { if(current()) setError(reason.message) }) }, [])
  async function importProject(file?: File) {
    const current = capture(); setBusy(true); setError('')
    try {
      let operation = pendingStore.get(accountId)
      if (!operation) {
        operation = { key: randomUUID(), filename: file?.name }
        if (file) { const form = new FormData(); form.append('file',file); const request = new Request(new URL('/api/trial/import',location.origin), {method:'POST',body:form}); operation.contentType = request.headers.get('Content-Type')!; operation.body = await request.blob() }
        pendingStore.set(accountId, operation); if (current()) setPending(operation)
      }
      const response = await fetch('/api/trial/import',{method:'POST',credentials:'same-origin',headers:{'Idempotency-Key':operation.key,...(operation.contentType ? {'Content-Type':operation.contentType} : {})},...(operation.body ? {body:operation.body} : {})})
      const data = await response.json(); if (!response.ok) throw new Error(accountError(data))
      pendingStore.delete(accountId)
      if (current()) { setPending(undefined); navigate(`/projects/${data.project_id}`) }
    } catch(reason) { if (current()) setError((reason as Error).message) } finally { if (current()) setBusy(false) }
  }
  return <main className="page examples-page">
    <header className="examples-intro"><h1>Учебные примеры</h1><p>Попробуйте сервис на готовом проекте или скачайте фотографии для собственного анализа.</p></header>
    {error && <p className="error" role="alert">{error}</p>}
    <section className="examples-start" aria-labelledby="examples-start-title"><div><span className="examples-kicker">Быстрый старт</span><h2 id="examples-start-title">Попробуйте на готовом проекте</h2><p>В отдельном проекте уже есть фотографии, план работ и примеры результатов. Ваши проекты останутся без изменений.</p>{authenticated ? <>{pending && <p role="status">Импорт {pending.filename ?? 'учебного проекта'} не подтверждён. Повторите попытку: второй проект не создастся.</p>}<button className="primary" disabled={busy} onClick={() => void importProject()}>{busy ? 'Создаём проект…' : pending ? 'Повторить незавершённый импорт' : 'Импортировать учебный проект'}</button></> : <a className="primary" href="/login">Войдите для импорта</a>}</div><ol className="examples-steps"><li>Откройте учебный проект</li><li>Посмотрите фотографии и предупреждения</li><li>Запустите свой анализ или исправьте разметку</li></ol></section>
    <details className="examples-files"><summary>Скачать материалы или загрузить свой архив</summary><div className="examples-file-options"><div><h3>Скачать материалы</h3><p>Фотографии можно загрузить в любой свой проект.</p><a href="/api/trial/photos.zip" download>Скачать фотографии</a><a href="/api/trial/project.zip" download>Скачать полный проект</a></div>{authenticated && <div><h3>Загрузить архив проекта</h3><p>Выберите ранее скачанный ZIP-архив учебного проекта.</p><label className="examples-upload"><span>Выбрать ZIP-архив</span><input className="examples-file-input" aria-label="Импорт архива проекта" type="file" accept=".zip" disabled={busy || !!pending} onChange={event => { const file=event.target.files?.[0]; if(file) void importProject(file); event.target.value='' }} /></label></div>}</div></details>
    <section aria-labelledby="examples-gallery-title"><h2 id="examples-gallery-title">Что можно увидеть в результате</h2><p className="examples-disclaimer">Это учебные примеры с готовыми пояснениями. Они не являются результатом реальной проверки. Новый анализ запускается отдельно.</p>{!preview && !error && <p role="status">Загружаем примеры…</p>}<div className="examples-grid">{preview?.examples?.map((item:any,index:number) => <article className="example-card" key={index}><div className="example-card-photos">{item.photos?.map((url:string) => <a key={url} href={apiAssetUrl(url)} target="_blank" rel="noreferrer" aria-label={`Открыть фотографию: ${item.title}`}><img src={apiAssetUrl(url)} alt={item.title} loading="lazy" /></a>)}</div><div className="example-card-body"><span className="example-outcome" data-outcome={item.outcome}>{item.outcome}</span><h3>{item.title}</h3><dl><div><dt>Что видно</dt><dd>{item.found}</dd></div><div><dt>Что ожидалось</dt><dd>{item.expected}</dd></div><div className="example-next-step"><dt>Что проверить</dt><dd>{item.check}</dd></div></dl></div></article>)}</div></section>
  </main>
}
