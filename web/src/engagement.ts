let browser = ''
let identity: Promise<string> | undefined

export function browserIdentity(): Promise<string> {
  if (!identity) identity = (async () => {
    const read = () => {
      try {
        browser = localStorage.getItem('construction-browser') ?? crypto.randomUUID()
        localStorage.setItem('construction-browser', browser)
      } catch { browser = crypto.randomUUID() }
      return browser
    }
    return navigator.locks ? navigator.locks.request('construction-browser', read) : read()
  })()
  return identity
}

export function attributionHeaders(): Record<string, string> {
  return browser ? { 'X-Browser-ID': browser } : {}
}

export async function track(kind: 'visit' | 'wizard_started' | 'wizard_completed' | 'wizard_skipped') {
  try {
    const body = JSON.stringify({ browser_id: await browserIdentity(), event_id: crypto.randomUUID(), kind })
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const response = await fetch('/api/analytics/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, signal: AbortSignal.timeout(5000) })
        if (response.ok || response.status < 500) return
      } catch { /* Retry the same event identity after an unknown response. */ }
    }
  } catch { /* Telemetry never blocks the application. */ }
}

export function startActivity() {
  let last = 0
  const activity = () => {
    if (document.visibilityState === 'hidden' || location.pathname.startsWith('/admin')) return
    if (Date.now() - last < 60_000) return
    last = Date.now()
    void track('visit')
  }
  activity()
  const events = ['pointerdown', 'keydown', 'scroll'] as const
  events.forEach(name => window.addEventListener(name, activity, { passive: true }))
  document.addEventListener('visibilitychange', activity)
  return () => { events.forEach(name => window.removeEventListener(name, activity)); document.removeEventListener('visibilitychange', activity) }
}
