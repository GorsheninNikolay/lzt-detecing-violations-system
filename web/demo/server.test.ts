import { describe, expect, it } from 'vitest'
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
