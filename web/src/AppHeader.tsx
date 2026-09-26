import { useEffect, useRef, type MouseEvent } from 'react'

type Props = {
  projectId?: string
  projectName?: string
  projects?: { id: string; name: string }[]
  route: string | null
  historyPath: string
  navigate: (path: string) => void
  onNewAnalysis: () => void
}

export default function AppHeader({ route, historyPath, navigate, onNewAnalysis, projectId, projectName, projects = [] }: Props) {
  const more = useRef<HTMLDetailsElement>(null)
  useEffect(() => { if (more.current) more.current.open = false }, [route])

  const primary = [
    { path: projectId ? `/projects/${projectId}` : '/', route: projectId ? 'overview' : 'projects', label: projectId ? 'Обзор' : 'Проекты' },
    { path: historyPath, route: 'history', label: 'Анализы' },
    { path: '/plan', route: 'plan', label: 'План работ' },
    { path: '/signals', route: 'signals', label: 'Сигналы' },
  ]
  const nav = projectId ? primary.map(item => ({ ...item, path: item.path.startsWith('/projects/') ? item.path : `/projects/${projectId}${item.route === 'history' ? '/analyses' : item.path}` })) : [primary[0], { path: '/archive', route: 'history', label: 'Анализы' }]
  const additional = [
    { path: '/about', route: 'about', label: 'О системе' },
  ]
  const open = (event: MouseEvent<HTMLAnchorElement>, path: string) => {
    event.preventDefault()
    navigate(path)
  }

  return <>
    <header className="topbar"><div className="topbar-inner">
      <div className="brand"><img className="header-team-logo" src="/team-logo.png" alt="" /><a href="/" onClick={event => open(event, '/')}>Контроль строительства</a><a className="team-link" href="/about" onClick={event => open(event, '/about')}>17 мгновений ИИ</a></div>
      <label className="project-switcher"><select aria-label="Выбрать проект" value={projectId ?? ""} onChange={event => navigate(event.target.value ? `/projects/${event.target.value}` : "/")}><option value="">Все проекты</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{projectId && !projects.some(item => item.id === projectId) && <span>{projectName ?? "Загрузка…"}</span>}</label><nav className="primary-nav" aria-label="Основная навигация">{nav.map(item => <a key={item.route} href={item.path} aria-current={route === item.route ? 'page' : undefined} onClick={event => open(event, item.path)}>{item.label}</a>)}</nav>
      <details ref={more} className="more-menu" onKeyDown={event => { if (event.key === 'Escape') { more.current!.open = false; more.current!.querySelector('summary')?.focus() } }}>
        <summary>Ещё</summary>
        <nav className="secondary-nav" aria-label="Дополнительная навигация">{additional.map(item => <a key={item.route} href={item.path} aria-current={route === item.route ? 'page' : undefined} onClick={event => open(event, item.path)}>{item.label}</a>)}</nav>
      </details>
      <a className="primary new-analysis-link" href={projectId ? `/projects/${projectId}/new` : "/"} aria-current={route === 'new' ? 'page' : undefined} onClick={event => { event.preventDefault(); onNewAnalysis() }}>{projectId ? "Загрузить фото" : "Создать проект"}</a>
    </div></header>
    <nav className="bottom-nav" aria-label="Навигация по разделам">{nav.map(item => <a key={item.route} href={item.path} aria-label={`Раздел ${item.label}`} aria-current={route === item.route ? 'page' : undefined} onClick={event => open(event, item.path)}>{item.label}</a>)}</nav>
  </>
}
