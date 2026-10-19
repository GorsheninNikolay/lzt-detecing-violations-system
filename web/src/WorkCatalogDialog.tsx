import { useEffect, useRef, useState } from 'react'
import { Modal } from './PublicSupport'

type Work = { id: string; title: string; code: string | null; source_row: number }
export default function WorkCatalogDialog({ works, choose, close }: { works: Work[]; choose: (work: Work) => void; close: () => void }) {
  const [search, setSearch] = useState('')
  const [count, setCount] = useState(40)
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => { input.current?.focus() }, [])
  const normalize = (value: string) => value.toLocaleLowerCase('ru').replace(/ё/g, 'е')
  const query = normalize(search.trim())
  const visible = works.filter(work => normalize(`${work.title ?? ''} ${work.code ?? ''}`).includes(query))
  const variants = new Map<string, number>()
  for (const work of works) { const key = `${work.code ?? ''}:${work.title ?? ''}`; variants.set(key, (variants.get(key) ?? 0) + 1) }
  return <Modal title="Выберите работу" close={close}><div className="work-picker">
    <label htmlFor="work-search">Найти по названию или коду</label><input id="work-search" ref={input} type="search" value={search} onChange={event => { setSearch(event.target.value); setCount(40) }} placeholder="Введите название работы" />
    <p className="work-picker-count">Найдено: {visible.length}</p>
    <ul className="work-picker-list">{visible.slice(0, count).map(work => <li key={work.id}><button type="button" aria-label={`Выбрать: ${work.title || 'Работа без названия'}${work.code ? ` (${work.code})` : ''}${(variants.get(`${work.code ?? ''}:${work.title ?? ''}`) ?? 0) > 1 ? `, строка ${work.source_row}` : ''}`} onClick={() => choose(work)}><span>{work.title || 'Работа без названия'}</span>{work.code && <small>Код {work.code}</small>}{((variants.get(`${work.code ?? ''}:${work.title ?? ''}`) ?? 0) > 1 || !work.title) && <small>Строка источника {work.source_row}</small>}</button></li>)}</ul>
    {!visible.length && <p>Ничего не найдено. Попробуйте другое название или код.</p>}
    {visible.length > count && <button type="button" className="secondary" onClick={() => setCount(value => value + 40)}>Показать ещё</button>}
  </div></Modal>
}
