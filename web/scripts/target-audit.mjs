export async function auditTargets(page) {
  return page.evaluate(() => {
    const measured = [], exceptions = [], failures = [], seen = new Set()
    const visible = element => element.checkVisibility() && element.getBoundingClientRect().width > 0 && element.getBoundingClientRect().height > 0
    for (const element of document.querySelectorAll('button,summary,input,select,textarea,a')) {
      if (!visible(element) || element.closest('[aria-hidden=true]')) continue
      const rect = element.getBoundingClientRect()
      const description = element.getAttribute('aria-label') || element.textContent?.trim().slice(0, 70) || element.id || element.tagName
      if (element.matches('.object-box,.annotation-box,.annotation-resize')) {
        exceptions.push({ description, kind: 'geometry', width: rect.width, height: rect.height, reason: 'Existing geometry controls; keyboard and labeled object/numeric alternatives. Pseudo-element hit area is not measured here.' }); continue
      }
      if (element.matches('a') && !element.closest('nav') && !element.matches('.primary,.secondary,.project-open,.new-analysis-link')) {
        exceptions.push({ description, kind: 'inline-link', width: rect.width, height: rect.height, reason: 'Inline prose or heading link; excluded from the standalone 44px target criterion.' }); continue
      }
      const target = element.matches('input[type=checkbox],input[type=radio],input[type=file]') ? element.labels?.[0] ?? element : element
      if (seen.has(target)) continue
      seen.add(target)
      const box = target.getBoundingClientRect()
      const item = { description, kind: element.matches('input[type=checkbox],input[type=radio]') ? 'checkbox-label' : element.closest('nav') ? 'navigation' : element.tagName.toLowerCase(), width: box.width, height: box.height, disabled: !!element.disabled }
      measured.push(item)
      if (box.width < 43.5 || box.height < 43.5) failures.push(item)
    }
    return { measured, failures, exceptions }
  })
}
