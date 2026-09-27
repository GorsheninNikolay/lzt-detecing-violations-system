import labels from '../../shared/display-labels.ru.json'

export const equipmentLabels: Record<string, string> = labels.equipment
export const stageLabels: Record<string, string> = labels.stages
export const signalKindLabels: Record<string, string> = labels.signal_kinds
export const signalStateLabels: Record<string, string> = labels.signal_states
const sourceLabels: Record<string, string> = labels.source_equipment
const normalized = (value: string) => value.trim().toLowerCase().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ')
const lookup = (values: Record<string, string>, key: string) => Object.hasOwn(values, key) ? values[key] : undefined
const russian = (value: string) => /^[^a-zа-яё]*[а-яё]/i.test(value)

export function equipmentLabel(name: string, typeRu?: string, typeEn?: string): string {
  if (typeRu?.trim()) {
    if (russian(typeRu)) return typeRu.trim()
    const translated = lookup(sourceLabels, normalized(typeRu))
    if (translated) return translated
  }
  return lookup(equipmentLabels, name) ?? lookup(sourceLabels, normalized(name)) ?? (typeEn ? lookup(sourceLabels, normalized(typeEn)) : undefined) ?? (russian(name) ? name : 'Неопределённая техника')
}
export const stageLabel = (name: string) => lookup(stageLabels, name) ?? 'Этап не определён'
export const signalKindLabel = (name: string) => lookup(signalKindLabels, name) ?? 'Сигнал для проверки'
export const signalStateLabel = (name: string) => lookup(signalStateLabels, name) ?? 'Состояние не определено'

const sceneLabels: Record<string, string> = labels.scenes
const callStateLabels: Record<string, string> = labels.call_states
export const sceneLabel = (name: string) => lookup(sceneLabels, name) ?? 'Признак сцены не определён'
export const callStateLabel = (name: string) => lookup(callStateLabels, name) ?? 'Состояние не определено'

export function explanationLabel(text: string, workTitles: Record<string, string> = {}): string {
  let result = text.replace(/\b(excavation|concreting|roadwork)\b/g, name => `«${stageLabel(name)}»`)
  for (const [id, title] of Object.entries(workTitles)) result = result.replaceAll(id, `«${title}»`)
  return result
}
