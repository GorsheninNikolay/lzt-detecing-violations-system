import { AnnotationEditor, validObjects, type AnnotationObject } from './Annotations'
import trialFixture from '../../shared/trial-project/manifest.json'
import { createPortal } from 'react-dom'
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { randomUUID } from './randomUUID'
import { UploadZone } from './NewAnalysisPage'
import { useMotionPreference } from './MotionPreference'
import './Tutorial.css'
import { validateImage } from './imageValidation'
export const tutorialSteps = [
  'create_project',
  'add_materials',
  'plan',
  'photos',
  'result',
  'signals',
  'complete',
] as const
export type TutorialStep = (typeof tutorialSteps)[number]
type Progress = {
  version: 1
  step: TutorialStep
  projectId?: string
  key: string
  paused: boolean
  started: boolean
  selected: string[]
  signal: boolean
  planRead?: boolean
  planImported?: boolean
  questionSubmitted?: boolean
  revealedSteps?: TutorialStep[]
  correction?: AnnotationObject[]
  chatHidden?: boolean
  creationRequested?: boolean
}
const fresh = (): Progress => ({
  version: 1,
  step: 'create_project',
  key: randomUUID(),
  paused: false,
  started: false,
  selected: [],
  signal: false,
})
function read(account: string): Progress {
  try {
    const value = JSON.parse(
      localStorage.getItem(`tutorial:1:${account}`) || 'null',
    )
    if (
      value?.version === 1 &&
      tutorialSteps.includes(value.step) &&
      typeof value.key === 'string' &&
      Array.isArray(value.selected)
    )
      return value
  } catch {}
  return fresh()
}
type Guide = {
  state: Progress
  update: (change: Partial<Progress>) => void
  start: () => void
  restart: () => void
  navigate: (path: string) => boolean
}
const Context = createContext<Guide | null>(null)
export const useTutorial = () => useContext(Context)
export function TutorialProvider({
  account,
  navigate,
  children,
}: {
  account: string
  navigate: (path: string) => boolean
  children: ReactNode
}) {
  const [state, setState] = useState(() => read(account))
  const update = (change: Partial<Progress>) =>
    setState((current) => ({ ...current, ...change }))
  useEffect(() => {
    try {
      localStorage.setItem(`tutorial:1:${account}`, JSON.stringify(state))
    } catch {}
  }, [account, state])
  useEffect(() => {
    const created = (event: Event) => {
      const id = (event as CustomEvent).detail?.id
      if (id)
        setState((current) =>
          current.started &&
          !current.paused &&
          current.step === 'create_project'
            ? { ...current, projectId: id, step: 'add_materials' }
            : current,
        )
    }
    addEventListener('tutorial-project-created', created)
    return () => removeEventListener('tutorial-project-created', created)
  }, [])
  useEffect(() => {
    const loaded = (event: Event) => {
      const id = (event as CustomEvent).detail?.id
      setState((current) =>
        current.projectId === id ? { ...current, planRead: true } : current,
      )
    }
    const imported = (event: Event) => { const id = (event as CustomEvent).detail?.id; setState(current => current.projectId === id ? { ...current, planImported: true } : current) }
    addEventListener('tutorial-plan-imported', imported)
    addEventListener('tutorial-plan-loaded', loaded)
    return () => { removeEventListener('tutorial-plan-loaded', loaded); removeEventListener('tutorial-plan-imported', imported) }
  }, [])
  const start = () => {
    const next = state.step === 'complete' ? fresh() : state
    const destination = next.step === 'create_project' || !next.projectId ? '/'
      : next.step === 'add_materials' ? `/projects/${next.projectId}` : `/projects/${next.projectId}/${next.step === 'plan' ? 'plan' : `learn/${next.step}`}`
    if (!navigate(destination)) return
    setState({ ...next, started: true, paused: false, chatHidden: false })
    dispatchEvent(new Event('open-assistant'))
  }
  return (
    <Context.Provider
      value={
        account === 'anonymous'
          ? null
          : {
              state,
              update,
              start,
              restart: () => {
                if (!navigate('/')) return
                setState({ ...fresh(), started: true })
                dispatchEvent(new Event('open-assistant'))
              },
              navigate,
            }
      }
    >
      {children}
    </Context.Provider>
  )
}
export function TutorialStart() {
  const guide = useTutorial()
  return (
    guide && (
      <button className="header-action" type="button" onClick={guide.start}>
        Как пользоваться
      </button>
    )
  )
}
const script: Record<TutorialStep, string> = {
  create_project:
    'Нажмите подсвеченную кнопку «Создать проект». В форме укажите название и подтвердите создание.',
  add_materials:
    'Проект готов! Добавьте учебный набор: план и фотографии. Действие доступно только для пустого проекта.',
  plan: 'Скачайте учебный Excel, загрузите его в план и нажмите «Заменить план». После сохранения продолжите обучение.',
  photos:
    'Выберите учебные фотографии или свои кадры. Сейчас мы только готовим фотографии.',
  result:
    'Рамка неточная: захватывает дерево и обрезает экскаватор. Исправьте её в редакторе, сохраните и перейдите к предупреждению.',
  signals: 'Откройте предупреждение и нажмите «Начать проверку». Статус «В работе» означает, что вы начали разбираться с предупреждением.',
  complete:
    'Готово! Вы создали проект и прошли путь от плана до сигнала. Свой анализ можно запустить отдельно.',
}
export function TutorialGuide() {
  const guide = useTutorial()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [question, setQuestion] = useState('')
  const [replyVisible, setReplyVisible] = useState(false)
  const pendingAttach = useRef<AbortController | null>(null)
  const sendingAttach = useRef(false)
  const { enabled } = useMotionPreference()
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      pendingAttach.current?.abort()
    }
  }, [])
  const state = guide?.state
  const currentKey = useRef(state?.key)
  currentKey.current = state?.key
  const latestState = useRef(state)
  latestState.current = state
  const [spot, setSpot] = useState<DOMRect | null>(null)
  useEffect(() => {
    if (!state?.started || state.paused) {
      setSpot(null)
      return
    }
    let highlighted: HTMLElement | null = null
    const targets: Record<TutorialStep, string[]> = {
      create_project: ['[data-tutorial="project-submit"]', '[data-tutorial="project-name"]', '[data-tutorial="create-project"]'],
      add_materials: ['[data-tutorial="add-materials"]'],
      plan: state.planImported ? ['[data-tutorial="plan-next"]'] : ['[data-tutorial="plan-import"]', '[data-tutorial="plan-example"]', '[data-tutorial="plan-open"]'],
      photos: state.selected.length ? ['[data-tutorial="show-result"]'] : ['[data-tutorial="select-photos"]'],
      result: state.correction?.length ? ['[data-tutorial="open-signal"]'] : ['[data-tutorial="save-correction"]', '[data-tutorial="edit-box"]', '[data-tutorial="edit-annotation"]'],
      signals: ['[data-tutorial="take-signal"]', '[data-tutorial="expand-signal"]'],
      complete: ['[data-tutorial="finish-learning"]'],
    }
    const locate = () => {
      const target = targets[state.step].flatMap(selector => Array.from(document.querySelectorAll<HTMLElement>(selector)))
        .find(element => !element.closest('[hidden], dialog:not([open])') && !element.hasAttribute('disabled')) ?? null
      if (target !== highlighted) {
        highlighted?.removeAttribute('data-tutorial-highlighted')
        highlighted?.removeAttribute('data-tutorial-pulse')
        highlighted = target
        highlighted?.setAttribute('data-tutorial-highlighted', 'true')
        if (enabled) highlighted?.setAttribute('data-tutorial-pulse', 'true')
        highlighted?.scrollIntoView?.({ block: 'nearest', inline: 'nearest', behavior: enabled ? 'smooth' : 'instant' })
      }
      const box = target?.matches('[data-tutorial="edit-box"]') ? target.closest('.annotation-photo-workspace')?.getBoundingClientRect() : target?.getBoundingClientRect()
      const panel = document.querySelector<HTMLElement>('.assistant-chat-panel')
      if (box && panel && !panel.contains(target) && innerWidth > 760) panel.dataset.guideSide = box.left + box.width / 2 > innerWidth / 2 ? 'left' : 'right'
      setSpot(box && box.width > 0 && box.height > 0 ? box : null)
    }
    locate()
    addEventListener('resize', locate)
    addEventListener('scroll', locate, true)
    const observer = new MutationObserver(locate)
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['open', 'hidden', 'disabled'] })
    const resize = typeof ResizeObserver === 'function' ? new ResizeObserver(locate) : null
    resize?.observe(document.body)
    return () => {
      observer.disconnect()
      resize?.disconnect()
      highlighted?.removeAttribute('data-tutorial-highlighted')
      highlighted?.removeAttribute('data-tutorial-pulse')
      document.querySelector<HTMLElement>('.assistant-chat-panel')?.removeAttribute('data-guide-side')
      removeEventListener('resize', locate)
      removeEventListener('scroll', locate, true)
    }
  }, [state?.step, state?.paused, state?.started, state?.planImported, state?.selected.length, state?.correction, enabled])

  useEffect(() => {
    if (!state?.started) return
    const text = 'Как пользоваться приложением?'
    if (state.questionSubmitted || !enabled) {
      setQuestion(text)
      if (!state.questionSubmitted) guide?.update({ questionSubmitted: true })
      return
    }
    guide?.update({ questionSubmitted: true })
    let index = 0
    const timer = setInterval(() => {
      setQuestion(text.slice(0, ++index))
      if (index === text.length) {
        clearInterval(timer)
        guide?.update({ questionSubmitted: true })
      }
    }, 30)
    return () => clearInterval(timer)
  }, [state?.started, state?.key, enabled])
  useEffect(() => {
    if (!state?.started) return
    const revealed = state.revealedSteps ?? []
    const ready = !enabled || revealed.includes(state.step)
    setReplyVisible(ready)
    if (ready) return
    const timer = setTimeout(
      () => {
        setReplyVisible(true)
        guide?.update({ revealedSteps: [...revealed, state.step] })
      },
      !state.questionSubmitted
        ? 'Как пользоваться приложением?'.length * 30 + 450
        : 450,
    )
    return () => clearTimeout(timer)
  }, [state?.key, state?.step, state?.started, enabled])
  useEffect(() => {
    if (state?.paused) pendingAttach.current?.abort()
  }, [state?.paused])
  useEffect(() => () => pendingAttach.current?.abort(), [state?.key])
  if (!guide) return null
  if (!state?.started)
    return (
      <button type="button" className="secondary" onClick={guide.start}>
        Как пользоваться приложением?
      </button>
    )
  const go = (_step: TutorialStep, suffix: string) => {
    if (!state.projectId || state.paused) return false
    return guide.navigate(`/projects/${state.projectId}/${suffix}`)
  }
  async function attach() {
    if (sendingAttach.current || state!.paused) return
    const key = state!.key
    const controller = new AbortController()
    pendingAttach.current = controller
    sendingAttach.current = true
    setBusy(true)
    setError('')
    let timedOut = false
    const timeout = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, 20_000)
    try {
      const response = await fetch(`/api/projects/${state!.projectId}/trial`, {
        method: 'POST',
        credentials: 'same-origin',
        signal: controller.signal,
        headers: { 'Idempotency-Key': key },
      })
      if (!response.ok)
        throw new Error(
          'Не удалось добавить набор. Проверьте доступ владельца и убедитесь, что проект пуст. Повторите с тем же ключом.',
        )
      if (
        alive.current &&
        currentKey.current === key &&
        !latestState.current?.paused &&
        !controller.signal.aborted
      ) {
        if (guide!.navigate(`/projects/${state!.projectId}/plan`))
          guide!.update({ step: 'plan' })
        else
          setError(
            'Набор добавлен. Переход отменён: сохраните текущую работу и повторите. Набор не добавится второй раз.',
          )
      }
    } catch (reason) {
      if (alive.current && currentKey.current === key)
        setError(
          timedOut
            ? 'Добавление набора задерживается. Повторите попытку: используется тот же ключ, данные не продублируются.'
            : controller.signal.aborted
              ? 'Добавление приостановлено. Можно повторить с тем же ключом.'
              : (reason as Error).message,
        )
    } finally {
      clearTimeout(timeout)
      if (pendingAttach.current === controller) {
        pendingAttach.current = null
        sendingAttach.current = false
        if (alive.current) setBusy(false)
      }
    }
  }
  return (
    <>
      {spot && createPortal(<svg className="tutorial-dimmer" aria-hidden="true" width={innerWidth} height={innerHeight} viewBox={`0 0 ${innerWidth} ${innerHeight}`}><path fillRule="evenodd" d={`M0 0H${innerWidth}V${innerHeight}H0Z M${spot.left - 9} ${spot.top - 9}H${spot.right + 9}V${spot.bottom + 9}H${spot.left - 9}Z`} /></svg>, document.body)}
      <span
        aria-hidden="true"
        className="tutorial-spotlight"
        style={
          spot
            ? {
                display: 'block',
                left: spot.left - 4,
                top: spot.top - 4,
                width: spot.width + 8,
                height: spot.height + 8,
              }
            : { display: 'none' }
        }
      />
      <section
        className="tutorial-guide"
        aria-label="Обучение"
        data-tutorial="guide"
      >
        <article className="chat-message chat-message--user">
          <span className="chat-author">Вы</span>
          <div className="chat-bubble">
            <p className="tutorial-question">{question}</p>
          </div>
        </article>
        <div className="tutorial-step-header"><span>Шаг {tutorialSteps.indexOf(state.step) + 1} из 7{state.paused ? ' · Пауза' : ''}</span><details className="tutorial-options"><summary aria-label="Настройки обучения">⋯</summary><div>
          <button onClick={() => guide.update({ paused: true })}>Пауза</button>
          <button onClick={() => guide.update({ started: false, paused: true })}>Прервать обучение</button>
          <button onClick={guide.restart}>Начать заново</button>
          <small>Созданный проект сохранится.</small>
          {tutorialSteps.indexOf(state.step) > 0 && <details><summary>Пройденные шаги</summary>{tutorialSteps.slice(0, tutorialSteps.indexOf(state.step)).map(step => <p key={step}>{script[step]}</p>)}</details>}
        </div></details></div>
        <progress max={7} value={tutorialSteps.indexOf(state.step) + 1} />
        <article className="chat-message chat-message--assistant">
          <span className="chat-author">Помощник · обучение</span>
          <div className="chat-bubble">
            {replyVisible ? (
              <p aria-live="polite">{script[state.step]}</p>
            ) : (
              <span
                role="status"
                aria-label="Помощник готовит учебную подсказку"
                className="chat-typing"
              >
                <span />
                <span />
                <span />
              </span>
            )}
          </div>
        </article>
        {error && <p role="alert">{error}</p>}
        <div className="tutorial-actions">
          {state.paused ? (
            <button onClick={() => guide.update({ paused: false })}>
              Продолжить обучение
            </button>
          ) : (
            <>
              {state.step === 'create_project' && <p className="tutorial-target-hint">Кнопка «Создать проект» подсвечена на странице.</p>}
              {state.step === 'add_materials' && (
                <button data-tutorial="add-materials" disabled={busy} onClick={() => void attach()}>
                  {busy ? 'Добавляем…' : 'Добавить учебный набор'}
                </button>
              )}
              {state.step === 'plan' && (
                <>
                  {location.pathname !== `/projects/${state.projectId}/plan` && <button data-tutorial="plan-open" onClick={() => go('plan', 'plan')}>Открыть план</button>}
                  {location.pathname === `/projects/${state.projectId}/plan` && <button data-tutorial="plan-next"
                    disabled={!state.planImported}
                    onClick={() => {
                      if (
                        state.planImported &&
                        location.pathname ===
                          `/projects/${state.projectId}/plan`
                      ) {
                        if (go('photos', 'learn/photos'))
                          guide.update({ step: 'photos' })
                      }
                    }}
                  >
                    План импортирован, к фотографиям
                  </button>}
                </>
              )}
              {(['photos', 'result', 'signals'] as const).includes(
                state.step as 'photos',
              ) && location.pathname !== `/projects/${state.projectId}/learn/${state.step}` && (
                <button onClick={() => go(state.step, `learn/${state.step}`)}>
                  Продолжить:{' '}
                  {state.step === 'photos'
                    ? 'фотографии'
                    : state.step === 'result'
                      ? 'пример результата'
                      : 'учебный сигнал'}
                </button>
              )}
              {state.step === 'complete' && state.projectId && (
                <>
                  <button data-tutorial="finish-learning"
                    onClick={() =>
                      guide.navigate(`/projects/${state.projectId}`)
                    }
                  >
                    Открыть мой проект
                  </button>

                </>
              )}
            </>
          )}
        </div>
      </section>
    </>
  )
}
type Example = {
  title: string
  found: string
  expected: string
  check: string
  outcome: string
  photos: string[]
  annotations?: { label: string; box: number[] }[]
}
export function TutorialPage({
  projectId,
  page,
  request,
}: {
  projectId: string
  page: string
  request: (path: string) => Promise<any>
}) {
  const guide = useTutorial()
  const [examples, setExamples] = useState<Example[]>()
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [files, setFiles] = useState<File[]>([])
  const [opened, setOpened] = useState(false)
  const [editing, setEditing] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [validating, setValidating] = useState(false)
  const uploadGeneration = useRef(0)
  const activeGuide = useRef(guide)
  activeGuide.current = guide
  useEffect(
    () => () => {
      uploadGeneration.current++
    },
    [],
  )
  async function selectFiles(next: File[]) {
    if (!guide || guide.state.paused || guide.state.projectId !== projectId)
      return
    const generation = ++uploadGeneration.current
    setUploadError('')
    if (next.length > 8) {
      setUploadError(
        'Можно выбрать не более 8 кадров. Предыдущий выбор сохранён.',
      )
      return
    }
    setValidating(true)
    try {
      for (const file of next) {
        const invalid = await validateImage(file)
        if (invalid) {
          if (generation === uploadGeneration.current)
            setUploadError(
              `${file.name}: ${invalid} Предыдущий выбор сохранён.`,
            )
          return
        }
      }
      if (
        generation !== uploadGeneration.current ||
        activeGuide.current?.state.key !== guide.state.key ||
        activeGuide.current?.state.projectId !== projectId ||
        activeGuide.current?.state.paused
      )
        return
      setFiles(next)
      guide.update({ selected: [] })
    } finally {
      if (generation === uploadGeneration.current) setValidating(false)
    }
  }
  useEffect(() => {
    const controller = new AbortController()
    setExamples(undefined)
    setError('')
    void request(`/projects/${projectId}/trial`)
      .then((data) => {
        if (!controller.signal.aborted) setExamples(data.examples)
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            'Учебный набор недоступен. Проверьте доступ к проекту или начните обучение заново.',
          )
      })
    return () => controller.abort()
  }, [projectId, attempt, request])
  const [urls, setUrls] = useState<string[]>([])
  useEffect(() => {
    const next = files.map((file) => URL.createObjectURL(file))
    setUrls(next)
    return () => next.forEach((url) => URL.revokeObjectURL(url))
  }, [files])
  if (error)
    return (
      <main className="page">
        <h1>Обучение</h1>
        <p role="alert">{error}</p>
        <button onClick={() => setAttempt((value) => value + 1)}>
          Повторить
        </button>
        <button onClick={guide?.restart}>Начать заново</button>
      </main>
    )
  if (!examples)
    return (
      <main className="page" role="status">
        Проверяем учебный набор…
      </main>
    )
  const owned = guide?.state.projectId === projectId
  const allowed = examples[0]?.photos ?? []
  const selected = owned
    ? guide.state.selected.filter((url) => allowed.includes(url))
    : []
  const first = examples[0]
  const savedCorrection = owned && validObjects(guide.state.correction) && guide.state.correction.length ? guide.state.correction : null
  const referenceBox = trialFixture.examples[0].corrections[0].corrected_annotations[0].box
  const initialObjects: AnnotationObject[] = [{id:'tutorial-excavator',class_name:'excavator',box:(first?.annotations?.[0]?.box ?? [.1,.1,.5,.6]) as AnnotationObject['box']}]
  const editable = !!owned && !guide.state.paused
  const navigate = (step: TutorialStep) => {
    if (!guide || !editable) return
    if (guide.navigate(`/projects/${projectId}/learn/${step}`))
      guide.update({ step })
  }
  return (
    <main className="page tutorial-page" data-tutorial={page}>
      <h1>
        {page === 'photos'
          ? 'Подготовка фотографий'
          : page === 'result'
            ? 'Учебный результат'
            : 'Учебный сигнал'}
      </h1>
      <p className="attention">
        Иллюстративный пример. Он подготовлен заранее, не является выводом
        модели и не попадёт в историю анализов.
      </p>
      {owned && guide.state.paused && (
        <p role="status">
          Обучение на паузе. Просмотр доступен; продолжите обучение в чате,
          чтобы выполнить шаг.
        </p>
      )}
      {page !== 'photos' && (
        <p>
          Готовый пример «{first?.title}»: результат и разметка относятся к
          учебной фотографии, а не к вашим выбранным кадрам.
        </p>
      )}
      {page === 'photos' ? (
        <>
          <UploadZone
            onFiles={(next) => void selectFiles(next)}
            onCamera={() => {}}
            disabled={!editable || validating}
            cameraDisabled={true}
            invalid={!!uploadError}
            describedBy={uploadError ? 'tutorial-upload-error' : undefined}
          />
          {uploadError && (
            <p id="tutorial-upload-error" role="alert">
              {uploadError}
            </p>
          )}
          <p>
            Готовый пример «{first?.title}» связан только с его учебной
            фотографией. Ваши выбранные кадры сейчас не анализируются.
          </p>
          <a href="/api/trial/project.zip" download>
            Скачать полный проект
          </a>
          <a href="/api/trial/photos.zip" download>
            Скачать фотографии
          </a>
          <button data-tutorial="select-photos"
            disabled={!editable || validating}
            onClick={() => {
              if (!editable) return
              uploadGeneration.current++
              setUploadError('')
              setFiles([])
              if (owned)
                guide.update({
                  selected: first?.photos ?? [],
                })
            }}
          >
            Выбрать учебные фотографии
          </button>
          <div className="tutorial-photos">
            {(urls.length ? urls : selected).map((url, index) => (
              <img
                key={url}
                src={
                  url.startsWith('/projects/') || url.startsWith('/trial/')
                    ? `/api${url}`
                    : url
                }
                alt={`Выбранный кадр ${index + 1}`}
              />
            ))}
          </div>
          {owned && !files.length && !selected.length && (
            <p>После перезагрузки файлы с устройства нужно выбрать заново.</p>
          )}
          <button className="primary" data-tutorial="show-result"
            disabled={
              !editable || validating || !(files.length || selected.length)
            }
            onClick={() => navigate('result')}
          >
            Посмотреть готовый пример
          </button>
        </>
      ) : (
        <>
          <section className="tutorial-result-summary" aria-label="Разбор учебного результата">
            <span className="tutorial-outcome">{first?.outcome}</span>
            <h2>{first?.title}</h2>
            <dl><div><dt>Что обнаружено</dt><dd>{first?.found}</dd></div><div><dt>Что ожидалось</dt><dd>{first?.expected}</dd></div><div><dt>Что проверить</dt><dd>{first?.check}</dd></div></dl>
          </section>
          {page === 'result' && !savedCorrection && <section className="tutorial-correction-intro"><h2>Исправьте неточную рамку</h2><p>Сейчас рамка захватывает дерево. Обведите весь экскаватор: корпус, гусеницы, стрелу и ковш. В редакторе перетащите рамку и её углы; с клавиатуры используйте стрелки, Shift + стрелки меняют размер.</p></section>}
          {editing && page === 'result' ? <AnnotationEditor key={`${projectId}:${guide?.state.key}`} initial={initialObjects} local={{
            storageKey:`tutorial-annotation:${projectId}:${guide?.state.key}`,
            imageUrl:first.photos[0].startsWith('/api/') ? first.photos[0] : `/api${first.photos[0]}`,
            disabled:!editable,
            save: objects => {
              const box = objects[0]?.box
              if (!editable || !validObjects(objects) || objects.length !== 1 || objects[0].class_name !== 'excavator' || !box) throw new Error('На этом снимке нужно выделить один экскаватор.')
              const overlap = Math.max(0, Math.min(box[2],referenceBox[2])-Math.max(box[0],referenceBox[0])) * Math.max(0, Math.min(box[3],referenceBox[3])-Math.max(box[1],referenceBox[1]))
              const union = (box[2]-box[0])*(box[3]-box[1]) + (referenceBox[2]-referenceBox[0])*(referenceBox[3]-referenceBox[1]) - overlap
              if (overlap / union < .7) throw new Error('Рамка пока неточная. Охватите экскаватор целиком, включая стрелу, ковш и гусеницы, и уберите лишний фон.')
              guide!.update({correction:objects});setEditing(false)
            }
          }}/> : <div className="tutorial-photos">
            {first?.photos.map((url, photoIndex) => (
              <div className="annotated-image" key={url}>
                <img
                  src={
                    url.startsWith('/projects/') || url.startsWith('/trial/')
                      ? `/api${url}`
                      : url
                  }
                  alt={first.title}
                />
                {photoIndex === 0 &&
                  (savedCorrection ? savedCorrection.map(object=>({label:'Экскаватор · ваша правка',box:object.box})) : first.annotations?.map(annotation=>({...annotation,label:'Экскаватор · неточная рамка'})))?.map((annotation, index) => (
                    <div
                      key={index}
                      className="object-box"
                      style={{
                        left: `${annotation.box[0] * 100}%`,
                        top: `${annotation.box[1] * 100}%`,
                        width: `${(annotation.box[2] - annotation.box[0]) * 100}%`,
                        height: `${(annotation.box[3] - annotation.box[1]) * 100}%`,
                        pointerEvents: 'none',
                      }}
                    >
                      <span>{annotation.label}</span>
                    </div>
                  ))}
              </div>
            ))}
          </div>}
          {page === 'result' ? (
            <>{!savedCorrection && !editing && <button className="primary" data-tutorial="edit-annotation" disabled={!editable} onClick={()=>setEditing(true)}>Исправить рамку</button>}
            {savedCorrection && <p role="status">Ваша правка сохранена в учебном проекте. Исходная рамка осталась без изменений.</p>}
            {!editing && <button className="primary" data-tutorial="open-signal" disabled={!editable || !savedCorrection} onClick={() => navigate('signals')}>
              Открыть учебное предупреждение
            </button>}</>
          ) : (
            <article className="panel">
              <button data-tutorial="expand-signal"
                aria-expanded={opened}
                onClick={() => setOpened((value) => !value)}
              >
                {first?.outcome} · учебное предупреждение
              </button>
              {opened && (
                <>
                  <p>{first?.check}</p>
                  <p>«Начать проверку» переводит предупреждение в статус «В работе»: вы начали его проверять. Это не означает, что проблема подтверждена или устранена.</p>
                  {owned && guide.state.signal && <p role="status">Статус: В работе</p>}
                  <button className="primary" data-tutorial="take-signal"
                    disabled={!editable || guide.state.signal}
                    onClick={() =>
                      editable &&
                      guide?.update({ signal: true, step: 'complete' })
                    }
                  >
                    {owned && guide.state.signal
                      ? 'Проверка начата'
                      : 'Начать проверку'}
                  </button>
                </>
              )}
            </article>
          )}
        </>
      )}
    </main>
  )
}
