type Work = { starts_at: string; ends_at: string }
export default function PlanTimeline({ entries, title, selected, select }: { entries: Work[]; title: (index: number) => string; selected: number; select: (index: number) => void }) {
  const ordered = entries.map((entry, index) => ({ ...entry, index })).sort((a, b) => a.starts_at.localeCompare(b.starts_at) || a.index - b.index)
  const predecessors = new Map<number, number[]>()
  for (const work of ordered) {
    const earlier = ordered.filter(other => other.index !== work.index && other.ends_at <= work.starts_at && other.starts_at < work.starts_at)
    const latest = earlier.reduce((end, other) => other.ends_at > end ? other.ends_at : end, '')
    predecessors.set(work.index, earlier.filter(other => other.ends_at === latest).map(other => other.index))
  }
  const width = Math.max(320, ordered.length * 250)
  const position = new Map(ordered.map((work, index) => [work.index, index]))
  return <section className="plan-timeline" aria-label="Порядок работ по срокам"><h3>Порядок работ</h3><p className="plan-field-hint">Стрелки связывают работу с ближайшей завершившейся по срокам. Это порядок по датам, а не подтверждённая зависимость. Нажмите на работу, чтобы изменить её.</p><div className="plan-timeline-scroll"><div className="plan-timeline-canvas" style={{ width }}><svg width={width} height="160" aria-hidden="true"><defs><marker id="plan-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" /></marker></defs>{ordered.flatMap(work => (predecessors.get(work.index) ?? []).map(from => {
    const x1 = position.get(from)! * 250 + 218
    const x2 = position.get(work.index)! * 250 + 8
    return <path key={`${from}-${work.index}`} d={`M${x1},80 C${x1 + 24},80 ${x2 - 24},80 ${x2},80`} fill="none" stroke="currentColor" strokeWidth="2" markerEnd="url(#plan-arrow)" />
  }))}</svg>{ordered.map((work, column) => <button key={work.index} type="button" className="plan-timeline-node" aria-pressed={selected === work.index} onClick={() => select(work.index)} style={{ left: column * 250 + 8 }}><strong>{work.index + 1}. {title(work.index)}</strong><span>{work.starts_at.replace('T', ' ')} → {work.ends_at.replace('T', ' ')}</span><small>{(predecessors.get(work.index) ?? []).length ? `После: ${(predecessors.get(work.index) ?? []).map(index => index + 1).join(', ')}` : 'Без предшествующих работ'}</small></button>)}</div></div></section>
}
