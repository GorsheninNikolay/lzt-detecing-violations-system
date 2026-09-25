import { useEffect, useRef, type MouseEvent } from 'react'

type Props = {
  route: string | null
  historyPath: string
  navigate: (path: string) => void
  onNewAnalysis: () => void
}

export default function AppHeader({ route, historyPath, navigate, onNewAnalysis }: Props) {
  const more = useRef<HTMLDetailsElement>(null)
  useEffect(() => { if (more.current) more.current.open = false }, [route])

  const primary = [
    { path: '/', route: 'stages', label: 'Этапы' },
    { path: historyPath, route: 'history', label: 'Анализы' },
    { path: '/plan', route: 'plan', label: 'План' },
    { path: '/signals', route: 'signals', label: 'Сигналы' },
  ]
  const additional = [
    { path: '/readiness', route: 'readiness', label: 'Готовность' },
    { path: '/provider-comparison', route: 'provider-comparison', label: 'Сравнение провайдеров' },
    { path: '/about', route: 'about', label: 'О проекте' },
  ]
  const open = (event: MouseEvent<HTMLAnchorElement>, path: string) => {
    event.preventDefault()
    navigate(path)
  }

  return <>
    <header className="topbar"><div className="topbar-inner">
      <div className="brand"><a href="/" onClick={event => open(event, '/')}>Контроль строительства</a><a className="team-link" href="/about" onClick={event => open(event, '/about')}>17 мгновений ИИ</a></div>
      <nav className="primary-nav" aria-label="Основная навигация">{primary.map(item => <a key={item.route} href={item.path} aria-current={route === item.route ? 'page' : undefined} onClick={event => open(event, item.path)}>{item.label}</a>)}</nav>
      <details ref={more} className="more-menu" onKeyDown={event => { if (event.key === 'Escape') { more.current!.open = false; more.current!.querySelector('summary')?.focus() } }}>
        <summary>Ещё</summary>
        <nav className="secondary-nav" aria-label="Дополнительная навигация">{additional.map(item => <a key={item.route} href={item.path} aria-current={route === item.route ? 'page' : undefined} onClick={event => open(event, item.path)}>{item.label}</a>)}</nav>
      </details>
      <a className="primary new-analysis-link" href="/new" aria-current={route === 'new' ? 'page' : undefined} onClick={event => { event.preventDefault(); onNewAnalysis() }}>Новый анализ</a>
    </div></header>
    <nav className="bottom-nav" aria-label="Навигация по разделам">{primary.map(item => <a key={item.route} href={item.path} aria-label={`Раздел ${item.label}`} aria-current={route === item.route ? 'page' : undefined} onClick={event => open(event, item.path)}>{item.label}</a>)}</nav>
  </>
}
