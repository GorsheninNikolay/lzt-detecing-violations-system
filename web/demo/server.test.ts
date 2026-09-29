import { describe, expect, it } from 'vitest'
import { createHash, randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import sharp from 'sharp'
import { createDemoStore } from './server'
import { PROJECT_A, PROJECT_B, RUN_A } from './fixtures'
describe('isolated demonstration contract', () => {
  it('fails unknown routes and isolates project writes', async () => {
    const store = createDemoStore()
    expect((await store.request('POST', '/api/not-a-real-endpoint')).status).toBe(404)
    const a = await store.request('GET', `/api/runs?project_id=${PROJECT_A}`)
    const b = await store.request('GET', `/api/runs?project_id=${PROJECT_B}`)
    expect(a.data.runs[0].project_id).toBe(PROJECT_A)
    expect(b.data.runs[0].project_id).toBe(PROJECT_B)
    const signal = (await store.request('GET', `/api/signals?project_id=${PROJECT_A}`)).data.signals[0]
    await store.request('PATCH', `/api/signals/${signal.id}`, { state: 'closed', comment: 'Проверено' })
    expect((await store.request('GET', `/api/signals?project_id=${PROJECT_A}`)).data.summary.open_count).toBe(0)
    expect((await store.request('GET', `/api/signals?project_id=${PROJECT_B}`)).data.summary.open_count).toBe(1)
  })
  it('retains idempotency, progresses real server stages and recovers a failed submission', async () => {
    let now = 0
    const store = createDemoStore(() => now)
    await store.request('POST', '/api/__demo/state', { state: 'recovery' })
    const body = { project_id: PROJECT_A, zone_id: `${PROJECT_A}-zone`, image_base64: 'aGVsbG8=' }
    expect((await store.request('POST', '/api/runs/single-image', body, 'upload')).status).toBe(503)
    const accepted = await store.request('POST', '/api/runs/single-image', body, 'upload')
    expect(accepted.status).toBe(202)
    expect(await store.request('POST', '/api/runs/single-image', body, 'upload')).toEqual(accepted)
    expect((await store.request('POST', '/api/runs/single-image', { ...body, scenario: 'different' }, 'upload')).status).toBe(409)
    expect((await store.request('GET', `/api/runs/${accepted.data.run_id}`)).data.state).toBe('running')
    now = 10000
    expect((await store.request('GET', `/api/runs/${accepted.data.run_id}`)).data.state).toBe('succeeded')
    await store.request('POST', '/api/__demo/state', { state: 'empty' })
    expect((await store.request('GET', '/api/projects')).data.projects).toEqual([])
    expect((await store.request('GET', `/api/runs/${RUN_A}`)).status).toBe(404)
  })
})

it('keeps retry projections tied to readable artifacts and annotation checksums', async () => {
  let now = 0
  const store = createDemoStore(() => now)
  await store.request('POST', '/api/__demo/state', { state: 'error' })
  const retry = await store.request('POST', `/api/runs/${RUN_A}/retry`)
  const run = (await store.request('GET', `/api/runs/${retry.data.run_id}`)).data
  now = 10000
  const completed = (await store.request('GET', `/api/runs/${retry.data.run_id}`)).data
  expect(completed.stages.every((stage: {state:string}) => stage.state === 'succeeded')).toBe(true)
  expect(completed.result_projection.frames.map((frame: {source_artifact_id:string}) => frame.source_artifact_id)).toEqual(completed.inputs.map((input: {artifact_id:string}) => input.artifact_id))
  for (const input of run.inputs) {
    expect((await store.request('GET', `/api/runs/${retry.data.run_id}/artifacts/${input.artifact_id}`)).status).toBe(200)
    expect((await store.request('POST', `/api/runs/${retry.data.run_id}/frames/${input.input_id}/annotations`, { input_sha256: input.sha256, objects: [] }, input.input_id)).status).toBe(201)
  }
})

it('binds an immutable zone revision and derives only justified signals from that plan', async () => {
  let now = 0
  const store = createDemoStore(() => now)
  const zone = `${PROJECT_A}-zone`, oldPlan = (await store.request('GET', `/api/zones/${zone}/plan`)).data
  const changed = (await store.request('PUT', `/api/zones/${zone}/plan`, { expected_revision: 1, entries: [{ catalog_work_id: 'earthworks', start_at: '2026-09-01T00:00:00Z', end_at: '2026-10-01T00:00:00Z', state: 'active', stage_key: 'concreting', expected_equipment: ['excavator'], allowed_equipment: [], excluded_equipment: [] }] })).data
  const body = { project_id: PROJECT_A, zone_id: zone, image_base64: 'aGVsbG8=', stage_id: 'roadwork', capture_times: ['2026-09-28T06:30:00Z'] }
  for (const revision of ['missing', `${PROJECT_B}-plan-1`]) expect((await store.request('POST', '/api/runs/single-image', { ...body, plan_revision_id: revision })).status).toBe(404)
  const first = await store.request('POST', '/api/runs/single-image', { ...body, plan_revision_id: oldPlan.revision_id })
  const second = await store.request('POST', '/api/runs/single-image', { ...body, plan_revision_id: changed.revision_id })
  now = 10000
  const oldRun = (await store.request('GET', `/api/runs/${first.data.run_id}`)).data
  const newRun = (await store.request('GET', `/api/runs/${second.data.run_id}`)).data
  expect(oldRun.planned_works[0].id).toBe(oldPlan.entries[0].id)
  expect(newRun.planned_works[0].id).toBe(changed.entries[0].id)
  expect(newRun.result_projection.created_signals).toEqual([])
  expect(newRun.stage).toBe('roadwork')
  expect(newRun.context.stage_id).toBe('roadwork')
  expect(newRun.result_projection.context.stage_id).toBe('roadwork')
  expect(newRun.result_projection.stage_hypotheses[0].stage).toBe('excavation')
  const signal = (await store.request('GET', `/api/signals?project_id=${PROJECT_A}`)).data.signals.find((item: {run_id:string}) => item.run_id === oldRun.run_id)
  expect(signal.revision_id).toBe(oldPlan.revision_id)
  expect(signal.work_entry_id).toBe(oldPlan.entries[0].id)
  expect(signal.basis.class_name).toBe('dump_truck')
  expect((await store.request('GET', `/api/zones/${zone}/plan?revision=1`)).data).toEqual(oldPlan)
  const history = (await store.request('GET', `/api/runs?project_id=${PROJECT_A}`)).data.runs
  expect(history.slice(0, 2).map((run: {run_id:string}) => run.run_id)).toEqual([newRun.run_id, oldRun.run_id])
})

it('retains the submitted custom-zone plan even after that plan changes', async () => {
  let now = 0
  const store = createDemoStore(() => now)
  const zone = (await store.request('POST', `/api/projects/${PROJECT_A}/zones`, { name: 'Дополнительный участок' })).data
  const plan = (await store.request('PUT', `/api/zones/${zone.id}/plan`, { expected_revision: 0, entries: [{ catalog_work_id: 'earthworks', start_at: '2026-09-01T00:00:00Z', end_at: '2026-10-01T00:00:00Z', state: 'active', expected_equipment: ['dump_truck'] }] })).data
  const accepted = await store.request('POST', '/api/runs/single-image', { project_id: PROJECT_A, zone_id: zone.id, image_base64: 'aGVsbG8=', plan_revision_id: plan.revision_id, capture_times: ['2026-09-28T06:30:00Z'] })
  await store.request('PUT', `/api/zones/${zone.id}/plan`, { expected_revision: 1, entries: [] })
  now = 10000
  const run = (await store.request('GET', `/api/runs/${accepted.data.run_id}`)).data
  expect(run.planned_works[0].id).toBe(plan.entries[0].id)
  const signal = (await store.request('GET', `/api/signals?project_id=${PROJECT_A}`)).data.signals.find((item: {run_id:string}) => item.run_id === run.run_id)
  expect(signal).toMatchObject({ zone_id: zone.id, zone_name: zone.name, revision_id: plan.revision_id, plan_revision_number: 1, work_entry_id: plan.entries[0].id })
})

it('rejects an annotation frame segment that only contains a valid frame id', async () => {
  const store = createDemoStore()
  const run = (await store.request('GET', `/api/runs/${RUN_A}`)).data
  const input = run.inputs[0]
  expect((await store.request('POST', `/api/runs/${RUN_A}/frames/wrong-${input.input_id}-suffix/annotations`, { input_sha256: input.sha256, objects: [] })).status).toBe(409)
  expect((await store.request('GET', `/api/runs/${RUN_A}`)).data.annotations).toBeUndefined()
})

it('keeps uploaded project covers isolated, replayable and resettable', async () => {
  const store = createDemoStore()
  const initial = (await store.request('GET', '/api/projects')).data.projects
  expect(initial[0].cover_sha256).not.toBe(initial[1].cover_sha256)
  expect((await store.request('GET', `/api/projects/${PROJECT_A}/cover`)).artifact).toBe('/demo/Screenshot_23.jpg')
  const bytes = await readFile(resolve('public/demo/Screenshot_25.jpg'))
  const body = { data: bytes.toString('base64') }
  const key = randomUUID()
  const uploaded = await store.request('PUT', `/api/projects/${PROJECT_A}/cover`, body, key)
  expect(uploaded.status).toBe(200)
  const image = (await store.request('GET', `/api/projects/${PROJECT_A}/cover?revision=${uploaded.data.cover_sha256}`)).artifact as Uint8Array
  expect(uploaded.data.cover_sha256).toBe(createHash('sha256').update(image).digest('hex'))
  expect((await sharp(image).metadata()).format).toBe('jpeg')
  expect((await sharp(image).metadata()).exif).toBeUndefined()
  expect(await store.request('PUT', `/api/projects/${PROJECT_A}/cover`, body, key)).toEqual(uploaded)
  expect((await store.request('PUT', `/api/projects/${PROJECT_A}/cover`, { data: 'changed' }, key)).status).toBe(409)
  expect((await store.request('PUT', `/api/projects/${PROJECT_B}/cover`, body, key)).status).toBe(409)
  expect((await store.request('PUT', `/api/projects/${PROJECT_A}/cover`, body)).status).toBe(400)
  expect((await store.request('PUT', `/api/projects/${PROJECT_A}/cover`, { data: Buffer.from('not a photograph').toString('base64') }, randomUUID())).status).toBe(400)
  expect((await store.request('PUT', '/api/projects/missing/cover', body, randomUUID())).status).toBe(404)
  const current = (await store.request('GET', '/api/projects')).data.projects
  expect(current[0].cover_sha256).toBe(uploaded.data.cover_sha256)
  expect(current[1].cover_sha256).toBe(initial[1].cover_sha256)
  expect(Buffer.from(image).equals(bytes)).toBe(false)
  const corrupt = Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), Buffer.alloc(40)])
  expect((await store.request('PUT', `/api/projects/${PROJECT_A}/cover`, { data: corrupt.toString('base64') }, randomUUID())).status).toBe(400)
  await store.request('POST', '/api/__demo/state', { state: 'result' })
  expect((await store.request('GET', '/api/projects')).data.projects[0].cover_sha256).toBe(initial[0].cover_sha256)
  expect((await store.request('GET', `/api/projects/${PROJECT_A}/cover`)).artifact).toBe('/demo/Screenshot_23.jpg')
})
