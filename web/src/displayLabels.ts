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

export type CloudProvider = 'deepseek' | 'yandex_ai_studio'
export const cloudProviderLabel = (_provider: CloudProvider) => 'Мультимодальная модель'
export function savedCloudProviderLabel(adapterCode?: string): string | null {
  return adapterCode === 'deepseek_direct' || adapterCode === 'yandex_deepseek' ? 'Мультимодальная модель' : null
}
export const cloudErrorLabels: Record<string, string> = {
  observer_balance_failed: 'На аккаунте облачной модели недостаточно средств. Пополните баланс перед новым анализом.',
  cloud_provider_mismatch: 'Сервис облачной обработки изменился. Обновите настройки и подтвердите согласие для нового сервиса.',
  quality_budget_provider_mismatch: 'Для этого облачного сервиса настроен несовместимый бюджет обработки. Проверьте настройки сервера.',
  cloud_provider_unavailable: 'Облачная обработка пока недоступна. Обновите настройки или проверьте конфигурацию сервера.',
  deepseek_response_invalid: 'Ответ облачной модели не прошёл проверку. Проверьте сохранённые данные вызова; автоматического повтора не будет.',
  observer_redirect_rejected: 'Облачный сервис вернул перенаправление. Передача ключа на другой адрес заблокирована.',
  observer_access_failed: 'Облачный сервис отклонил доступ. Проверьте API-ключ выбранного провайдера.',
  observer_quota_failed: 'Достигнут лимит запросов облачного сервиса. Подождите перед новым анализом.',
}

const sceneLabels: Record<string, string> = labels.scenes
const callStateLabels: Record<string, string> = labels.call_states
export const sceneLabel = (name: string) => lookup(sceneLabels, name) ?? 'Признак сцены не определён'
export const callStateLabel = (name: string) => lookup(callStateLabels, name) ?? 'Состояние не определено'

export function explanationLabel(text: string, workTitles: Record<string, string> = {}): string {
  let result = text.replace(/\bDeepSeek\b/gi, 'мультимодальная модель').replace(/\b(excavation|concreting|roadwork)\b/g, name => `«${stageLabel(name)}»`)
  for (const [id, title] of Object.entries(workTitles)) result = result.replaceAll(id, `«${title}»`)
  return result
}
