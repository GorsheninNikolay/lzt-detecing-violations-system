import { randomUUID, createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import type { Plugin } from 'vite'
import sharp from 'sharp'
import { validateTrialZip } from './trial'
import { createAccountDemo } from './accounts'
import { FIXED_DATE, PROJECT_A, PROJECT_B, RUN_A, RUN_B, projects, works, photos, makeRun, stageNames } from './fixtures'

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
  const covers = new Map<string, string | Uint8Array>()
  const coverRequests = new Map<string, { projectId: string; body: string; response: Data }>()
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
  function runSignals(run: Data): Data[] {
    const plan = run.plan_snapshot
    if (!plan) return []
    const detected = new Set(run.observations.filter((item: Data) => item.state === 'detected').map((item: Data) => item.class_name))
    const times = run.context.capture_times?.length ? run.context.capture_times : [run.context.period]
    return plan.entries.filter((entry: Data) => entry.state !== 'completed' && times.some((time: string) => Date.parse(time) >= Date.parse(entry.starts_at) && Date.parse(time) <= Date.parse(entry.ends_at))).flatMap((entry: Data) =>
      [...new Set<string>(entry.expected_equipment)].filter(machine => !detected.has(machine)).map(machine => ({
        id: `${run.run_id}-${entry.id}-${machine}-signal`, project_id: run.project_id,
        project_name: projectRows.find(project => project.id === run.project_id)?.name,
        zone_id: run.zone_id, zone_name: zones[run.project_id]?.find(zone => zone.id === run.zone_id)?.name,
        revision_id: plan.revision_id, plan_revision_number: plan.revision_number, work_entry_id: entry.id,
        kind: 'expected_equipment_missing', state: 'new', comment: '', created_at: FIXED_DATE,
        run_id: run.run_id, work_title: works.find(work => work.id === entry.catalog_work_id)?.title ?? 'Работа каталога',
        preview: { ...run.inputs[0], ordinal: 0 },
        basis: { class_name: machine, reason: 'not_detected_in_series', recommendation: 'check_on_site', supporting_input_ids: run.inputs.map((input: Data) => input.input_id) },
      })))
  }
  function bindPlan(run: Data, plan?: Data) {
    run.plan_snapshot = plan ? structuredClone(plan) : null
    run.plan_binding = plan ? { zone_id: run.zone_id, revision_id: plan.revision_id, capture_times: run.context.capture_times ?? [] } : null
    run.planned_works = (plan?.entries ?? []).map((entry: Data) => ({ ...entry, title: works.find(work => work.id === entry.catalog_work_id)?.title ?? 'Работа каталога' }))
    if (run.result_projection) { run.result_projection.context = run.context; run.result_projection.series.declared_observation_area = run.context.observation_area; run.result_projection.created_signals = runSignals(run).map(({ id, kind, state }) => ({ id, kind, state })) }
  }
  function reset(preset = 'result') {
    state = preset; failNextSubmit = preset === 'recovery'; requests.clear(); artifacts.clear(); covers.clear(); coverRequests.clear(); planVersions.clear()
    projectRows = structuredClone(projects).map(project => ({ ...project, cover_sha256: project.id === PROJECT_A
      ? '2dadb850e7a78cca8691763df50d1096d441b7837b1334a26e95d612123aaf9a'
      : '057ae16749a6a50c522b750ae9cf02bc3a168a89e26d3a263ffb2d9ce394de0c' }))
    covers.set(PROJECT_A, '/demo/Screenshot_23.jpg')
    covers.set(PROJECT_B, '/demo/Screenshot_87.jpg')
    runs = {}; signals = []; zones = {}; plans = {}
    for (const project of projectRows) { zones[project.id] = [{ id: `${project.id}-zone`, name: 'Основной участок' }]; plans[`${project.id}-zone`] = { revision_number: 0, entries: [] } }
    if (preset !== 'empty' && preset !== 'upload') {
      for (const [id, projectId] of [[RUN_A, PROJECT_A], [RUN_B, PROJECT_B]]) {
        const run: Data = makeRun(id, projectId)
        if (preset === 'error') { run.state = 'failed'; run.retry_eligible = true; run.profile_id = 'demo-observer'; run.retry_profile_id = 'demo-observer'; run.retry_authorization_revision = 1; run.result_projection = null; run.outcome = null; run.stages = stageNames.map((name, index) => ({ name, state: index < 2 ? 'succeeded' : index === 2 ? 'failed' : 'skipped', reason: index === 2 ? 'observer_execution_failed' : index > 2 ? 'dependency_failed' : null })) }
        if (preset === 'analyzing') { run.state = 'running'; run.started = now(); run.pinned = true }
        plans[run.zone_id] = { revision_id: `${projectId}-plan-1`, revision_number: 1, entries: [{ id: `${projectId}-work-1`, catalog_work_id: 'earthworks', starts_at: '2026-09-01T09:00:00+03:00', ends_at: '2026-10-01T18:00:00+03:00', state: 'active', stage_key: 'excavation', expected_equipment: ['excavator', 'dump_truck'], allowed_equipment: [], excluded_equipment: [] }] }; bindPlan(run, plans[run.zone_id]); register(run); if (preset === 'result' || preset === 'recovery') signals.push(...runSignals(run))
      }
    }
    if (preset === 'empty') { projectRows = []; zones = {}; plans = {} }
  }
  function snapshot(run: Data) {
    if (run.state !== 'running') return run
    const step = run.pinned ? 2 : Math.floor((now() - run.started) / 550)
    if (step >= stageNames.length) { run.state = 'succeeded'; signals.push(...runSignals(run)); return run }
    return { ...run, result_projection: null, outcome: null, observations: step > 2 ? run.observations : [], objects: step > 2 ? run.objects : [], stages: stageNames.map((name, index) => ({ name, state: index < step ? 'succeeded' : index === step ? 'running' : 'pending', timestamp: index <= step ? FIXED_DATE : null })) }
  }
  reset()
  async function request(method: string, rawUrl: string, body: Data = {}, key = ''): Promise<{ status: number; data: any; artifact?: string | Uint8Array; contentType?: string }> {
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
    if (path === '/analysis-choices' && method === 'GET') return ok({ cloud_provider: 'yandex_ai_studio', cloud_provider_label: 'Yandex AI Studio', cloud_profile_id: '11111111-1111-4111-8111-111111111111', stages: [{ id: 'excavation', label: 'Земляные работы', rule: null }, { id: 'concreting', label: 'Бетонирование', rule: null }, { id: 'roadwork', label: 'Дорожные работы', rule: null }] })
    if (path === '/catalog/works' && method === 'GET') return ok({ works })
    const cacheKey = key ? `${method}:${path}:${key}` : ''
    const prior = cacheKey && requests.get(cacheKey)
    if (prior) return prior.body === JSON.stringify(body) ? prior.response as any : error('idempotency_key_conflict', 409)
    const remember = (data: Data, status = 201) => { const response = ok(data, status); if (cacheKey) requests.set(cacheKey, { body: JSON.stringify(body), response }); return response }
    if (path === '/projects') {
      if (method === 'GET') return ok({ projects: projectRows })
      if (method === 'POST') { if (!body.name?.trim()) return error('name_required'); const project = { id: randomUUID(), name: body.name.trim(), timezone: body.timezone || 'Europe/Moscow', cover_sha256: null }; projectRows.push(project); zones[project.id] = [{ id: `${project.id}-zone`, name: 'Основной участок' }]; plans[`${project.id}-zone`] = { revision_number: 0, entries: [] }; return remember(project) }
    }
    const coverMatch = path.match(/^\/projects\/([^/]+)\/cover$/)
    if (coverMatch) {
      const project = projectRows.find(item => item.id === coverMatch[1])
      if (!project) return error('project_not_found', 404)
      if (method === 'GET') return covers.has(project.id)
        ? { status: 200, data: null, artifact: covers.get(project.id) }
        : error('project_cover_not_found', 404)
      if (method === 'PUT') {
        if (!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(key)) return error('invalid_idempotency_key')
        const serialized = JSON.stringify(body)
        const previous = coverRequests.get(key)
        if (previous) return previous.projectId === project.id && previous.body === serialized
          ? previous.response as { status: number; data: Data }
          : error('idempotency_key_conflict', 409)
        if (typeof body.data !== 'string' || body.data.length > 7_000_000 || !/^[A-Za-z0-9+/]+={0,2}$/.test(body.data)) return error('invalid_project_cover')
        const bytes = Buffer.from(body.data, 'base64')
        if (!bytes.length || bytes.length > 5_000_000) return error('invalid_project_cover')
        let cover: Buffer
        try {
          const input = sharp(bytes, { failOn: 'warning', limitInputPixels: 25_000_000, autoOrient: true })
          const metadata = await input.metadata()
          if (!['jpeg', 'png', 'webp'].includes(metadata.format ?? '')) return error('invalid_project_cover')
          cover = await input.resize({ width: 1600, height: 1600, fit: 'inside', withoutEnlargement: true })
            .flatten({ background: '#ffffff' }).jpeg({ quality: 82 }).toBuffer()
          if (!cover.length || cover.length > 5_000_000) return error('invalid_project_cover')
        } catch { return error('invalid_project_cover') }
        const digest = createHash('sha256').update(cover).digest('hex')
        covers.set(project.id, cover)
        project.cover_sha256 = digest
        const response = ok({ cover_sha256: digest })
        coverRequests.set(key, { projectId: project.id, body: serialized, response })
        return response
      }
    }
    const zoneMatch = path.match(/^\/projects\/([^/]+)\/zones$/)
    if (zoneMatch) { if (!zones[zoneMatch[1]]) return error('project_not_found', 404); if (method === 'GET') return ok({ zones: zones[zoneMatch[1]] }); if (method === 'POST') { const zone = { id: randomUUID(), name: body.name }; zones[zoneMatch[1]].push(zone); plans[zone.id] = { revision_number: 0, entries: [] }; return ok(zone, 201) } }
    const excelMatch = path.match(/^\/zones\/([^/]+)\/plan\/(template\.xlsx|import-preview)$/)
    if (excelMatch && plans[excelMatch[1]]) {
      const directory = resolve(process.cwd(), existsSync(resolve(process.cwd(), 'web/demo')) ? 'web/demo' : 'demo')
      const tutorialBytes = readFileSync(resolve(directory, 'tutorial-plan.xlsx'))
      if (excelMatch[2] === 'template.xlsx' && method === 'GET') return { status: 200, data: null, artifact: url.searchParams.get('tutorial') === 'true' ? tutorialBytes : readFileSync(resolve(directory, 'plan-template.xlsx')), contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }
      if (excelMatch[2] === 'import-preview' && method === 'POST') {
        const bytes = body.xlsx instanceof Uint8Array ? Buffer.from(body.xlsx) : Buffer.alloc(0)
        if (!bytes.equals(tutorialBytes)) return ok({ entries: [], errors: [{ row: null, message: 'В демонстрации загрузите неизменённый учебный Excel. Полный импорт доступен на сервере.' }], timezone: 'Europe/Moscow', expected_revision: plans[excelMatch[1]].revision_number })
        return ok({ entries: [{ catalog_work_id: 'earthworks', title: works[0].title, start_at: '2026-10-19T00:00:00+03:00', end_at: '2026-10-20T23:59:59.999999+03:00', state: 'planned', stage_key: 'excavation', expected_equipment: ['excavator'], allowed_equipment: [], excluded_equipment: [] }], errors: [], timezone: 'Europe/Moscow', date_note: 'Дата без времени означает начало и конец дня по часовому поясу проекта.', expected_revision: plans[excelMatch[1]].revision_number })
      }
    }
    const planMatch = path.match(/^\/zones\/([^/]+)\/plan$/)
    if (planMatch && plans[planMatch[1]]) { const plan = plans[planMatch[1]]; if (method === 'GET') { const revision = url.searchParams.get('revision'); if (revision && Number(revision) !== plan.revision_number) { const saved = planVersions.get(`${planMatch[1]}:${revision}`); return saved ? ok(saved) : error('plan_revision_not_found', 404) } return ok(plan) } if (method === 'PUT') { if (body.expected_revision !== plan.revision_number) return error('plan_revision_conflict', 409); planVersions.set(`${planMatch[1]}:${plan.revision_number}`, structuredClone(plan)); plans[planMatch[1]] = { revision_id: randomUUID(), revision_number: plan.revision_number + 1, entries: body.entries.map((entry: Data) => ({ ...entry, id: randomUUID(), starts_at: entry.start_at, ends_at: entry.end_at })) }; return ok(plans[planMatch[1]]) } }
    if (path === '/runs' && method === 'GET') { const projectId = url.searchParams.get('project_id'); const rows = Object.values(runs).reverse().filter(run => projectId ? run.project_id === projectId : !run.project_id).map(run => snapshot(run)); const offset = Number(url.searchParams.get('offset') || 0); return ok({ runs: rows.slice(offset, offset + 20), total: rows.length, next_offset: offset + 20 < rows.length ? offset + 20 : null }) }
    if (['/runs/single-image', '/runs/series'].includes(path) && method === 'POST') {
      if (failNextSubmit) { failNextSubmit = false; return error('demo_temporary_failure', 503) }
      if (!projectRows.some(project => project.id === body.project_id)) return error('project_not_found', 404)
      if (!zones[body.project_id]?.some(zone => zone.id === body.zone_id)) return error('zone_not_found', 404)
      const images: string[] = body.images_base64 ?? [body.image_base64]
      if (!images.length || !images.every(image => typeof image === 'string' && image.length > 0)) return error('images_required')
      const currentPlan = plans[body.zone_id]
      const savedPlan = body.plan_revision_id
        ? currentPlan?.revision_id === body.plan_revision_id ? currentPlan
          : [...planVersions.entries()].find(([key, plan]) => key.startsWith(`${body.zone_id}:`) && plan.revision_id === body.plan_revision_id)?.[1]
        : undefined
      if (body.plan_revision_id && !savedPlan) return error('plan_revision_not_found', 404)
      const run: Data = makeRun(randomUUID(), body.project_id, images.length)
      run.zone_id = body.zone_id
      run.stage = body.stage_id ?? body.stage ?? run.stage
      run.intent = body.intent ?? run.intent
      run.context = { ...run.context, ...body, stage_id: run.stage }
      delete run.context.image_base64; delete run.context.images_base64
      run.result_projection.context = run.context
      bindPlan(run, savedPlan)
      run.state = 'running'; run.started = now(); register(run, images)
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
      if (tail === '/retry' && method === 'POST') { if (run.retry_successor_id) return ok({ run_id: run.retry_successor_id }, 202); if (!run.retry_eligible || run.state !== 'failed') return error('retry_not_eligible', 409); const successor = structuredClone(run); successor.run_id = randomUUID(); successor.id = successor.run_id; successor.state = 'running'; successor.started = now(); successor.pinned = false; successor.retry_predecessor_id = run.run_id; successor.retry_eligible = false; successor.stages = stageNames.map(name => ({ name, state: 'succeeded', timestamp: FIXED_DATE })); successor.result_projection = { ...makeRun(run.run_id, run.project_id, run.inputs.length).result_projection, frames: run.observations, context: run.context, created_signals: [] }; bindPlan(successor, run.plan_snapshot ?? undefined); run.retry_successor_id = successor.run_id; runs[successor.run_id] = successor; return ok({ run_id: successor.run_id }, 202) }
      const annotationMatch = tail.match(/^\/frames\/([^/]+)\/annotations$/)
      if (annotationMatch && method === 'POST') { const input = run.inputs.find((value: Data) => value.input_id === annotationMatch[1]); if (!input || input.sha256 !== body.input_sha256) return error('input_integrity_conflict', 409); run.annotations = { ...body, id: randomUUID(), status: 'pending' }; return remember(run.annotations) }
    }
    if (path === '/signals' && method === 'GET') { const scoped = signals.filter(signal => !url.searchParams.get('project_id') || signal.project_id === url.searchParams.get('project_id')); const open = scoped.filter(signal => signal.state !== 'closed'); return ok({ signals: scoped.filter(signal => !url.searchParams.get('state') || signal.state === url.searchParams.get('state')), new_count: scoped.filter(signal => signal.state === 'new').length, summary: { open_count: open.length, attention_count: open.length, insufficient_data_count: 0 } }) }
    const signalMatch = path.match(/^\/signals\/([^/]+)$/)
    if (signalMatch && method === 'PATCH') { const signal = signals.find(value => value.id === signalMatch[1]); if (!signal) return error('signal_not_found', 404); Object.assign(signal, body); return ok(signal) }
    return error('demo_endpoint_not_implemented', 404)
  }
  return { request }
}
export function demoPlugin(): Plugin {
  const store = createAccountDemo()
  return { name: 'isolated-demonstration', apply: 'serve', configureServer(server) {
    server.middlewares.use(async (req, res, next) => {
      if (!req.url?.startsWith('/api/')) return next()
      try {
        const chunks: Uint8Array[] = []; let size = 0
        for await (const chunk of req) { size += chunk.length; if (size > 180 * 1024 * 1024) { res.writeHead(413).end(); return } chunks.push(chunk) }
        const buffer = Buffer.concat(chunks), raw = buffer.toString()
        const contentType=String(req.headers['content-type'] || '')
        if(req.url.startsWith('/api/trial/import')&&contentType.includes('multipart/form-data')&&raw.includes('filename="')){
          const boundary=/boundary=(?:"([^"]+)"|([^;]+))/.exec(contentType),marker=Buffer.from(`--${boundary?.[1]??boundary?.[2]}`)
          const headerEnd=buffer.indexOf(Buffer.from('\r\n\r\n')),end=buffer.indexOf(marker,headerEnd+4)
          if(headerEnd<0||end<0)throw new Error('invalid_archive')
          validateTrialZip(buffer.subarray(headerEnd+4,end-2))
        }
        const result = await store.request(req.method || 'GET', req.url, raw && String(req.headers['content-type']).includes('application/json') ? JSON.parse(raw) : req.url.includes('/plan/import-preview') ? { xlsx: buffer } : {}, String(req.headers['idempotency-key'] || ''), /(?:^|; )demo_session=([^;]*)/.exec(req.headers.cookie || '')?.[1] || '')
        if (result.session !== undefined) res.setHeader('Set-Cookie', `demo_session=${result.session}; HttpOnly; SameSite=Strict; Path=/`)
        if (result.artifact) { const bytes = typeof result.artifact === 'string' ? await readFile(resolve(server.config.root, 'public', result.artifact.slice(1))) : result.artifact; const type = result.contentType || (bytes[0] === 0x89 ? 'image/png' : bytes[0] === 0x52 ? 'image/webp' : 'image/jpeg'); res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' }); res.end(bytes); return }
        res.writeHead(result.status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(result.data))
      } catch { res.writeHead(400, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ code: 'invalid_demo_request' })) }
    })
  } }
}
