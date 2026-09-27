import { createRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SignalsPage from './SignalsPage'

const base = {
  zone_id: 'zone-1', revision_id: 'revision-1', work_entry_id: null, state: 'new', comment: '',
  basis: {}, created_at: '2026-09-25T11:00:00Z', project_name: 'Объект А', zone_name: 'Север',
} as const
const signal = (id: string, kind = 'completion_unconfirmed', extra = {}) => ({ ...base, id, kind, run_id: null, ...extra })
const json = (value: unknown) => ({ ok: true, json: async () => value })
const page = () => render(<SignalsPage heading={createRef<HTMLHeadingElement>()} onOpenRun={vi.fn()} />)

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); delete (URL as unknown as { createObjectURL?: unknown }).createObjectURL; delete (URL as unknown as { revokeObjectURL?: unknown }).revokeObjectURL })

describe('SignalsPage', () => {
  it('shows twenty rows, loads more, and filters by state', async () => {
    const records = Array.from({ length: 21 }, (_, index) => signal(`signal-${index}`))
    const fetchMock = vi.fn(async (url: string) => json({ new_count: 21, signals: url.includes('state=closed') ? [] : records }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    page()
    await waitFor(() => expect(document.querySelectorAll('.signals-row')).toHaveLength(20))
    await user.click(screen.getByRole('button', { name: 'Показать ещё' }))
    expect(document.querySelectorAll('.signals-row')).toHaveLength(21)
    await user.selectOptions(screen.getByLabelText('Показать'), 'closed')
    expect(await screen.findByText('Сигналов по выбранному фильтру нет.')).toBeTruthy()
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/signals?state=closed')).toBe(true)
  })

  it('loads the saved plan revision and a real preview, then revokes its URL', async () => {
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:signal-preview') })
    const revoke = vi.fn()
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revoke })
    const record = signal('signal-1', 'expected_equipment_missing', {
      run_id: 'run-1', revision_id: 'revision-2', plan_revision_number: 2, work_entry_id: 'entry-1', work_title: 'Подготовка',
      preview: { input_id: 'input-1', ordinal: 0, artifact_id: 'artifact-1' }, basis: { supporting_input_ids: ['input-1'], class_name: 'excavator' },
    })
    const fetchMock = vi.fn(async (url: string) => url === '/api/signals' ? json({ new_count: 1, signals: [record] })
      : url === '/api/runs/run-1/artifacts/artifact-1' ? { ok: true, blob: async () => new Blob(['image']) }
        : url === '/api/runs/run-1' ? json({ state: 'succeeded', inputs: [{ input_id: 'input-1' }], result_projection: { outcome: 'check_requested' } })
          : url === '/api/zones/zone-1/plan?revision=2' ? json({ revision_id: 'revision-2', revision_number: 2, entries: [{ id: 'entry-1', state: 'active', stage_key: 'excavation', starts_at: '2026-09-25T08:00:00Z', ends_at: '2026-09-25T18:00:00Z', expected_equipment: ['excavator'] }] })
            : { ok: false })
    vi.stubGlobal('fetch', fetchMock)
    const view = page()
    expect(await screen.findByAltText('Поддерживающий кадр 1')).toHaveProperty('src', 'blob:signal-preview')
    expect(await screen.findByText('Ожидается: Экскаватор')).toBeTruthy()
    expect(screen.getByText(/Итог: Рекомендована проверка человеком/)).toBeTruthy()
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/zones/zone-1/plan?revision=2')).toBe(true)
    view.unmount()
    expect(revoke).toHaveBeenCalledWith('blob:signal-preview')
  })

  it('labels a fallback analysis frame and rejects a plan with the wrong revision ID', async () => {
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:fallback') })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    const record = signal('signal-1', 'stage_plan_mismatch', {
      run_id: 'run-1', revision_id: 'recorded-revision', plan_revision_number: 1, state: 'closed',
      preview: { input_id: 'input-1', ordinal: 2, artifact_id: 'artifact-1' },
    })
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/signals' ? json({ new_count: 0, signals: [record] })
      : url.includes('/artifacts/') ? { ok: true, blob: async () => new Blob(['image']) }
        : url.includes('/plan?') ? json({ revision_id: 'different-revision', revision_number: 1, entries: [{ id: 'wrong-entry' }] })
          : json({ state: 'succeeded', inputs: [], result_projection: { outcome: 'no_check' } })))
    page()
    expect(await screen.findByAltText('Кадр анализа 3')).toBeTruthy()
    expect(await screen.findByText('Полученная ревизия плана не совпадает с сигналом.')).toBeTruthy()
    expect(screen.queryByText('Работа 1')).toBeNull()
    expect(screen.getByText('Закрыт означает завершение ручной обработки, а не подтверждение безопасности.')).toBeTruthy()
  })

  it('preserves each comment across selection and filtering, including a failed save', async () => {
    const first = signal('signal-1')
    const second = signal('signal-2', 'insufficient_observations')
    let failSave = true
    const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') {
        if (failSave) { failSave = false; return { ok: false } }
        return json(JSON.parse(String(options.body)))
      }
      return json({ new_count: 2, signals: [first, second] })
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    page()
    await screen.findByRole('button', { name: /Завершение не подтверждено.*Север/ })
    await user.type(screen.getByLabelText('Комментарий'), 'Первый черновик')
    await user.click(screen.getByRole('button', { name: /Недостаточно наблюдений.*Север/ }))
    await user.type(screen.getByLabelText('Комментарий'), 'Второй черновик')
    await user.selectOptions(screen.getByLabelText('Показать'), 'new')
    await screen.findByRole('button', { name: /Завершение не подтверждено.*Север/ })
    await user.click(screen.getByRole('button', { name: /Недостаточно наблюдений.*Север/ }))
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('value', 'Второй черновик')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByText('Не удалось сохранить сигнал. Комментарий остался в черновике.')).toBeTruthy()
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('value', 'Второй черновик')
    await user.click(screen.getByRole('button', { name: /Завершение не подтверждено.*Север/ }))
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('value', 'Первый черновик')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, options]) => options?.method === 'PATCH')).toHaveLength(2))
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === '/api/signals?state=new').length).toBeGreaterThan(1))
  })

  it('keeps a submitted draft stable while its save is pending', async () => {
    let finishSave!: (response: ReturnType<typeof json>) => void
    const pendingSave = new Promise<ReturnType<typeof json>>(resolve => { finishSave = resolve })
    vi.stubGlobal('fetch', vi.fn((_url: string, options?: RequestInit) => options?.method === 'PATCH'
      ? pendingSave : Promise.resolve(json({ new_count: 1, signals: [signal('signal-1')] }))))
    const user = userEvent.setup()
    page()
    await screen.findByRole('button', { name: /Завершение не подтверждено.*Север/ })
    await user.type(screen.getByLabelText('Комментарий'), 'Черновик')
    await user.selectOptions(screen.getByLabelText('Состояние'), 'in_progress')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('disabled', true)
    expect(screen.getByLabelText('Состояние')).toHaveProperty('disabled', true)
    finishSave(json({ state: 'in_progress', comment: 'Черновик' }))
    await waitFor(() => expect(screen.getByLabelText('Комментарий')).toHaveProperty('disabled', false))
    expect(screen.getByLabelText('Комментарий')).toHaveProperty('value', 'Черновик')
  })

  it('aborts old detail reads and ignores responses that arrive after selection changes', async () => {
    let releaseOld!: () => void
    const old = new Promise<void>(resolve => { releaseOld = resolve })
    const first = signal('signal-1', 'expected_equipment_missing', { run_id: 'run-1', revision_id: 'revision-1', plan_revision_number: 1 })
    const second = signal('signal-2', 'stage_plan_mismatch', { run_id: 'run-2', revision_id: 'revision-2', plan_revision_number: 2 })
    const fetchMock = vi.fn(async (url: string, _options?: RequestInit) => {
      if (url === '/api/signals') return json({ new_count: 2, signals: [first, second] })
      if (url.includes('run-1') || url.includes('revision=1')) {
        await old
        return url.includes('revision=1') ? json({ revision_id: 'revision-1', revision_number: 1, entries: [{ id: 'old', state: 'active', starts_at: '2026-09-25T08:00:00Z', ends_at: '2026-09-25T18:00:00Z', expected_equipment: ['dump_truck'] }] }) : json({ state: 'succeeded', inputs: [], result_projection: { outcome: 'no_check' } })
      }
      return url.includes('revision=2') ? json({ revision_id: 'revision-2', revision_number: 2, entries: [{ id: 'new', state: 'active', starts_at: '2026-09-25T08:00:00Z', ends_at: '2026-09-25T18:00:00Z', expected_equipment: ['excavator'] }] }) : json({ state: 'succeeded', inputs: [], result_projection: { outcome: 'check_requested' } })
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    page()
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url === '/api/runs/run-1')).toBe(true))
    await user.click(screen.getByRole('button', { name: /Этап расходится с планом.*Север/ }))
    expect(await screen.findByText('Ожидается: Экскаватор')).toBeTruthy()
    expect(fetchMock.mock.calls.find(([url]) => url === '/api/runs/run-1')?.[1]?.signal?.aborted).toBe(true)
    releaseOld()
    await waitFor(() => expect(screen.queryByText('Ожидается: Самосвал')).toBeNull())
    expect(screen.getByText(/Итог: Рекомендована проверка человеком/)).toBeTruthy()
  })

  it('places selected details directly after its row on a phone and explains a calendar signal', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 390 })
    vi.stubGlobal('fetch', vi.fn(async () => json({ new_count: 1, signals: [signal('signal-1', 'completion_unconfirmed', { basis: { due_at: '2026-09-25T10:00:00Z' } })] })))
    page()
    const row = await screen.findByRole('button', { name: /Завершение не подтверждено.*Север/ })
    const item = row.closest('li')!
    expect(within(item).getByRole('article')).toBeTruthy()
    expect(within(item).getByText('Сигнал сформирован по сроку плана. Связанных кадров нет.')).toBeTruthy()
    expect(within(item).getByText('Анализ не связан. Кадров нет.')).toBeTruthy()
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 })
    fireEvent(window, new Event('resize'))
  })
})

it('uses server totals independently of the visible list and refreshes them after patch',async()=>{
 let closed=false
 vi.stubGlobal('fetch',vi.fn(async (_url:string,options?:RequestInit)=>{
  if(options?.method==='PATCH'){closed=true;return json({state:'closed',comment:'Проверено'})}
  return json({new_count:closed?0:1,summary:{open_count:closed?0:520,attention_count:closed?0:500,insufficient_data_count:closed?0:20},signals:[signal('signal-1','completion_unconfirmed',{state:closed?'closed':'new'})]})
 }))
 const user=userEvent.setup();page()
 const summary=await screen.findByLabelText('Сводка открытых сигналов')
 expect(summary.textContent).toContain('Всего открытых: 520')
 expect(summary.textContent).toContain('Требуют проверки: 500')
 await user.selectOptions(screen.getByLabelText('Показать'),'closed')
 expect(summary.textContent).toContain('Недостаточно данных: 20')
 await screen.findByLabelText('Состояние')
 await user.selectOptions(screen.getByLabelText('Состояние'),'closed')
 await user.click(screen.getByRole('button',{name:'Сохранить'}))
 expect(await screen.findByText('Открытых сигналов нет')).toBeTruthy()
})

it('opens shared photo viewer, switches frames, toggles boxes and restores comment and focus',async()=>{
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> 'blob:photo')})
 Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()})
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');this.querySelector('button')?.focus()}
 HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');this.dispatchEvent(new Event('close'))}
 const record=signal('photo','equipment_not_planned',{run_id:'run-1',basis:{class_name:'truck',supporting_input_ids:['f2']}})
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>url==='/api/signals'?json({signals:[record],new_count:1}):url.includes('/artifacts/')?{ok:true,blob:async()=>new Blob(['photo'])}:json({state:'succeeded',inputs:[{input_id:'f1',ordinal:0,artifact_id:'a1',sha256:'s1'},{input_id:'f2',ordinal:1,artifact_id:'a2',sha256:'s2'}],objects:[{input_id:'f2',class_name:'truck',box:[.1,.1,.6,.6],invocation_id:'i'}]})))
 const user=userEvent.setup();page()
 const open=await screen.findByRole('button',{name:'Открыть фото'})
 await user.type(screen.getByLabelText('Комментарий'),'Проверю назначение')
 await user.click(open)
 await user.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Следующий кадр'}))
 expect(within(screen.getByRole('dialog')).getByRole('status').textContent).toContain('Кадр 2 из 2')
 await user.click(within(screen.getByRole('dialog')).getByLabelText('Рамки объектов'))
 expect(screen.getByRole('dialog').querySelector('.object-box')).toBeNull()
 await user.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Закрыть'}))
 expect(screen.getByLabelText('Комментарий')).toHaveProperty('value','Проверю назначение')
 expect(document.activeElement).toBe(open)
 expect(screen.getByText('Поддерживающий кадр · 2 из 2')).toBeTruthy()
})

it.each([
 ['expected_equipment_missing','Сверьте технику с текущей работой'],
 ['equipment_not_planned','Уточните назначение техники'],
 ['stage_plan_mismatch','Сверьте фактическую работу'],
 ['completion_unconfirmed','Уточните завершение'],
 ['insufficient_observations','Добавьте минимум три пригодных кадра'],
])('explains %s and its next action in Russian without a photograph',async(kind,action)=>{
 vi.stubGlobal('fetch',vi.fn(async()=>json({signals:[signal('signal-1',kind)],new_count:1})))
 page()
 expect(await screen.findByText(new RegExp(action))).toBeTruthy()
 expect(screen.getByText('Связанных фотографий нет. Основание — сохранённая ревизия плана ниже.')).toBeTruthy()
})

it.each([
 [{ risk: { cause: 'stage_plan_mismatch', text: 'Видимый этап расходится с планом', recommended_check: 'Уточнить этап у команды' } }, 'Гипотеза ИИ об этапе расходится с этапами активных работ сохранённого плана. Она требует проверки человеком.', 'Проверьте гипотезу по фотографиям с командой площадки', false],
 [{ confirmed_stage: 'excavation', planned_stages: ['concrete'], rule_revision: 'confirmed-stage-v2' }, 'Этап, подтверждённый человеком, расходится с этапами активных работ сохранённого плана.', 'Сверьте фактическую работу с планом', true],
 [{}, 'В основании сигнала указано возможное расхождение этапа с активными работами сохранённого плана.', 'Сверьте фактическую работу с планом', false],
] as const)('explains a stage mismatch according to its saved basis %#', async (basis, explanation, action, confirmed) => {
 vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/signals'
  ? json({ signals: [signal('stage', 'stage_plan_mismatch', { run_id: 'run-1', basis })], new_count: 1 })
  : json({ state: 'succeeded', inputs: [], result_projection: { outcome: 'check_requested' } })))
 page()
 expect(await screen.findByText(explanation)).toBeTruthy()
 expect(screen.getByText(new RegExp(action))).toBeTruthy()
 expect(Boolean(screen.queryByText(/Этап, подтверждённый человеком/))).toBe(confirmed)
 expect(Boolean(screen.queryByText(/Подтверждённый этап: Земляные работы/))).toBe(confirmed)
})

it.each([false,true])('distinguishes pending and failed photo reads while retaining valid preview=%s',async(hasPreview)=>{
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> 'blob:photo')})
 Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()})
 let reject!:()=>void
 const pending=new Promise((_resolve,rejectRead)=>{reject=()=>rejectRead(new Error('offline'))})
 const record=signal('photo','equipment_not_planned',{run_id:'run-1',...(hasPreview?{preview:{input_id:'f1',ordinal:0,artifact_id:'a1'}}:{})})
 const fetchMock=vi.fn(async(url:string)=>url==='/api/signals'?json({signals:[record],new_count:1}):url.includes('/artifacts/')?{ok:true,blob:async()=>new Blob(['photo'])}:pending)
 vi.stubGlobal('fetch',fetchMock);page()
 expect(await screen.findByText('Загружаем фотографии анализа…')).toBeTruthy()
 expect(screen.queryByText(/Связанных фотографий нет/)).toBeNull()
 if(hasPreview)expect(screen.getByRole('button',{name:'Открыть фото'})).toBeTruthy()
 reject()
 const retry=await screen.findByRole('button',{name:'Повторить загрузку фотографий'})
 expect(screen.queryByText(/Связанных фотографий нет/)).toBeNull()
 if(hasPreview)expect(screen.getByRole('button',{name:'Открыть фото'})).toBeTruthy()
 await userEvent.setup().click(retry)
 await waitFor(()=>expect(fetchMock.mock.calls.filter(([url])=>url==='/api/runs/run-1')).toHaveLength(2))
})

it('uses completed projection metadata and discloses saved equipment policies',async()=>{
 Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> 'blob:photo')})
 Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()})
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
 HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');this.dispatchEvent(new Event('close'))}
 const record=signal('photo','equipment_not_planned',{run_id:'run-1',plan_revision_number:1,work_entry_id:'entry-1',basis:{class_name:'truck'}})
 const fetchMock=vi.fn(async(url:string)=>url==='/api/signals'?json({signals:[record],new_count:1}):url.endsWith('/native')?{ok:true,text:async()=>'{"observer":"saved"}'}:url.includes('/artifacts/')?{ok:true,blob:async()=>new Blob(['photo'])}:url.includes('/plan?')?json({revision_id:'revision-1',revision_number:1,entries:[{id:'entry-1',state:'active',stage_key:'excavation',starts_at:'2026-09-26T10:00:00Z',ends_at:'2026-09-26T18:00:00Z',expected_equipment:['excavator'],allowed_equipment:['dump_truck'],excluded_equipment:['truck']}]}):json({state:'succeeded',context:{period:'raw period'},profile_snapshot:{adapter:{code:'saved-adapter'}},inputs:[{input_id:'f1',ordinal:0,artifact_id:'raw-artifact',sha256:'source-sha'}],observations:[{input_id:'f1',ordinal:0,class_name:'excavator',state:'detected',source_artifact_id:'raw-artifact'}],result_projection:{outcome:'check_requested',context:{period:'saved projection period'},series:{usable_input_ids:['f1']},frames:[{input_id:'f1',ordinal:2,class_name:'truck',state:'detected',source_artifact_id:'projected-artifact'}]},native_evidence_by_frame:[{input_id:'f1',artifact_id:'native',ordinal:2,sha256:'native-sha',invocation_id:'invocation',profile_id:'saved-profile',profile_revision:7}]}))
 vi.stubGlobal('fetch',fetchMock);const user=userEvent.setup();page()
 await user.click(await screen.findByRole('button',{name:'Открыть фото'}))
 const viewer=screen.getByRole('dialog')
 expect(within(viewer).getByText('Номер кадра: 3. Пригодность: пригоден.')).toBeTruthy()
 expect(within(viewer).getByText('Наблюдения: Грузовик: Обнаружен.')).toBeTruthy()
 expect(within(viewer).getByText('Период: saved projection period.')).toBeTruthy()
 expect(within(viewer).getByText('saved-adapter')).toBeTruthy()
 expect(within(viewer).getByText('saved-profile')).toBeTruthy()
 expect(fetchMock.mock.calls.some(([url])=>url.endsWith('/projected-artifact'))).toBe(true)
 await user.click(within(viewer).getByRole('button',{name:'Закрыть'}))
 expect(screen.getByText(/явно не предусмотрено Грузовик/)).toBeTruthy()
 expect(screen.getByText('Ожидается: Экскаватор')).toBeTruthy()
 expect(screen.getByText('Допускается: Самосвал')).toBeTruthy()
 expect(screen.getByText('Явно не предусмотрено: Грузовик')).toBeTruthy()
})
