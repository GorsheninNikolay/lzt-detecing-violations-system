import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

type Rect = { top: number; left: number; width: number; height: number }
const visible = (element: Element) => { const box = element.getBoundingClientRect(); return box.width > 0 && box.height > 0 }
const texts = [
  ['Контроль строительства по фотографиям', 'Система помогает увидеть строительную технику и разобраться, что происходит на участке. Распознаются поддерживаемые моделью классы. Плохой ракурс, перекрытия и незнакомая техника ограничивают выводы. Это помощник для проверки, а не подтверждение нарушения.'],
  ['Начните с проекта', 'Выберите проект здесь или создайте новый. Вместе с проектом появится «Основной участок». Проекты общие: коллеги увидят сохранённые анализы и план. Дополнительные участки можно добавить позже.'],
  ['Добавьте фотографии и время', 'Кнопка «Загрузить фото» открывает подготовку анализа. Добавьте один JPEG или PNG либо серию из 2–8 кадров одного участка. Проверьте время съёмки и порядок. Анализ начнётся только после отдельного нажатия «Запустить анализ».'],
  ['Читайте результат с учётом ограничений', 'В «Анализах» хранятся результаты. Техника, гипотеза модели об этапе и подтверждение человека — разные сведения. Не каждая модель показывает рамки или этапы. «Недостаточно данных» не означает, что техники нет. Проверьте основание вывода и фотографии.'],
  ['План и сигналы — по необходимости', 'В плане можно добавить работы и ожидаемую технику, затем явно выбрать сопоставление при загрузке. Сигналы предлагают проверку, но не доказывают нарушение или задержку. Подтверждения человека сохраняются отдельно.'],
]

export type Training = { start: () => Promise<void>; busy: boolean; ready: boolean; allowed: boolean; error: string; runId?: string }

export default function OnboardingTour({ projectId, finish, start, training }: { projectId?: string; finish: (completed: boolean) => void; start: () => void; training?: Training }) {
  const [step, setStep] = useState(0)
  const [target, setTarget] = useState<Rect | null>(null)
  const [position, setPosition] = useState({ left: 16, top: 16, width: 440, maxHeight: 600 })
  const tooltip = useRef<HTMLDivElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const targetElement = useRef<HTMLElement | null>(null)
  const previousFocus = useRef(document.activeElement as HTMLElement | null)
  const finishRef = useRef(finish)
  finishRef.current = finish
  useEffect(() => {
    const previous = previousFocus.current
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); finishRef.current(false) }
      if (event.key === 'Tab') {
        const controls = [...(tooltip.current?.querySelectorAll<HTMLElement>('button:not(:disabled)') ?? [])].filter(visible)
        const actual = targetElement.current
        if (actual && visible(actual) && actual.matches('a,button:not(:disabled),input:not(:disabled),select:not(:disabled)')) controls.push(actual)
        const index = controls.indexOf(document.activeElement as HTMLElement)
        event.preventDefault()
        controls[(index + (event.shiftKey ? -1 : 1) + controls.length) % controls.length]?.focus()
      }
    }
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('keydown', key); previous?.focus() }
  }, [])
  useEffect(() => { if (training?.runId) setStep(3) }, [training?.runId])
  useLayoutEffect(() => {
    const selectors = [
      '.brand > a',
      '[aria-label="Выбрать проект"]',
      training?.ready ? '#submit-action' : projectId ? '.new-analysis-link' : '#project-name, [aria-label="Выбрать проект"]',
      training?.runId ? '#main h1' : projectId ? '.primary-nav a[href$="/analyses"], .bottom-nav a[href$="/analyses"]' : '.primary-nav a[href="/archive"], .bottom-nav a[href="/archive"]',
      projectId ? '.primary-nav a[href$="/plan"], .bottom-nav a[href$="/plan"]' : '[aria-label="Выбрать проект"]',
    ]
    const pick = () => Array.from(document.querySelectorAll<HTMLElement>(selectors[step])).find(visible)
      ?? document.querySelector<HTMLElement>('[aria-label="Выбрать проект"]')
    const actual = pick()
    actual?.scrollIntoView?.({ block:'center', inline:'nearest', behavior:'instant' })
    heading.current?.focus({ preventScroll:true })
    let observer: ResizeObserver | undefined
    const place = () => {
      const element = pick()
      if (!element) return
      if (targetElement.current !== element) {
        if (targetElement.current) observer?.unobserve(targetElement.current)
        observer?.observe(element)
        targetElement.current = element
      }
      let box = element.getBoundingClientRect()
      if (box.bottom <= 0 || box.top >= innerHeight || box.right <= 0 || box.left >= innerWidth) {
        element.scrollIntoView?.({ block:'nearest', inline:'nearest', behavior:'instant' })
        box = element.getBoundingClientRect()
      }
      const left = Math.max(4,Math.min(innerWidth-12,box.left-5)), top = Math.max(4,Math.min(innerHeight-12,box.top-5))
      const width = Math.max(8,Math.min(innerWidth-4,box.right+5)-left), height = Math.max(8,Math.min(innerHeight-4,box.bottom+5)-top)
      setTarget({left,top,width,height})
      const panelWidth = Math.min(460,innerWidth-32)
      const below = innerHeight-(top+height)-28, above = top-28
      const measured = tooltip.current?.scrollHeight ?? 360
      const space = below >= Math.min(measured,420) || below >= above ? below : above
      const maxHeight = Math.max(140,space)
      const panelHeight = Math.min(measured,maxHeight)
      const panelTop = space === below ? top+height+12 : top-panelHeight-12
      setPosition({left:Math.max(16,Math.min(left,innerWidth-panelWidth-16)),top:Math.max(8,panelTop),width:panelWidth,maxHeight})
    }
    place()
    observer = new ResizeObserver(place)
    if (actual) observer.observe(actual)
    if (tooltip.current) observer.observe(tooltip.current)
    const mutations = new MutationObserver(place)
    const main = document.getElementById('main')
    if (main) mutations.observe(main,{childList:true,subtree:true})
    window.addEventListener('resize',place)
    window.addEventListener('scroll',place,true)
    return () => { observer?.disconnect(); mutations.disconnect(); window.removeEventListener('resize',place); window.removeEventListener('scroll',place,true) }
  }, [step,projectId,training?.ready,training?.runId])
  const prerequisite = !projectId && (step===2 || step===4)
  const copy = step===2 && training?.ready ? 'Учебный проект и проверенная фотография готовы. Время съёмки демонстрационное. Нажмите подсвеченную кнопку «Запустить анализ», чтобы выполнить реальное распознавание. Это отдельное действие; «Далее» анализ не запускает.' : step===3 && training?.runId ? 'Это ваш реальный учебный анализ. Дождитесь завершения, затем посмотрите распознанную технику и фотографии ниже. Модель может ошибаться; результат не подтверждает нарушение. При технической ошибке используйте доступное действие повтора.' : prerequisite ? step===2
    ? 'Сначала создайте или выберите проект через подсвеченный элемент. После этого появится «Загрузить фото». Добавьте JPEG/PNG, проверьте порядок и время съёмки. Запуск анализа всегда требует отдельного действия.'
    : 'Для плана и сигналов сначала выберите проект здесь. Внутри проекта появятся разделы «План работ» и «Сигналы». План необязателен; сигнал предлагает проверку, а не доказывает нарушение.'
    : texts[step][1]
  return createPortal(<div className="onboarding-tour">{target && <>
    <div className="tour-dim" style={{left:0,top:0,width:'100%',height:target.top}} />
    <div className="tour-dim" style={{left:0,top:target.top+target.height,width:'100%',bottom:0}} />
    <div className="tour-dim" style={{left:0,top:target.top,width:target.left,height:target.height}} />
    <div className="tour-dim" style={{left:target.left+target.width,top:target.top,right:0,height:target.height}} />
    <div className="tour-spotlight" style={target} aria-hidden="true" />
  </>}<div ref={tooltip} className="tour-tooltip" role="dialog" aria-modal="false" aria-labelledby="tour-heading" style={position}>
    <p className="muted" aria-live="polite">Шаг {step+1} из 5</p><h2 ref={heading} tabIndex={-1} id="tour-heading">{texts[step][0]}</h2><p>{copy}</p>
    {training && step<=2 && !training.ready && <div className="tour-training"><button className="secondary" disabled={training.busy || !training.allowed} onClick={() => { void training.start().then(() => setStep(2)).catch(() => {}) }}>{training.busy ? 'Готовим учебный пример…' : 'Попробовать на примере'}</button><p>Создадим отдельный учебный проект и добавим проверенную фотографию. Анализ запускаете вы.</p>{!training.allowed && !training.busy && <p>Сначала сохраните или завершите текущий черновик. Он останется без изменений.</p>}{training.error && <p className="error" role="alert">{training.error}</p>}</div>}
    <div className="support-actions"><button className="secondary" onClick={() => finish(false)}>Пропустить</button>{step>0 && <button className="secondary" onClick={() => setStep(step-1)}>Назад</button>}<button className="primary" onClick={() => { if(step<4)setStep(step+1);else {finish(true);if(!training?.ready && !training?.runId)start()} }}>{step===4 ? training?.ready || training?.runId ? 'Завершить знакомство' : projectId ? 'Перейти к загрузке фото' : 'Перейти к созданию проекта' : 'Далее'}</button></div>
  </div></div>,document.body)
}
