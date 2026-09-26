import type { Input } from './EvidenceViewer'
export type AiAssessment = { summary: string; stage_hypothesis: { stage: string; reason: string }; risks: { category: 'process' | 'plan' | 'safety'; text: string; frame_ids: string[]; observation_ids: string[]; cause?: string; work_entry_id?: string | null; impact?: string; recommended_check?: string; limitations?: string[] }[]; activity?: { state: string; reason: string; uncertainty: string; frame_ids: string[] }[]; stage_hypotheses?: { stage: string; reason: string; frame_ids: string[]; work_entry_id: string | null }[]; recommendations: string[]; limitations: string[] }
type Ground = { id: string; type_ru?: string; evidence?: string; name?: string; state?: string; status?: string }
export type AiEvidence = { id: string; kind: string; input_id?: string | null; state: string; context: { frames?: { input_id: string; observations: Ground[] }[] }; result: { model: string | null; usage: unknown; instruction_version: string; schema_version: string; raw: unknown } | null }
const categories = { process: 'Организация работ', plan: 'План работ', safety: 'Возможный риск безопасности' }
export function AiAssessmentPanel({ assessment, evidence, inputs, onOpenFrame }: { assessment?: AiAssessment | null; evidence: AiEvidence[]; inputs: Input[]; onOpenFrame?: (id: string) => void }) {
  const frames = evidence.find(call => call.kind === 'assessment')?.context.frames ?? []
  const grounds = new Map(frames.flatMap(frame => frame.observations.map(item => [item.id, { ...item, input_id: frame.input_id }] as const)))
  const scenes: Record<string, string> = { excavation_or_trench: 'Котлован или траншея', formwork: 'Опалубка', rebar: 'Арматура', concrete_surface: 'Бетонная поверхность', road_base_or_surface: 'Основание или покрытие дороги' }
  return <section className="panel" aria-labelledby="ai-assessment">
    <h2 id="ai-assessment">{assessment ? 'Аналитика DeepSeek' : 'Сохранённые вызовы DeepSeek'}</h2>
    <p>Источник: Yandex AI Studio. Вывод модели, требующий проверки человеком.</p>
    {assessment ? <><p>{assessment.summary}</p>
      {!!assessment.activity?.length && <><h3>Признаки работы</h3><ul>{assessment.activity.map((item, index) => <li key={index}><strong>{{ working_signs: 'Видны признаки работы', possible_idle: 'Возможный простой', insufficient_data: 'Недостаточно данных' }[item.state] ?? item.state}</strong>: {item.reason}<p>{item.uncertainty}</p>{item.frame_ids.map(id => <button key={id} type="button" className="secondary" onClick={() => onOpenFrame?.(id)}>Кадр {(inputs.find(input => input.input_id === id)?.ordinal ?? -1) + 1}</button>)}</li>)}</ul></>}
      {!!assessment.stage_hypotheses?.length && <><h3>Этапы и работы по кадрам</h3><ul>{assessment.stage_hypotheses.map((item, index) => <li key={index}>{item.stage}: {item.reason}{item.work_entry_id && <p>Работа плана: <a href={`#work-${item.work_entry_id}`}>{item.work_entry_id}</a></p>}{item.frame_ids.map(id => <button key={id} type="button" className="secondary" onClick={() => onOpenFrame?.(id)}>Кадр {(inputs.find(input => input.input_id === id)?.ordinal ?? -1) + 1}</button>)}</li>)}</ul></>}
      <h3>Риски для проверки</h3>
      {assessment.risks.length ? <ul>{assessment.risks.map((risk, index) => <li key={index}>
        <strong>{categories[risk.category]}</strong>: {risk.text}{risk.impact && <p>Возможное влияние: {risk.impact}</p>}{risk.recommended_check && <p>Проверить: {risk.recommended_check}</p>}{risk.work_entry_id && <p>Работа плана: <a href={`#work-${risk.work_entry_id}`}>{risk.work_entry_id}</a></p>}{risk.limitations?.map((text, i) => <p key={i}>{text}</p>)}
        <p>Кадры: {risk.frame_ids.map(id => (inputs.find(input => input.input_id === id)?.ordinal ?? -1) + 1).join(', ')}</p>
        <details><summary>Связанные наблюдения</summary><ul>{risk.observation_ids.map(id => {
          const ground = grounds.get(id)
          return <li key={id}>{ground ? <>
            <strong>{ground.type_ru ?? scenes[ground.name ?? ''] ?? ground.name}</strong>
            {ground.status === 'uncertain' && ' · тип не определён уверенно'}
            {ground.evidence && <>: {ground.evidence}</>}
            {ground.state && <> · {ground.state === 'present' ? 'виден в кадре' : 'видимость не подтверждена'}</>}
            {onOpenFrame && <button type="button" className="secondary" onClick={() => onOpenFrame(ground.input_id)}>Открыть кадр {(inputs.find(input => input.input_id === ground.input_id)?.ordinal ?? -1) + 1}</button>}
            <details><summary>Идентификатор наблюдения</summary><code>{id}</code></details>
          </> : <code>{id}</code>}</li>
        })}</ul></details>
      </li>)}</ul> : <p>Риски не выделены. Это не подтверждает безопасность или отсутствие проблем.</p>}
      <h3>Рекомендации</h3><ul>{assessment.recommendations.map((text, i) => <li key={i}>{text}</li>)}</ul>
      <h3>Ограничения</h3><ul>{assessment.limitations.map((text, i) => <li key={i}>{text}</li>)}</ul>
    </> : <p>Успешная аналитика отсутствует. Сохранённый ответ или резервация не являются успешным результатом; повтор вызова запрещён.</p>}
    <p>Необнаружение техники не доказывает её отсутствие. Расстояния и нормативные нарушения по этим фотографиям не подтверждены.</p>
    <details><summary>Сохранённые источники и ответы модели</summary>{evidence.map(call => <details key={call.id}><summary>{call.kind === 'frame' ? 'Наблюдение кадра' : 'Итоговая аналитика'} · {call.state}</summary><p>{call.result?.model} · инструкция {call.result?.instruction_version} · схема {call.result?.schema_version}</p><pre>{JSON.stringify(call, null, 2)}</pre></details>)}</details>
  </section>
}
