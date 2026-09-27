import { expect, it } from 'vitest'
import cases from '../../shared/display-label-cases.ru.json'
import manifest from '../../backend/app/data/yolo-manifest.json'
import { equipmentLabel, equipmentLabels, stageLabel, signalKindLabel, signalStateLabel, explanationLabel } from './displayLabels'

it('translates every pinned detector class without changing its catalog membership', () => {
  for (const model of manifest.models) for (const name of model.classes) {
    expect(equipmentLabel(name)).toMatch(/[А-Яа-яЁё]/)
    expect(equipmentLabel(name)).not.toBe('Неопределённая техника')
    expect(equipmentLabel(name)).not.toMatch(/[a-z]/i)
  }
  expect(equipmentLabel('lifting-equipment')).toBe('Подъёмная техника')
  expect(Object.hasOwn(equipmentLabels, 'lifting-equipment')).toBe(false)
  expect(equipmentLabel('tower-crane')).toBe('Башенный кран')
  expect(equipmentLabel('Crane manipulator')).toBe('Кран-манипулятор')
})
it('preserves Russian specific types and translates English fallbacks', () => {
  expect(equipmentLabel('unknown', 'Буровая установка')).toBe('Буровая установка')
  expect(equipmentLabel('excavator', 'Excavator')).toBe('Экскаватор')
  expect(equipmentLabel('unlisted-machine', 'unlisted type')).toBe('Неопределённая техника')
  expect(equipmentLabel('constructor', 'toString')).toBe('Неопределённая техника')
})
it('translates stages and visible signal metadata', () => {
  expect(stageLabel('installation')).toBe('Монтаж')
  expect(stageLabel('future-stage')).toBe('Этап не определён')
  expect(signalKindLabel('possible_idle')).toBe('Возможный простой')
  expect(signalStateLabel('in_progress')).toBe('В работе')
})

it('keeps Russian free types with manufacturer names and translates known English free types', () => {
  expect(equipmentLabel('unknown', 'Буровая установка Bauer BG 28', 'drilling rig')).toBe('Буровая установка Bauer BG 28')
  expect(equipmentLabel('unknown', 'special equipment', 'loader crane')).toBe('Кран-манипулятор')
  expect(equipmentLabel('piling rig')).toBe('Сваебойная установка')
  expect(equipmentLabel('road-roller')).toBe('Каток')
  expect(equipmentLabel('truck-mounted-crane')).toBe('Кран-манипулятор')
})

it('uses the review packet presentation cases and exactly eight catalog classes', () => {
  for (const row of cases) expect(equipmentLabel(row.input)).toBe(row.expected)
  expect(Object.keys(equipmentLabels).sort()).toEqual(['excavator','dump_truck','road_roller','truck_mounted_crane','concrete_mixer_truck','bulldozer','truck','mobile_crane'].sort())
  for (const model of manifest.models) for (const [source,target] of Object.entries(model.mapping)) {
    if (target === null) expect(Object.hasOwn(equipmentLabels,source)).toBe(false)
    else expect(Object.hasOwn(equipmentLabels,target)).toBe(true)
  }
})

it('formats known stage/work references without changing stored model text', () => {
 const raw='Этап excavation; проверить запись work-uuid.';
 expect(explanationLabel(raw,{'work-uuid':'Планировка грунта'})).toBe('Этап «Земляные работы»; проверить запись «Планировка грунта».')
 expect(raw).toBe('Этап excavation; проверить запись work-uuid.')
})
