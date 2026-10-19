import TeamLogo from './TeamLogo'
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { randomUUID } from './randomUUID'
import { useMotionPreference } from './MotionPreference'
import './AssistantChat.css'
import { TutorialGuide, useTutorial } from './Tutorial'

type Message = { id: string; role: 'user' | 'assistant'; content: string; created_at?: string; fresh?: boolean; failed?: boolean }
type Reply = { messages: Message[] }
type RequestChat = (path: string, method?: string, body?: object, signal?: AbortSignal) => Promise<Reply>

function inlineText(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) => part.length > 4 && part.startsWith('**') && part.endsWith('**')
    ? <strong key={index}>{part.slice(2, -2)}</strong>
    : part.length > 2 && part.startsWith('`') && part.endsWith('`') ? <code key={index}>{part.slice(1, -1)}</code> : part)
}
export function ChatText({ text }: { text: string }) {
  const blocks: { kind: 'p' | 'ol' | 'ul'; lines: string[] }[] = []
  let current: (typeof blocks)[number] | undefined
  for (const line of text.split('\n')) {
    if (!line.trim()) { current = undefined; continue }
    const ordered = /^\s*\d+[.)]\s+(.+)/.exec(line)
    const bullet = /^\s*[-*]\s+(.+)/.exec(line)
    const kind = ordered ? 'ol' : bullet ? 'ul' : 'p'
    if (!current || current.kind !== kind) { current = { kind, lines: [] }; blocks.push(current) }
    current.lines.push(ordered?.[1] ?? bullet?.[1] ?? line)
  }
  return <>{blocks.map((block, index) => block.kind === 'p' ? <p key={index}>{inlineText(block.lines.join('\n'))}</p>
    : block.kind === 'ol' ? <ol key={index}>{block.lines.map((line, i) => <li key={i}>{inlineText(line)}</li>)}</ol>
      : <ul key={index}>{block.lines.map((line, i) => <li key={i}>{inlineText(line)}</li>)}</ul>)}</>
}

export default function AssistantChat({ projectId, request, accountId = "anonymous" }: { projectId?: string; request: RequestChat; accountId?: string }) {
  const guide = useTutorial()
  const storageKey = `assistant-draft:${accountId}:${projectId ?? 'general'}`
  const [open, setOpen] = useState(() => !!guide?.state.started && !guide.state.paused && !guide.state.chatHidden)
  const [guideFocus, setGuideFocus] = useState(0)
  const [viewingAnswer, setViewingAnswer] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [tutorialExpanded, setTutorialExpanded] = useState(false)
  const compactTutorial = !!guide?.state.started && !guide.state.paused && !tutorialExpanded && !fullscreen
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState(() => { try { return localStorage.getItem(storageKey) ?? '' } catch { return '' } })
  useEffect(() => { try { localStorage.setItem(storageKey, draft) } catch {} }, [storageKey,draft])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [historyAttempt, setHistoryAttempt] = useState(0)
  const [failed, setFailed] = useState<Message | null>(null)
  const panelId = useId()
  const panel = useRef<HTMLDialogElement>(null)
  const launcher = useRef<HTMLButtonElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const transcript = useRef<HTMLDivElement>(null)
  const historyLoaded = useRef(false)
  const active = useRef(false)
  const epoch = useRef(0)
  const sending = useRef(false)
  const pendingRequest = useRef<AbortController | null>(null)
  const { enabled } = useMotionPreference()

  useEffect(() => {
    active.current = true
    return () => { active.current = false; epoch.current++; pendingRequest.current?.abort() }
  }, [])
  useEffect(() => {
    const show = () => { setOpen(true); setViewingAnswer(false); guide?.update({chatHidden:false}); setGuideFocus(value => value + 1) }
    addEventListener('open-assistant', show)
    return () => removeEventListener('open-assistant', show)
  }, [])
  useEffect(() => {
    if (!open || !panel.current) return
    const dialog = panel.current
    const previousOverflow = document.body.style.overflow
    if (dialog.open) dialog.close()
    if (fullscreen && typeof dialog.showModal === 'function') { dialog.showModal(); document.body.style.overflow = 'hidden' }
    else if (typeof dialog.show === 'function') dialog.show()
    else dialog.setAttribute('open', '')
    input.current?.focus({ preventScroll: true })
    return () => {
      if (dialog.open && typeof dialog.close === 'function') dialog.close()
      document.body.style.overflow = previousOverflow
      launcher.current?.focus({ preventScroll: true })
    }
  }, [open, fullscreen])
  useEffect(() => {
    if (!open || !projectId || historyLoaded.current) return
    const controller = new AbortController()
    const generation = epoch.current
    setLoadingHistory(true); setError('')
    void request(`/assistant/messages?project_id=${encodeURIComponent(projectId)}`, 'GET', undefined, controller.signal).then(data => {
      if (!controller.signal.aborted && active.current && generation === epoch.current) { setMessages(data.messages); historyLoaded.current = true }
    }).catch(reason => { if (!controller.signal.aborted && active.current && generation === epoch.current) setError(reason.message || 'Не удалось загрузить переписку.') })
      .finally(() => { if (!controller.signal.aborted && active.current && generation === epoch.current) setLoadingHistory(false) })
    return () => { controller.abort(); setLoadingHistory(false) }
  }, [open, projectId, historyAttempt, request])
  useEffect(() => {
    const element = transcript.current
    if (open && element) element.scrollTop = guide?.state.started && !guide.state.paused && !viewingAnswer ? 0 : element.scrollHeight
  }, [open, fullscreen, messages, busy, guide?.state.step, guide?.state.paused, guideFocus, viewingAnswer])
  useEffect(() => { setViewingAnswer(false) }, [guide?.state.step])

  function hide() { setOpen(false); setFullscreen(false); guide?.update({chatHidden:true}) }
  function show() { setOpen(true); guide?.update({chatHidden:false}) }
  function close() { setOpen(false); setFullscreen(false); if(guide?.state.started) guide.update({paused:true,chatHidden:true}) }
  async function send(retry?: Message) {
    const content = retry?.content ?? draft.trim()
    if (!content || sending.current || loadingHistory) return
    const generation = epoch.current
    const question: Message = retry ?? { id: randomUUID(), role: 'user', content, created_at: new Date().toISOString(), fresh: true }
    if (projectId) historyLoaded.current = true
    if(guide?.state.started) setViewingAnswer(true)
    sending.current = true; setBusy(true); setError(''); setFailed(null)
    if (retry) setMessages(current => current.map(item => item.id === retry.id ? { ...item, failed: false } : item))
    else { setMessages(current => [...current, question]); setDraft('') }
    const controller = new AbortController()
    pendingRequest.current = controller
    let timer: ReturnType<typeof setTimeout> | undefined
    try {
      const result = await Promise.race([
        request('/assistant/messages', 'POST', { message: content, ...(projectId ? { project_id: projectId } : {}), ...(guide?.state.started ? { tutorial_context: {version: 1, step: guide.state.step} } : {}) }, controller.signal),
        new Promise<never>((_, reject) => { timer = setTimeout(() => { controller.abort(); reject(new Error('Ответ задерживается. Можно повторить отправку.')) }, 45000) }),
      ])
      if (!active.current || generation !== epoch.current) return
      const response = result.messages.map((item, index) => ({ ...item, fresh: index === result.messages.length - 1 }))
      if (response.some(item => item.role === 'user')) setMessages(response)
      else setMessages(current => [...current, ...response])
    } catch (reason) {
      if (!active.current || generation !== epoch.current) return
      setError(reason instanceof Error ? reason.message : 'Не удалось получить ответ. Попробуйте снова.')
      setFailed(question)
      setMessages(current => current.map(item => item.id === question.id ? { ...item, failed: true } : item))
    } finally {
      clearTimeout(timer)
      if (active.current && generation === epoch.current) { sending.current = false; pendingRequest.current = null; setBusy(false); if (panel.current?.contains(document.activeElement)) input.current?.focus({ preventScroll: true }) }
    }
  }
  function submit(event: FormEvent) { event.preventDefault(); void send() }

  return <aside className="assistant-chat">
    <button ref={launcher} type="button" className="assistant-chat-launcher" aria-expanded={open} aria-controls={panelId} onClick={() => open ? hide() : show()}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M20 11a8 8 0 0 1-8 8H6l-4 3V11a9 9 0 0 1 18 0Z" /><path d="M7 10h8M7 14h5" /></svg>Помощник
    </button>
    <dialog hidden={!open} id={panelId} ref={panel} className={`assistant-chat-panel${fullscreen ? ' is-fullscreen' : ''}${compactTutorial ? ' is-tutorial-compact' : ''}${guide?.state.started ? ' has-tutorial' : ''}`} role="dialog" aria-label="Чат с помощником" aria-modal={fullscreen || undefined} onCancel={event => { event.preventDefault(); close() }} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); close() } }}>
      <header className="chat-header"><div className="chat-identity"><TeamLogo size={34} /><div><h2>Помощник</h2><p>{projectId ? 'По текущему проекту' : 'Помощь по сервису'}</p></div></div><div className="chat-window-actions">{compactTutorial && <button className="tutorial-expand-chat" type="button" aria-label="Открыть полный чат" onClick={() => setTutorialExpanded(true)}>Чат</button>}
        <button type="button" aria-label={fullscreen ? 'Свернуть чат' : 'Развернуть чат'} onClick={() => setFullscreen(value => !value)}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">{fullscreen ? <path d="M9 3v6H3m12-6v6h6M9 21v-6H3m12 6v-6h6" /> : <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" />}</svg></button>
        <button type="button" aria-label="Скрыть чат" title="Скрыть чат без паузы в обучении" onClick={hide}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M5 18h14" /></svg></button>
        <button type="button" aria-label="Закрыть чат" onClick={close}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button>
      </div></header>
      <div className="chat-transcript" ref={transcript}><TutorialGuide /><div className="chat-messages" role="log" aria-label="Переписка с помощником" aria-live="polite" aria-relevant="additions text">
        {!guide?.state.started && !messages.length && !loadingHistory && <div className="chat-welcome"><h3>Чем помочь?</h3><p>Подскажу, как начать анализ, разобраться в сигналах или пригласить участников.</p></div>}
        {loadingHistory && <p className="chat-history-status" role="status">Загружаем переписку…</p>}
        {messages.map(item => <motion.article key={item.id} className={`chat-message chat-message--${item.role}`} aria-label={item.role === 'user' ? 'Ваше сообщение' : 'Ответ помощника'} initial={enabled && item.fresh ? { opacity: 0, y: 6 } : false} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18, ease: 'easeOut' }}>
          <span className="chat-author">{item.role === 'user' ? 'Вы' : 'Помощник'}</span><div className="chat-bubble"><ChatText text={item.content} />{item.created_at && !Number.isNaN(Date.parse(item.created_at)) && <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</time>}</div>{item.failed && <span className="chat-delivery-error">Ответ не получен</span>}
        </motion.article>)}
        {busy && <div className="chat-message chat-message--assistant chat-pending" role="status" aria-label="Помощник готовит ответ"><span className="chat-author">Помощник</span><div className="chat-bubble"><span className="chat-typing" aria-hidden="true"><span /><span /><span /></span><span>Готовлю ответ…</span></div></div>}
        {guide?.state.started && !guide.state.paused && viewingAnswer && <button type="button" className="tutorial-resume-chat" onClick={() => { setViewingAnswer(false); setGuideFocus(value => value + 1) }}>К текущему шагу</button>}
        {guide?.state.started && guide.state.paused && <button type="button" className="tutorial-resume-chat" onClick={guide.start}>Вернуться к обучению</button>}
      </div></div>
      {error && <div className="chat-error" role="alert"><p>{error}</p>{failed ? <button type="button" disabled={busy} onClick={() => void send(failed)}>Повторить отправку</button> : projectId && <button type="button" onClick={() => setHistoryAttempt(value => value + 1)}>Повторить загрузку</button>}</div>}
      <form className="chat-composer" onSubmit={submit}><div className="chat-input-row"><label className="sr-only" htmlFor={`${panelId}-message`}>Сообщение помощнику</label><textarea id={`${panelId}-message`} ref={input} rows={2} required maxLength={4000} value={draft} placeholder="Напишите сообщение…" onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send() } }} /><button type="submit" className="chat-send" disabled={busy || loadingHistory || !draft.trim()} aria-label="Отправить сообщение"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true"><path d="m5 12 7-7 7 7M12 5v15" /></svg></button></div><p className="chat-composer-hint">Enter — отправить · Shift+Enter — новая строка</p></form>
    </dialog>
  </aside>
}
