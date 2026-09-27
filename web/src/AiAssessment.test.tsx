import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { AiAssessmentPanel } from './AiAssessment'
import { SourceImage } from './EvidenceViewer'
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('renders source-bound risks and limits without inventing confidence', () => {
  render(<AiAssessmentPanel inputs={[{ input_id:'frame',ordinal:0,sha256:'hash',artifact_id:null }]} evidence={[]} assessment={{summary:'Наблюдение площадки',stage_hypothesis:{stage:'unknown',reason:'Мало данных'},risks:[{category:'safety',text:'Нужен осмотр',frame_ids:['frame'],observation_ids:['object']}],recommendations:['Проверить вручную'],limitations:['Плана нет']}} />)
  expect(screen.getByText('Кадры: 1')).toBeTruthy()
  expect(screen.getByText('object')).toBeTruthy()
  expect(screen.getByText('Плана нет')).toBeTruthy()
  expect(screen.getByRole('heading', { name: 'Аналитика мультимодальной модели' })).toBeTruthy()
  expect(screen.queryByText(/\d+%/)).toBeNull()
})
it('preserves unknown unlocalized objects without trying to draw a box', async () => {
  Object.defineProperty(URL,'createObjectURL',{configurable:true,value:()=> 'blob:source'})
  Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:()=> {}})
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,blob:async()=>new Blob(['mock'])})))
  render(<SourceImage runId="run" artifactId="image" label="Кадр" description="буровая установка" showBoxes objects={[{input_id:'frame',class_name:'unknown',score:null,box:null,image_size:[64,48],invocation_id:'call'}]} />)
  expect(await screen.findByRole('img')).toBeTruthy()
  expect(screen.queryByRole('button')).toBeNull()
})

it('resolves frozen risk grounds and opens the supporting frame', () => {
  const open=vi.fn()
  render(<AiAssessmentPanel inputs={[{input_id:'frame',ordinal:0,sha256:'hash',artifact_id:'image'}]} onOpenFrame={open}
    evidence={[{id:'call',kind:'assessment',state:'completed',result:null,context:{frames:[{input_id:'frame',observations:[{id:'object',type_ru:'Экскаватор',evidence:'Виден ковш',status:'uncertain'}]}]}}]}
    assessment={{summary:'Осмотр',stage_hypothesis:{stage:'unknown',reason:'Недостаточно данных'},risks:[{category:'process',text:'Проверить технику',frame_ids:['frame'],observation_ids:['object']}],recommendations:[],limitations:['Фотография']}} />)
  expect(screen.getByText('Экскаватор')).toBeTruthy()
  expect(screen.getByText(/Виден ковш/, {selector:'li'})).toBeTruthy()
  expect(screen.getByText(/тип не определён уверенно/)).toBeTruthy()
  screen.getByText('Связанные наблюдения').click()
  screen.getByRole('button',{name:'Открыть кадр 1'}).click()
  expect(open).toHaveBeenCalledWith('frame')
})
it('shows retained invalid and uncertain calls without a successful assessment', () => {
  render(<AiAssessmentPanel inputs={[]} assessment={null} evidence={[
    {id:'one',kind:'frame',state:'invalid',context:{},result:{model:null,usage:null,instruction_version:'v1',schema_version:'v1',raw:{status:'incomplete'}}},
    {id:'two',kind:'assessment',state:'uncertain',context:{},result:null},
  ]} />)
  expect(screen.getByText('Наблюдение кадра · Ответ отклонён')).toBeTruthy()
  expect(screen.getByText('Итоговая аналитика · Результат неизвестен')).toBeTruthy()
  expect(screen.getByText(/Успешная аналитика отсутствует/)).toBeTruthy()
  expect(screen.getByRole('heading', { name: 'Сохранённые вызовы мультимодальной модели' })).toBeTruthy()
  expect(screen.getByText(/"incomplete"/)).toBeTruthy()
})

it('labels historical evidence without rewriting the saved provider response', () => {
  const evidence = [{id:'old-call',kind:'assessment',state:'completed',context:{},result:{
    model:'gpt://folder/deepseek-v4.1-flash/latest',usage:null,instruction_version:'deepseek-service-v1',
    schema_version:'deepseek-service-v1',raw:{provider:'DeepSeek'},
  }}]
  const saved = JSON.stringify(evidence)
  render(<AiAssessmentPanel inputs={[]} evidence={evidence} assessment={{
    summary:'Сохранённая аналитика',stage_hypothesis:{stage:'unknown',reason:'Мало данных'},
    risks:[],recommendations:[],limitations:[],
  }} />)
  expect(screen.getByRole('heading', { name: 'Аналитика мультимодальной модели' })).toBeTruthy()
  expect(screen.getByText(/Источник: Yandex AI Studio/)).toBeTruthy()
  expect(screen.getByText(/"provider": "DeepSeek"/)).toBeTruthy()
  expect(JSON.stringify(evidence)).toBe(saved)
})

it('shows hybrid activity, frame stage hypotheses and applicable plan links', () => {
  const open = vi.fn()
  render(<AiAssessmentPanel inputs={[{input_id:'frame',ordinal:0,sha256:'hash',artifact_id:null}]} evidence={[]} onOpenFrame={open}
    assessment={{summary:'Наблюдение',stage_hypothesis:{stage:'excavation',reason:'Котлован'},risks:[],recommendations:[],limitations:['Один кадр'],
      activity:[{state:'working_signs',reason:'Пересыпание грунта',uncertainty:'Длительность неизвестна',frame_ids:['frame']}],
      stage_hypotheses:[{stage:'excavation',reason:'Виден котлован',frame_ids:['frame'],work_entry_id:'work'}]}} />)
  expect(screen.getByText('Видны признаки работы')).toBeTruthy()
  expect(screen.getByText('Земляные работы: Виден котлован')).toBeTruthy()
  expect(screen.queryByText(/excavation:/)).toBeNull()
  expect(screen.getByText('Длительность неизвестна')).toBeTruthy()
  expect(screen.getByRole('link', {name:'Работа плана'}).getAttribute('href')).toBe('#work-work')
  screen.getAllByRole('button',{name:'Кадр 1'})[0].click()
  expect(open).toHaveBeenCalledWith('frame')
})
