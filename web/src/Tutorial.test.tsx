import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { useState } from 'react'
import {
  TutorialProvider,
  TutorialGuide,
  TutorialPage,
  TutorialStart,
} from './Tutorial'
import { MotionPreference } from './MotionPreference'
const examples = [
  {
    title: 'Земляные работы',
    found: 'Техника на площадке',
    expected: 'Земляные работы',
    check: 'Сверить с планом',
    outcome: 'Требует проверки',
    photos: ['/projects/p/trial/photos/excavation.jpg'],
  },
]
const request = vi.fn(async () => ({ examples }))
function Harness({
  account = 'a',
  allowNavigate = true,
}: {
  account?: string
  allowNavigate?: boolean
}) {
  const [path, setPath] = useState('/')
  return (
    <MotionPreference>
      <TutorialProvider
        key={account}
        account={account}
        navigate={(next) => {
          if (!allowNavigate) return false
          history.pushState(null, '', next)
          setPath(next)
          return true
        }}
      >
        <TutorialStart />
        <TutorialGuide />
        {path.includes('/learn/') && (
          <TutorialPage
            projectId="p"
            page={path.split('/').at(-1)!}
            request={request}
          />
        )}
      </TutorialProvider>
    </MotionPreference>
  )
}
beforeEach(() => {
  localStorage.clear()
  history.replaceState(null, '', '/')
  vi.stubGlobal('matchMedia', () => ({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
  request.mockClear()
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
it('completes the guide using an explicit creation success, attached materials, authorized photos and a local warning without inference', async () => {
  const fetcher = vi.fn(async (_path: string, _options: object) => ({
    ok: true,
    json: async () => ({ project_id: 'p' }),
  }))
  vi.stubGlobal('fetch', fetcher)
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: 'Как пользоваться' }))
  expect(screen.getByText('Как пользоваться приложением?')).toBeTruthy()
  expect(fetcher).not.toHaveBeenCalled()
  act(() => {
    dispatchEvent(
      new CustomEvent('tutorial-project-created', { detail: { id: 'p' } }),
    )
  })
  fireEvent.click(
    screen.getByRole('button', { name: 'Добавить учебный набор' }),
  )
  await screen.findByRole('button', { name: 'План посмотрел, к фотографиям' })
  expect(
    screen
      .getByRole('button', { name: 'План посмотрел, к фотографиям' })
      .hasAttribute('disabled'),
  ).toBe(true)
  expect(location.pathname).toBe('/projects/p/plan')
  act(() => {
    dispatchEvent(
      new CustomEvent('tutorial-plan-loaded', { detail: { id: 'p' } }),
    )
  })
  fireEvent.click(
    screen.getByRole('button', { name: 'План посмотрел, к фотографиям' }),
  )
  await screen.findByRole('button', { name: 'Выбрать учебные фотографии' })
  fireEvent.click(
    screen.getByRole('button', { name: 'Выбрать учебные фотографии' }),
  )
  expect(screen.getByAltText('Выбранный кадр 1').getAttribute('src')).toBe(
    '/api/projects/p/trial/photos/excavation.jpg',
  )
  fireEvent.click(
    screen.getByRole('button', { name: 'Посмотреть готовый пример' }),
  )
  await screen.findByRole('button', { name: 'Исправить рамку' })
  fixTutorialBox()
  fireEvent.click(
    screen.getByRole('button', { name: 'Открыть учебное предупреждение' }),
  )
  await screen.findByRole('button', {
    name: 'Требует проверки · учебное предупреждение',
  })
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Требует проверки · учебное предупреждение',
    }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Начать проверку' }))
  expect(screen.getByRole('button', { name: 'Проверка начата' })).toBeTruthy()
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(fetcher.mock.calls[0][0]).toBe('/api/projects/p/trial')
  expect(request).toHaveBeenCalledWith('/projects/p/trial')
})
it('preserves step and retry key, rejects unrelated creation while paused and fences accounts', async () => {
  const fetcher = vi
    .fn()
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValue({ ok: true })
  vi.stubGlobal('fetch', fetcher)
  const view = render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: 'Как пользоваться' }))
  const options = document.querySelector<HTMLDetailsElement>('.tutorial-options')!; options.open = true
  fireEvent.click(screen.getByRole('button', { name: 'Пауза' })); options.open = false
  act(() => {
    dispatchEvent(
      new CustomEvent('tutorial-project-created', { detail: { id: 'wrong' } }),
    )
  })
  fireEvent.click(screen.getByRole('button', { name: 'Продолжить обучение' }))
  expect(
    screen.getByText('Кнопка «Создать проект» подсвечена на странице.'),
  ).toBeTruthy()
  act(() => {
    dispatchEvent(
      new CustomEvent('tutorial-project-created', { detail: { id: 'p' } }),
    )
  })
  fireEvent.click(
    screen.getByRole('button', { name: 'Добавить учебный набор' }),
  )
  await screen.findByRole('alert')
  const key = fetcher.mock.calls[0][1].headers['Idempotency-Key']
  view.unmount()
  render(<Harness />)
  fireEvent.click(
    screen.getByRole('button', { name: 'Добавить учебный набор' }),
  )
  await screen.findByRole('button', { name: 'План посмотрел, к фотографиям' })
  expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).toBe(key)
  cleanup()
  render(<Harness account="b" />)
  expect(screen.queryByRole('button', { name: 'Открыть план' })).toBeNull()
  expect(
    screen.getByRole('button', { name: 'Как пользоваться приложением?' }),
  ).toBeTruthy()
})
it('retains an inaccessible sample on a retry screen without showing example content', async () => {
  request.mockRejectedValueOnce(new Error('forbidden'))
  render(<TutorialPage projectId="p" page="result" request={request} />)
  await screen.findByRole('alert')
  expect(screen.queryByText('Техника на площадке')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  await waitFor(() =>
    expect(screen.getByText('Техника на площадке')).toBeTruthy(),
  )
})
it('ignores an attach response after restarting the guide', async () => {
  let resolve!: (result: { ok: boolean }) => void
  vi.stubGlobal(
    'fetch',
    vi.fn(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    ),
  )
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: 'Как пользоваться' }))
  act(() => {
    dispatchEvent(
      new CustomEvent('tutorial-project-created', { detail: { id: 'p' } }),
    )
  })
  fireEvent.click(
    screen.getByRole('button', { name: 'Добавить учебный набор' }),
  )
  document.querySelector<HTMLDetailsElement>('.tutorial-options')!.open = true
  fireEvent.click(screen.getByRole('button', { name: 'Начать заново' }))
  await act(async () => resolve({ ok: true }))
  expect(
    screen.getByText('Кнопка «Создать проект» подсвечена на странице.'),
  ).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Открыть план' })).toBeNull()
})
function seed(step: string, extra: object = {}) {
  localStorage.setItem(
    'tutorial:1:a',
    JSON.stringify({
      version: 1,
      step,
      key: 'same-key',
      projectId: 'p',
      started: true,
      paused: false,
      selected: [],
      signal: false,
      ...extra,
    }),
  )
}
it('leaves the step and creation intent unchanged when guarded navigation is cancelled', () => {
  seed('plan', { planRead: true })
  history.replaceState(null, '', '/projects/p/plan')
  const view = render(<Harness allowNavigate={false} />)
  fireEvent.click(
    screen.getByRole('button', { name: 'План посмотрел, к фотографиям' }),
  )
  expect(JSON.parse(localStorage.getItem('tutorial:1:a')!).step).toBe('plan')
  view.unmount()
  seed('create_project')
  render(<Harness allowNavigate={false} />)
  fireEvent.click(screen.getByRole('button', {name:'Как пользоваться'}))
  expect(
    JSON.parse(localStorage.getItem('tutorial:1:a')!).creationRequested,
  ).toBeUndefined()
})
it('keeps an attached set retryable when the plan transition is cancelled', async () => {
  seed('add_materials')
  const fetcher = vi.fn().mockResolvedValue({ ok: true })
  vi.stubGlobal('fetch', fetcher)
  render(<Harness allowNavigate={false} />)
  fireEvent.click(
    screen.getByRole('button', { name: 'Добавить учебный набор' }),
  )
  await screen.findByRole('alert')
  expect(JSON.parse(localStorage.getItem('tutorial:1:a')!).step).toBe(
    'add_materials',
  )
  fireEvent.click(
    screen.getByRole('button', { name: 'Добавить учебный набор' }),
  )
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
  expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).toBe('same-key')
})
it('times out attach and retries the same key without concurrent duplicate requests', async () => {
  vi.useFakeTimers()
  seed('add_materials')
  const fetcher = vi.fn(
    (_path: string, options: RequestInit) =>
      new Promise((_done, reject) =>
        options.signal?.addEventListener('abort', () =>
          reject(new DOMException('Aborted', 'AbortError')),
        ),
      ),
  )
  vi.stubGlobal('fetch', fetcher)
  render(<Harness />)
  const button = screen.getByRole('button', { name: 'Добавить учебный набор' })
  fireEvent.click(button)
  fireEvent.click(button)
  expect(fetcher).toHaveBeenCalledTimes(1)
  await act(async () => {
    vi.advanceTimersByTime(20_000)
  })
  expect(screen.getByRole('alert').textContent).toContain('задерживается')
  fireEvent.click(
    screen.getByRole('button', { name: 'Добавить учебный набор' }),
  )
  expect(fetcher.mock.calls[1][1].headers).toEqual({
    'Idempotency-Key': 'same-key',
  })
})
it('allows reading a paused warning without completing it', async () => {
  seed('signals')
  render(<Harness />)
  fireEvent.click(
    screen.getByRole('button', { name: 'Продолжить: учебный сигнал' }),
  )
  await screen.findByRole('button', {
    name: 'Требует проверки · учебное предупреждение',
  })
  const options = document.querySelector<HTMLDetailsElement>('.tutorial-options')!; options.open = true
  fireEvent.click(screen.getByRole('button', { name: 'Пауза' })); options.open = false
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Требует проверки · учебное предупреждение',
    }),
  )
  const action = screen.getByRole('button', { name: 'Начать проверку' })
  expect(action.hasAttribute('disabled')).toBe(true)
  fireEvent.click(action)
  expect(JSON.parse(localStorage.getItem('tutorial:1:a')!).signal).toBe(false)
})
it('selects only the named tutorial example and preserves it on invalid uploads', async () => {
  seed('photos')
  request.mockResolvedValueOnce({
    examples: [
      ...examples,
      {
        ...examples[0],
        title: 'Обзор',
        photos: ['/projects/p/trial/photos/overview.jpg'],
      },
    ],
  })
  render(<Harness />)
  fireEvent.click(
    screen.getByRole('button', { name: 'Продолжить: фотографии' }),
  )
  await screen.findByRole('button', { name: 'Выбрать учебные фотографии' })
  fireEvent.click(
    screen.getByRole('button', { name: 'Выбрать учебные фотографии' }),
  )
  expect(screen.getAllByAltText(/Выбранный кадр/)).toHaveLength(1)
  const input = document.getElementById('images')!
  fireEvent.change(input, {
    target: { files: [new File(['text'], 'bad.txt', { type: 'text/plain' })] },
  })
  await screen.findByRole('alert')
  expect(screen.getByAltText('Выбранный кадр 1')).toBeTruthy()
  fireEvent.change(input, {
    target: {
      files: Array.from(
        { length: 9 },
        () => new File(['x'], 'a.jpg', { type: 'image/jpeg' }),
      ),
    },
  })
  expect(screen.getByRole('alert').textContent).toContain('не более 8')
  expect(screen.getByAltText('Выбранный кадр 1')).toBeTruthy()
})

it('opens the saved task when starting learning and keeps management actions in the closed menu', () => {
  seed('add_materials', { paused: true })
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', {name:'Как пользоваться'}))
  expect(location.pathname).toBe('/projects/p')
  expect(screen.getByRole('button', {name:'Добавить учебный набор'})).toBeTruthy()
  const pause=screen.getByRole('button', {name:'Пауза'})
  expect(pause.closest('details')?.open).toBe(false)
})

it.each([false, true])('dims around the target and respects reduced motion=%s, then clears both on pause', async reduced => {
  vi.stubGlobal('matchMedia', () => ({ matches: reduced, addEventListener:vi.fn(), removeEventListener:vi.fn() }))
  vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockReturnValue({x:100,y:50,left:100,top:50,right:300,bottom:100,width:200,height:50,toJSON:()=>({})})
  render(<><button data-tutorial="create-project">Начать проект</button><Harness /></>)
  fireEvent.click(screen.getByRole('button',{name:'Как пользоваться'}))
  const target=screen.getByRole('button',{name:'Начать проект'})
  await waitFor(()=>expect(target.getAttribute('data-tutorial-highlighted')).toBe('true'))
  expect(target.hasAttribute('data-tutorial-pulse')).toBe(!reduced)
  expect(document.querySelector('.tutorial-dimmer path')?.getAttribute('d')).toContain('M91 41H309V109H91Z')
  document.querySelector<HTMLDetailsElement>('.tutorial-options')!.open=true
  fireEvent.click(screen.getByRole('button',{name:'Пауза'}))
  await waitFor(()=>expect(document.querySelector('.tutorial-dimmer')).toBeNull())
  expect(target.hasAttribute('data-tutorial-highlighted')).toBe(false)
  expect(target.hasAttribute('data-tutorial-pulse')).toBe(false)
})

function fixTutorialBox() {
  fireEvent.click(screen.getByRole('button',{name:'Исправить рамку'}))
  const image=screen.getByAltText('Кадр для исправления объектов')
  Object.defineProperties(image,{naturalWidth:{value:1215,configurable:true},naturalHeight:{value:811,configurable:true}})
  fireEvent.load(image)
  const details=screen.getByText('Точные координаты').closest('details')!;details.open=true
  for(const [label,value] of [['Справа','.675'],['Снизу','.665'],['Слева','.255'],['Сверху','.17']]) {
    const input=screen.getByLabelText(label);fireEvent.change(input,{target:{value}});fireEvent.blur(input)
  }
  fireEvent.click(screen.getByRole('button',{name:'Сохранить учебную правку'}))
}

it('requires a real correction, rejects a misplaced box and restores the saved correction without posting real annotations', async () => {
  seed('result')
  const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher)
  const view=render(<Harness />)
  fireEvent.click(screen.getByRole('button',{name:'Продолжить: пример результата'}))
  fireEvent.click(await screen.findByRole('button',{name:'Исправить рамку'}))
  const image=screen.getByAltText('Кадр для исправления объектов')
  Object.defineProperties(image,{naturalWidth:{value:1215,configurable:true},naturalHeight:{value:811,configurable:true}});fireEvent.load(image)
  expect((screen.getByRole('button',{name:'Сохранить учебную правку'}) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.keyDown(screen.getByRole('button',{name:'Объект 1: Экскаватор'}),{key:'ArrowRight'})
  fireEvent.click(screen.getByRole('button',{name:'Сохранить учебную правку'}))
  expect(await screen.findByText(/Рамка пока неточная/)).toBeTruthy()
  expect(JSON.parse(localStorage.getItem('tutorial:1:a')!).correction).toBeUndefined()
  screen.getByText('Точные координаты').closest('details')!.open=true
  for(const [label,value] of [['Справа','.675'],['Снизу','.665'],['Слева','.255'],['Сверху','.17']]){const field=screen.getByLabelText(label);fireEvent.change(field,{target:{value}});fireEvent.blur(field)}
  fireEvent.click(screen.getByRole('button',{name:'Сохранить учебную правку'}))
  expect(JSON.parse(localStorage.getItem('tutorial:1:a')!).correction[0].box).toEqual([.255,.17,.675,.665])
  view.unmount();history.replaceState(null,'','/');render(<Harness />)
  fireEvent.click(screen.getByRole('button',{name:'Продолжить: пример результата'}))
  const next=await screen.findByRole('button',{name:'Открыть учебное предупреждение'}) as HTMLButtonElement
  expect(next.disabled).toBe(false)
  expect(screen.queryByRole('button',{name:'Исправить рамку'})).toBeNull()
  expect(screen.getByText('Экскаватор · ваша правка')).toBeTruthy()
  expect(fetcher).not.toHaveBeenCalled()
})
