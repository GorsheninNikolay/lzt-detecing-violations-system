import { useState } from 'react'
import { equipmentLabels } from './displayLabels'

type Equipment = { expected_equipment: string[]; allowed_equipment: string[]; excluded_equipment: string[] }
export default function PlanEquipment({ value, ordinal, change }: { value: Equipment; ordinal: number; change: (value: Equipment) => void }) {
  const [adding, setAdding] = useState(false)
  const known = Object.keys(equipmentLabels)
  const chosen = new Set([...value.expected_equipment, ...value.allowed_equipment, ...value.excluded_equipment])
  const selected = [...known.filter(name => chosen.has(name)), ...Array.from(chosen).filter(name => !known.includes(name))]
  const available = known.filter(name => !chosen.has(name))
  const label = (name: string) => equipmentLabels[name] ?? name
  function update(name: string, mode: string) {
    const next = { expected_equipment: value.expected_equipment.filter(item => item !== name), allowed_equipment: value.allowed_equipment.filter(item => item !== name), excluded_equipment: value.excluded_equipment.filter(item => item !== name) }
    if (mode === 'expected' || mode === 'expected_allowed') next.expected_equipment.push(name)
    if (mode === 'allowed' || mode === 'expected_allowed') next.allowed_equipment.push(name)
    if (mode === 'excluded') next.excluded_equipment.push(name)
    change(next)
  }
  return <section className="plan-equipment" aria-label={`Техника работы ${ordinal}`}><h4>Техника</h4>
    {!selected.length && <p className="plan-field-hint">Добавьте только ту технику, которую нужно учитывать для этой работы.</p>}
    {selected.map(name => {
      const both = value.expected_equipment.includes(name) && value.allowed_equipment.includes(name)
      const mode = value.excluded_equipment.includes(name) ? 'excluded' : both ? 'expected_allowed' : value.expected_equipment.includes(name) ? 'expected' : 'allowed'
      return <div className="plan-equipment-row" key={name}><span className="plan-equipment-name">{label(name)}</span><label className="plan-equipment-condition"><span>Условие для проверки</span><select aria-label={`Условие для ${label(name)} · работа ${ordinal}`} value={mode} onChange={event => update(name, event.target.value)}><option value="expected">Ожидается</option><option value="allowed">Допускается</option><option value="excluded">Не предусмотрена</option>{both && <option value="expected_allowed">Ожидается и допускается</option>}</select></label><button type="button" className="plan-icon-button" aria-label={`Убрать ${label(name)} из работы ${ordinal}`} onClick={() => update(name, '')}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button></div>
    })}
    {available.length > 0 && <button type="button" className="secondary" aria-expanded={adding} onClick={() => setAdding(value => !value)}>{adding ? 'Готово' : 'Добавить технику'}</button>}
    {adding && available.length > 0 && <div className="plan-equipment-options" aria-label="Доступная техника">{available.map(name => <button type="button" key={name} aria-label={`Добавить: ${label(name)}`} onClick={() => update(name, 'expected')}>+ {label(name)}</button>)}</div>}
    {selected.length > 0 && <p className="plan-field-hint">Для каждой машины выберите, нужна ли она для работы, просто допустима или не предусмотрена.</p>}
    {selected.length > 0 && <details className="plan-field-help"><summary>Что означают условия?</summary><p>«Ожидается» — техника нужна для работы. «Допускается» — может присутствовать, но её наличие необязательно. «Не предусмотрена» — явно исключена для этой работы. Неуказанная техника не считается запрещённой.</p></details>}
  </section>
}
