import TeamLogo from './TeamLogo'
import { useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from 'react'

type Props = {
  readOnly?: boolean
  projectId?: string
  projectName?: string
  projects?: { id: string; name: string }[]
  route: string | null
  historyPath: string
  navigate: (path: string) => void
  onNewAnalysis: () => void
}

export default function AppHeader({ route, historyPath, navigate, onNewAnalysis, projectId, projectName, projects = [], readOnly = false }: Props) {
  const more = useRef<HTMLDetailsElement>(null)
  const row = useRef<HTMLDivElement>(null)
  const measure = useRef<HTMLDivElement>(null)
  const [inline, setInline] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  useEffect(() => { setMenuOpen(false) }, [route])
  useLayoutEffect(() => {
    const element = row.current
    const probe = measure.current
    if (!element || !probe) return
    const update = () => {
      if (!element.clientWidth) return
      const style = getComputedStyle(element)
      const fixed = Array.from(element.children).filter(child => child !== more.current && child !== probe)
        .map(child => child.getBoundingClientRect().width).filter(width => width > 0)
      const padding = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0)
      const gap = parseFloat(style.columnGap) || 0
      const required = fixed.reduce((sum, width) => sum + width, 0) + probe.getBoundingClientRect().width + gap * fixed.length
      setInline(required <= element.clientWidth - padding)
    }
    update()
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(update) : null
    observer?.observe(element)
    observer?.observe(probe)
    Array.from(element.children).filter(child => child !== more.current && child !== probe).forEach(child => observer?.observe(child))
    window.addEventListener('resize', update)
    let active = true
    void document.fonts?.ready.then(() => { if (active) update() })
    return () => { active = false; observer?.disconnect(); window.removeEventListener('resize', update) }
  }, [projectId, readOnly])

  const primary = [
    { path: projectId ? `/projects/${projectId}` : '/', route: projectId ? 'overview' : 'projects', label: projectId ? 'Обзор' : 'Проекты' },
    { path: historyPath, route: 'history', label: 'Анализы' },
    { path: '/plan', route: 'plan', label: 'План работ' },
    { path: '/signals', route: 'signals', label: 'Сигналы' },
  ]
  const nav = projectId ? primary.map(item => ({ ...item, path: item.path.startsWith('/projects/') ? item.path : `/projects/${projectId}${item.route === 'history' ? '/analyses' : item.path}` })) : [primary[0], { path: '/archive', route: 'history', label: 'Анализы' }]
  const open = (event: MouseEvent<HTMLAnchorElement>, path: string) => { event.preventDefault(); navigate(path) }

  return <>
    <header className="topbar"><div className="topbar-inner" ref={row}>
      <div className="brand"><TeamLogo className="header-team-logo" /><a href="/" onClick={event => open(event, '/')}>Контроль строительства</a><a className="team-link" href="/about" onClick={event => open(event, '/about')}>17 мгновений ИИ</a></div>
      <label className="project-switcher"><select aria-label="Выбрать проект" value={projectId ?? ''} onChange={event => navigate(event.target.value ? `/projects/${event.target.value}` : '/')}><option value="">Все проекты</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><svg className="project-switcher-chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>{projectId && !projects.some(item => item.id === projectId) && <span>{projectName ?? 'Загрузка…'}</span>}</label>
      <nav className="primary-nav" aria-label="Основная навигация">{nav.map(item => <a key={item.route} href={item.path} aria-current={route === item.route ? 'page' : undefined} onClick={event => open(event, item.path)}>{item.label}</a>)}</nav>
      <details ref={more} className={`more-menu${inline ? ' more-menu-inline' : ''}`} open={inline || menuOpen} onToggle={event => { if (!inline) setMenuOpen(event.currentTarget.open) }} onKeyDown={event => { if (!inline && event.key === 'Escape') { setMenuOpen(false); more.current?.querySelector('summary')?.focus() } }}>
        <summary hidden={inline}>Ещё</summary>
        <nav className="secondary-nav" aria-label="Дополнительная навигация"><a href="/api/redoc" target="_blank" rel="noreferrer">Документация API</a></nav>
      </details>
      {!readOnly && <a data-tutorial={projectId ? undefined : "create-project"} className="primary new-analysis-link" href={projectId ? `/projects/${projectId}/new` : '/'} aria-current={route === 'new' ? 'page' : undefined} onClick={event => { event.preventDefault(); onNewAnalysis() }}>{projectId ? 'Загрузить фото' : 'Создать проект'}</a>}
      <div className="secondary-nav-measure" ref={measure} aria-hidden="true" inert><span>Документация API</span></div>
    </div></header>
    <nav className="bottom-nav" aria-label="Навигация по разделам">{nav.map(item => <a key={item.route} href={item.path} aria-label={`Раздел ${item.label}`} aria-current={route === item.route ? 'page' : undefined} onClick={event => open(event, item.path)}>{item.label}</a>)}</nav>
  </>
}
