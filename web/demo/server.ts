import { randomUUID, createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import type { Plugin } from 'vite'
import { FIXED_DATE, PROJECT_A, PROJECT_B, RUN_A, RUN_B, projects, works, photos, makeRun, makeSignal, stageNames } from './fixtures'

type Data = Record<string, any>
export function createDemoStore(now = Date.now) {
  let state = 'result'
  let projectRows: Data[] = []
  let runs: Record<string, Data> = {}
  let signals: Data[] = []
  let zones: Record<string, Data[]> = {}
  let plans: Record<string, Data> = {}
  const planVersions = new Map<string, Data>()
  const artifacts = new Map<string, string | Uint8Array>()
  const requests = new Map<string, { body: string; response: Data }>()
  let failNextSubmit = false
  function register(run: Data, images?: string[]) {
    runs[run.run_id] = run
    run.inputs.forEach((input: Data, index: number) => {
      const image = images?.[index]
      const bytes = image ? Buffer.from(image.replace(/^data:[^,]*,/, ''), 'base64') : undefined
      artifacts.set(input.artifact_id, bytes ?? photos[index % photos.length])
      if (bytes) input.sha256 = createHash('sha256').update(bytes).digest('hex')
      for (const observation of run.observations) if (observation.input_id === input.input_id) { observation.input_sha256 = input.sha256; observation.sha256 = input.sha256 }
    })
  }
  function reset(preset = 'result') {
    state = preset; failNextSubmit = preset === 'recovery'; requests.clear(); artifacts.clear(); planVersions.clear()
    projectRows = structuredClone(projects); runs = {}; signals = []; zones = {}; plans = {}
    for (const project of projectRows) { zones[project.id] = [{ id: `${project.id}-zone`, name: 'Основной участок' }]; plans[`${project.id}-zone`] = { revision_number: 0, entries: [] } }
    if (preset !== 'empty' && preset !== 'upload') {
      for (const [id, projectId] of [[RUN_A, PROJECT_A], [RUN_B, PROJECT_B]]) {
        const run: Data = makeRun(id, projectId)
        if (preset === 'error') { run.state = 'failed'; run.retry_eligible = true; run.profile_id = 'demo-observer'; run.retry_profile_id = 'demo-observer'; run.retry_authorization_revision = 1; run.result_projection = null; run.outcome = null; run.stages = stageNames.map((name, index) => ({ name, state: index < 2 ? 'succeeded' : index === 2 ? 'failed' : 'skipped', reason: index === 2 ? 'observer_execution_failed' : index > 2 ? 'dependency_failed' : null })) }
        if (preset === 'analyzing') { run.state = 'running'; run.started = now(); run.pinned = true }
        plans[run.zone_id] = { revision_id: `${projectId}-plan-1`, revision_number: 1, entries: [{ id: `${projectId}-work-1`, catalog_work_id: 'earthworks', starts_at: '2026-09-01T09:00:00+03:00', ends_at: '2026-10-01T18:00:00+03:00', state: 'active', stage_key: 'excavation', expected_equipment: ['excavator', 'dump_truck'], allowed_equipment: [], excluded_equipment: [] }] }; register(run); if (preset === 'result' || preset === 'recovery') signals.push(makeSignal(run as ReturnType<typeof makeRun>))
      }
    }
    if (preset === 'empty') { projectRows = []; zones = {}; plans = {} }
  }
  function snapshot(run: Data) {
    if (run.state !== 'running') return run
    const step = run.pinned ? 2 : Math.floor((now() - run.started) / 550)
    if (step >= stageNames.length) { run.state = 'succeeded'; if (run.plan_binding) signals.push(makeSignal(run as ReturnType<typeof makeRun>)); return run }
    return { ...run, result_projection: null, outcome: null, observations: step > 2 ? run.observations : [], objects: step > 2 ? run.objects : [], stages: stageNames.map((name, index) => ({ name, state: index < step ? 'succeeded' : index === step ? 'running' : 'pending', timestamp: index <= step ? FIXED_DATE : null })) }
  }
  reset()
  async function request(method: string, rawUrl: string, body: Data = {}, key = ''): Promise<{ status: number; data: any; artifact?: string | Uint8Array }> {
    const url = new URL(rawUrl, 'http://demo.local'); const path = url.pathname.replace(/^\/api/, '')
    const ok = (data: any, status = 200) => ({ status, data: structuredClone(data) })
    const error = (code: string, status = 400) => ok({ code }, status)
    if (path === '/__demo/state' && method === 'POST') {
      if (!['empty', 'upload', 'analyzing', 'result', 'error', 'recovery'].includes(body.state)) return error('unknown_demo_state')
      reset(body.state); return ok({ state })
    }
    if (path === '/__demo/state' && method === 'GET') return ok({ state })
    if (method === 'GET' && (path === '/health/live' || path === '/health/ready')) return ok({ status: 'demonstration' })
    if (path === '/analytics/events' && method === 'POST') return ok({ accepted: true }, 202)
    if (path === '/feedback' && method === 'POST') return ok({ id: randomUUID(), status: 'received' }, 201)
    if (path === '/admin/session') return error('authentication_required', 401)
    if (path === '/analysis-choices' && method === 'GET') return ok({ stages: [{ id: 'excavation', label: 'Земляные работы', rule: null }, { id: 'concreting', label: 'Бетонирование', rule: null }, { id: 'roadwork', label: 'Дорожные работы', rule: null }] })
    if (path === '/catalog/works' && method === 'GET') return ok({ works })
    const cacheKey = key ? `${method}:${path}:${key}` : ''
    const prior = cacheKey && requests.get(cacheKey)
    if (prior) return prior.body === JSON.stringify(body) ? prior.response as any : error('idempotency_key_conflict', 409)
    const remember = (data: Data, status = 201) => { const response = ok(data, status); if (cacheKey) requests.set(cacheKey, { body: JSON.stringify(body), response }); return response }
    if (path === '/projects') {
      if (method === 'GET') return ok({ projects: projectRows })
      if (method === 'POST') { if (!body.name?.trim()) return error('name_required'); const project = { id: randomUUID(), name: body.name.trim(), timezone: body.timezone || 'Europe/Moscow' }; projectRows.push(project); zones[project.id] = [{ id: `${project.id}-zone`, name: 'Основной участок' }]; plans[`${project.id}-zone`] = { revision_number: 0, entries: [] }; return remember(project) }
    }
    const zoneMatch = path.match(/^\/projects\/([^/]+)\/zones$/)
    if (zoneMatch) { if (!zones[zoneMatch[1]]) return error('project_not_found', 404); if (method === 'GET') return ok({ zones: zones[zoneMatch[1]] }); if (method === 'POST') { const zone = { id: randomUUID(), name: body.name }; zones[zoneMatch[1]].push(zone); plans[zone.id] = { revision_number: 0, entries: [] }; return ok(zone, 201) } }
    const planMatch = path.match(/^\/zones\/([^/]+)\/plan$/)
    if (planMatch && plans[planMatch[1]]) { const plan = plans[planMatch[1]]; if (method === 'GET') { const revision = url.searchParams.get('revision'); if (revision && Number(revision) !== plan.revision_number) { const saved = planVersions.get(`${planMatch[1]}:${revision}`); return saved ? ok(saved) : error('plan_revision_not_found', 404) } return ok(plan) } if (method === 'PUT') { if (body.expected_revision !== plan.revision_number) return error('plan_revision_conflict', 409); planVersions.set(`${planMatch[1]}:${plan.revision_number}`, structuredClone(plan)); plans[planMatch[1]] = { revision_id: randomUUID(), revision_number: plan.revision_number + 1, entries: body.entries.map((entry: Data) => ({ ...entry, id: randomUUID(), starts_at: entry.start_at, ends_at: entry.end_at })) }; return ok(plans[planMatch[1]]) } }
    if (path === '/runs' && method === 'GET') { const projectId = url.searchParams.get('project_id'); const rows = Object.values(runs).filter(run => projectId ? run.project_id === projectId : !run.project_id).map(run => snapshot(run)); const offset = Number(url.searchParams.get('offset') || 0); return ok({ runs: rows.slice(offset, offset + 20), total: rows.length, next_offset: offset + 20 < rows.length ? offset + 20 : null }) }
    if (['/runs/single-image', '/runs/series'].includes(path) && method === 'POST') {
      if (failNextSubmit) { failNextSubmit = false; return error('demo_temporary_failure', 503) }
      if (!projectRows.some(project => project.id === body.project_id)) return error('project_not_found', 404)
      if (!zones[body.project_id]?.some(zone => zone.id === body.zone_id)) return error('zone_not_found', 404)
      const images: string[] = body.images_base64 ?? [body.image_base64]
      if (!images.length || !images.every(image => typeof image === 'string' && image.length > 0)) return error('images_required')
      const run: Data = makeRun(randomUUID(), body.project_id, images.length)
      run.zone_id = body.zone_id; run.plan_binding = body.plan_revision_id ? { zone_id: body.zone_id, revision_id: body.plan_revision_id, capture_times: body.capture_times } : null; if (!run.plan_binding) { run.result_projection.created_signals = []; run.planned_works = [] } run.context = { ...run.context, ...body }; delete run.context.image_base64; delete run.context.images_base64; run.result_projection.context = run.context; run.state = 'running'; run.started = now(); register(run, images)
      return remember({ run_id: run.run_id }, 202)
    }
    const runMatch = path.match(/^\/runs\/([^/]+)(.*)$/)
    if (runMatch) {
      const run = runs[runMatch[1]]; if (!run) return error('run_not_found', 404)
      const tail = runMatch[2]
      if (!tail && method === 'GET') return ok(snapshot(run))
      const artifactMatch = tail.match(/^\/artifacts\/([^/]+)(?:\/thumbnail)?$/)
      if (artifactMatch && method === 'GET') { const id = artifactMatch[1]; if (!run.inputs.some((input: Data) => input.artifact_id === id) || !artifacts.has(id)) return error('artifact_not_found', 404); return { status: 200, data: null, artifact: artifacts.get(id) } }
      if (tail === '/confirm-stage' && method === 'POST') { run.stage_confirmation = { ...body, created_at: FIXED_DATE }; return ok(run.stage_confirmation) }
      if (tail === '/retry' && method === 'POST') { if (run.retry_successor_id) return ok({ run_id: run.retry_successor_id }, 202); if (!run.retry_eligible || run.state !== 'failed') return error('retry_not_eligible', 409); const successor = structuredClone(run); successor.run_id = randomUUID(); successor.id = successor.run_id; successor.state = 'running'; successor.started = now(); successor.pinned = false; successor.retry_predecessor_id = run.run_id; successor.retry_eligible = false; successor.stages = stageNames.map(name => ({ name, state: 'succeeded', timestamp: FIXED_DATE })); successor.result_projection = { ...makeRun(run.run_id, run.project_id, run.inputs.length).result_projection, frames: run.observations, context: run.context, created_signals: run.plan_binding ? [{ id: `${successor.run_id}-signal`, kind: 'expected_equipment_missing', state: 'new' }] : [] }; run.retry_successor_id = successor.run_id; runs[successor.run_id] = successor; return ok({ run_id: successor.run_id }, 202) }
      if (/^\/frames\/[^/]+\/annotations$/.test(tail) && method === 'POST') { const input = run.inputs.find((value: Data) => tail.includes(value.input_id)); if (!input || input.sha256 !== body.input_sha256) return error('input_integrity_conflict', 409); run.annotations = { ...body, id: randomUUID(), status: 'pending' }; return remember(run.annotations) }
    }
    if (path === '/signals' && method === 'GET') { const scoped = signals.filter(signal => !url.searchParams.get('project_id') || signal.project_id === url.searchParams.get('project_id')); const open = scoped.filter(signal => signal.state !== 'closed'); return ok({ signals: scoped.filter(signal => !url.searchParams.get('state') || signal.state === url.searchParams.get('state')), new_count: scoped.filter(signal => signal.state === 'new').length, summary: { open_count: open.length, attention_count: open.length, insufficient_data_count: 0 } }) }
    const signalMatch = path.match(/^\/signals\/([^/]+)$/)
    if (signalMatch && method === 'PATCH') { const signal = signals.find(value => value.id === signalMatch[1]); if (!signal) return error('signal_not_found', 404); Object.assign(signal, body); return ok(signal) }
    return error('demo_endpoint_not_implemented', 404)
  }
  return { request }
}
export function demoPlugin(): Plugin {
  const store = createDemoStore()
  return { name: 'isolated-demonstration', apply: 'serve', configureServer(server) {
    server.middlewares.use(async (req, res, next) => {
      if (!req.url?.startsWith('/api/')) return next()
      try {
        const chunks: Uint8Array[] = []; let size = 0
        for await (const chunk of req) { size += chunk.length; if (size > 180 * 1024 * 1024) { res.writeHead(413).end(); return } chunks.push(chunk) }
        const raw = Buffer.concat(chunks).toString()
        const result = await store.request(req.method || 'GET', req.url, raw ? JSON.parse(raw) : {}, String(req.headers['idempotency-key'] || ''))
        if (result.artifact) { const bytes = typeof result.artifact === 'string' ? await readFile(resolve(server.config.root, 'public', result.artifact.slice(1))) : result.artifact; res.writeHead(200, { 'Content-Type': bytes[0] === 0x89 ? 'image/png' : 'image/jpeg', 'Cache-Control': 'no-store' }); res.end(bytes); return }
        res.writeHead(result.status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(result.data))
      } catch { res.writeHead(400, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ code: 'invalid_demo_request' })) }
    })
  } }
}
