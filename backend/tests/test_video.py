import asyncio
import io
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.application import video
from app.application.deepseek_runtime import provision
from test_accounts import accounts


@pytest.fixture
def clip(tmp_path):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg required')
    path = tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x96:rate=5:duration=0.6',
                    '-f','lavfi','-i','sine=frequency=440:duration=0.6','-c:v','libx264','-c:a','aac','-shortest',str(path)],check=True)
    return path


def test_probe_real_video_and_sampling(clip):
    metadata = video.probe(clip)
    assert metadata['frame_count'] == 3
    assert metadata['timestamps'] == [0,0.2,0.4]
    assert metadata['codec'] == 'h264'
    assert video.selected_indices(3) == [0,1,2]
    assert video.selected_indices(7200) == [0,1028,2057,3085,4114,5142,6171,7199]
    assert video.selected_indices([0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,9]) == [0,8,9]


def test_reject_corrupt_file(tmp_path):
    path = tmp_path/'broken.mov'
    path.write_bytes(b'not a video')
    with pytest.raises(ValueError,match='video_decode_failed'):
        video.probe(path)


class MemoryS3:
    def __init__(self):
        self.data = {}

    def put_object(self,Key,Body,**kwargs):
        self.data[Key] = Body.read() if hasattr(Body,'read') else Body

    def get_object(self,Key,Range=None,**kwargs):
        payload = self.data[Key]
        if Range:
            start,end = map(int,Range.removeprefix('bytes=').split('-'))
            payload = payload[start:end+1]
        return {'Body':io.BytesIO(payload)}

    def head_object(self,Key,**kwargs):
        return {'ContentLength':len(self.data[Key])}


def persisted_job(store):
    profile_id = provision(store,'video-fixture-'+str(uuid4()))
    profile,revision = store.require_authorized(profile_id)
    identifier,project,zone = uuid4(),uuid4(),uuid4()
    with store.engine.begin() as db:
        db.execute(text("INSERT INTO site_projects(id,name,timezone) VALUES (:id,'Video fixture','Europe/Moscow')"),{'id':project})
        db.execute(text("INSERT INTO site_zones(id,project_id,name) VALUES (:id,:project,'Fixture zone')"),{'id':zone,'project':project})
        db.execute(text("""INSERT INTO video_jobs(id,project_id,zone_id,request_key,request_hash,source_key,source_sha256,source_size,
            context,profile_snapshot,state,metadata,profile_id,authorization_revision)
            VALUES (:id,:project,:zone,:key,'fixture','fixture-source',:sha,1,
                CAST(:context AS jsonb),CAST(:profile AS jsonb),'running','{}',:profile_id,:revision)"""),
            {'id':identifier,'project':project,'zone':zone,'key':str(uuid4()),'sha':'0'*64,
             'context':json.dumps({'project_id':str(project),'zone_id':str(zone),'cloud_processing_consent':True,'cloud_provider':'yandex_ai_studio'}),
             'profile':json.dumps(profile),'profile_id':profile_id,'revision':revision})
        return dict(db.execute(text('SELECT * FROM video_jobs WHERE id=:id'),{'id':identifier}).mappings().one())


def test_range_suffix_and_invalid(monkeypatch):
    s3 = MemoryS3()
    s3.data['result'] = b'0123456789'
    app = FastAPI()
    app.include_router(video.router)
    app.state.artifacts = SimpleNamespace(client=s3,bucket='test')
    monkeypatch.setattr(video,'load_job',lambda *args:{'result':{'artifact_key':'result'}})
    with TestClient(app) as client:
        url = f'/video-runs/{uuid4()}/media'
        response = client.get(url,headers={'Range':'bytes=2-4'})
        assert response.status_code == 206 and response.content == b'234'
        assert response.headers['content-range'] == 'bytes 2-4/10'
        assert client.get(url,headers={'Range':'bytes=-3'}).content == b'789'
        assert client.get(url,headers={'Range':'bytes=10-'}).status_code == 416
        assert client.get(url,headers={'Range':'bytes=0-1,3-4'}).status_code == 416


@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='isolated PostgreSQL required')
@pytest.mark.parametrize('cloud_failure',[False,True])
@pytest.mark.parametrize('media_variant',['normal','rotated','variable','delayed','silent','silent_variable'])
def test_video_pipeline_and_unknown_call_are_not_replayed(clip,monkeypatch,cloud_failure,media_variant):
    if media_variant == 'rotated':
        changed = clip.parent/'portrait.mov'
        video.command(['ffmpeg','-v','error','-display_rotation','90','-i',str(clip),'-c','copy',str(changed)])
        clip = changed
    elif media_variant == 'variable':
        changed = clip.parent/'variable.mp4'
        video.command(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x96:rate=20:duration=0.15','-i',str(clip),'-map','0:v:0','-map','1:a:0','-vf',r'setpts=if(eq(N\,0)\,0\,if(eq(N\,1)\,3\,10))','-fps_mode','vfr','-c:v','libx264','-c:a','copy',str(changed)])
        clip = changed
    elif media_variant in ('silent','silent_variable'):
        changed = clip.parent/'silent.mp4'
        args = ['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x96:rate=20:duration=0.15']
        if media_variant == 'silent_variable':
            args += ['-vf',r'setpts=if(eq(N\,0)\,0\,if(eq(N\,1)\,3\,10))','-fps_mode','vfr']
        video.command([*args,'-c:v','libx264',str(changed)])
        clip = changed
    elif media_variant == 'delayed':
        changed = clip.parent/'delayed.mp4'
        video.command(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x96:rate=5:duration=0.6',
            '-f','lavfi','-i',r'aevalsrc=sin(2*PI*if(lt(t\,1)\,440\,880)*t):s=44100:d=1.6',
            '-filter_complex','[0:v]setpts=PTS+1/TB[v]','-map','[v]','-map','1:a:0',
            '-fps_mode','vfr','-c:v','libx264','-c:a','aac',str(changed)])
        clip = changed
    monkeypatch.setenv('AUTH_REQUIRED','false')
    from app.adapters.postgres import PostgresStore
    from app.application.site import router as site_router
    from app.profiles.deepseek import snapshot, SCENES
    store = PostgresStore(os.environ['TEST_DATABASE_URL'])
    app = FastAPI()
    app.include_router(site_router)
    app.include_router(video.router)
    app.state.store = store
    app.state.readiness = SimpleNamespace(ready=SimpleNamespace(is_set=lambda:True))
    profile_id = provision(store,'video-'+str(uuid4()))
    profile,_ = store.require_authorized(profile_id)
    app.state.claim_loop = SimpleNamespace(runtime_binding=(profile_id,1))
    monkeypatch.setattr(store,'require_authorized',lambda *args:(profile,1))
    monkeypatch.setattr(video.Config,'from_env',lambda:SimpleNamespace(api_key_for=lambda _: 'fake'))
    s3 = MemoryS3()
    app.state.artifacts = SimpleNamespace(client=s3,bucket='test')
    calls = []
    real_detector = video.video_detectors()[0] if os.getenv('VIDEO_REAL_YOLO') == '1' and not cloud_failure else None
    class Detector:
        def detect(self,payload,identity):
            calls.append(identity)
            if real_detector:
                return real_detector.detect(payload,identity)
            return {'models':[{'model_id':'first','detections':[]},{'model_id':'second','detections':[]}]}
    monkeypatch.setattr(video,'video_detectors',lambda *args:(Detector(),{'actual_device':'cpu','warning':'slow'}))
    class Observer:
        def __init__(self,*args): pass
        def call(self,kind,context,*args,**kwargs):
            if cloud_failure:
                raise ValueError('observer_transport_failed')
            if kind == 'assessment':
                return {'valid':True,'value':{'summary':'test'}}
            return {'valid':True,'value':{'objects':[],'scenes':{k:'uncertain' for k in SCENES},'stage':'unknown','stage_reason':'test'}}
    monkeypatch.setattr(video,'DeepSeek',Observer)
    with TestClient(app) as client:
        project = client.post('/projects',json={'name':'video '+str(uuid4()),'timezone':'Europe/Moscow'}).json()['id']
        zone = client.post(f'/projects/{project}/zones',json={'name':'north'}).json()['id']
        url = f'/runs/video?project_id={project}&zone_id={zone}&cloud_processing_consent=true&cloud_provider=yandex_ai_studio'
        confirmed = media_variant == 'normal' and not cloud_failure
        original_plan = None
        if confirmed:
            works = client.get('/catalog/works').json()['works']
            entry = {'catalog_work_id':works[0]['id'],'start_at':'2026-10-20T00:00:00+03:00',
                'end_at':'2026-10-21T00:00:00+03:00','state':'active','stage_key':'excavation',
                'expected_equipment':['excavator'],'allowed_equipment':[],'excluded_equipment':[]}
            saved = client.put(f'/zones/{zone}/plan',json={'expected_revision':0,'entries':[entry]})
            assert saved.status_code == 200,saved.text
            original_plan = client.get(f'/zones/{zone}/plan').json()
            url += '&capture_started_at=2026-10-20T09:00:00%2B03:00&plan_revision_id='+original_plan['revision_id']
        headers = {'Idempotency-Key':str(uuid4()),'Content-Type':'video/mp4'}
        response = client.post(url,content=clip.read_bytes(),headers=headers)
        assert response.status_code == 202,response.text
        identifier = response.json()['id']
        if confirmed:
            changed_plan = client.put(f'/zones/{zone}/plan',json={'expected_revision':1,'entries':[{**entry,'expected_equipment':[]}]})
            assert changed_plan.status_code == 200,changed_plan.text
        else:
            with store.engine.begin() as db:
                db.execute(text('INSERT INTO zone_plan_revisions(id,zone_id,revision_number) VALUES (:id,:zone,1)'),{'id':uuid4(),'zone':zone})
        app.state.claim_loop.runtime_binding = None
        assert client.post(url,content=clip.read_bytes(),headers=headers).json()['id'] == identifier
        changed_url = url.replace('2026-10-20T09:00:00%2B03:00','2026-10-20T00:00:00Z') if confirmed else url+'&capture_started_at=2026-10-20T00:00:00Z'
        changed = client.post(changed_url,content=clip.read_bytes(),headers=headers)
        assert changed.status_code == 409
        with store.engine.begin() as db:
            row = dict(db.execute(text('SELECT * FROM video_jobs WHERE id=:id'),{'id':identifier}).mappings().one())
            db.execute(text("UPDATE video_jobs SET state='running' WHERE id=:id"),{'id':identifier})
        video.run_video(app,row)
        result = client.get(f'/video-runs/{identifier}').json()
        assert result['state'] == ('failed' if cloud_failure else 'succeeded'),result
        assert result['result']['explanation_state'] == ('failed' if cloud_failure else 'succeeded')
        history = store.list_ordinary(project_id=project)
        assert any(item['id'] == identifier and item['media_kind'] == 'video' for item in history['runs'])
        assert not any(item['id'] == identifier for item in store.list_ordinary(unassigned=True)['runs'])
        if confirmed:
            with store.engine.connect() as db:
                frozen = db.execute(text("SELECT context FROM video_calls WHERE job_id=:id AND call_key='assessment'"),{'id':identifier}).scalar_one()
            assert frozen['plan']['revision_id'] == original_plan['revision_id']
            assert frozen['plan']['entries'][0]['expected_equipment'] == ['excavator']
            for frame,timestamp in zip(frozen['frames'],video.probe(clip)['timestamps']):
                assert datetime.fromisoformat(frame['captured_at']) == datetime.fromisoformat('2026-10-20T09:00:00+03:00')+timedelta(seconds=timestamp)
            assert any(rule['kind'] == 'expected_equipment_missing' and rule['entry_id'] == original_plan['entries'][0]['id'] for rule in result['result']['rule_results'])
        assert result['result']['processed_frame_count'] == len(calls) == 3
        assert len(result['result']['selected_frames']) == 3
        output = clip.parent/'output.mp4'
        output.write_bytes(client.get(f'/video-runs/{identifier}/media').content)
        output_meta = video.probe(output)
        input_meta = video.probe(clip)
        assert output_meta['frame_count'] == 3
        expected_duration = input_meta['timestamps'][-1]+input_meta['last_frame_duration']
        output_stream = json.loads(video.command(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=duration','-of','json',str(output)]))['streams'][0]
        assert float(output_stream['duration']) == pytest.approx(expected_duration,abs=0.00005)
        assert output_meta['timestamps'] == pytest.approx(input_meta['timestamps'],abs=0.00003)
        assert (output_meta['width'],output_meta['height']) == (input_meta['width'],input_meta['height'])
        streams = json.loads(video.command(['ffprobe','-v','error','-show_streams','-of','json',str(output)]))['streams']
        assert any(s['codec_type']=='audio' for s in streams) == (not media_variant.startswith('silent'))
        if media_variant == 'delayed':
            import numpy as np
            assert input_meta['audio_offset_seconds'] == pytest.approx(-1)
            samples = np.frombuffer(video.command(['ffmpeg','-v','error','-i',str(output),'-map','0:a:0','-f','f32le','-ar','8000','pipe:1']),dtype='<f4')[800:3200]
            dominant = np.argmax(np.abs(np.fft.rfft(samples)))*8000/len(samples)
            assert dominant == pytest.approx(880,abs=8)
        with store.engine.begin() as db:
            db.execute(text("INSERT INTO video_calls(job_id,call_key,context) VALUES (:id,'unknown','{}')"),{'id':identifier})
        with pytest.raises(ValueError,match='video_cloud_outcome_uncertain'):
            video.cloud_call(store.engine,row,Observer(),'unknown','frame',{})
        retry = client.post(f'/video-runs/{identifier}/retry-cpu',headers={'Idempotency-Key':str(uuid4())})
        assert retry.status_code == 409
    store.close()


def test_mov_rotation_and_variable_timestamps(clip):
    rotated = clip.parent/'rotated.mov'
    video.command(['ffmpeg','-v','error','-display_rotation','90','-i',str(clip),'-c','copy',str(rotated)])
    meta = video.probe(rotated)
    assert (meta['width'],meta['height']) == (96,160)
    assert abs(meta['rotation']) == 90
    variable = clip.parent/'variable.mp4'
    video.command(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x96:rate=20:duration=0.15',
                   '-vf',r'setpts=if(eq(N\,0)\,0\,if(eq(N\,1)\,3\,10))','-fps_mode','vfr','-c:v','libx264',str(variable)])
    assert video.probe(variable)['timestamps'] == [0,0.15,0.5]


@pytest.mark.parametrize('change,code',[
    ({'duration':121},'video_limits_exceeded'),
    ({'width':5000},'video_limits_exceeded'),
    ({'fps':'61/1'},'video_limits_exceeded'),
    ({'codec':'vp9'},'video_codec_unsupported'),
    ({'times':[0,0.01]},'video_timestamps_invalid'),
    ({'times':[0,0]},'video_timestamps_invalid'),
])
def test_metadata_limits_reject_before_decode(monkeypatch,change,code):
    responses = [json.dumps({'format':{'duration':change.get('duration',1),'format_name':'mov,mp4'},'streams':[
        {'codec_type':'video','codec_name':change.get('codec','h264'),'avg_frame_rate':change.get('fps','30/1'),
         'width':change.get('width',1920),'height':1080}]}).encode(),
        json.dumps({'frames':[{'best_effort_timestamp_time':str(t)} for t in change.get('times',[0,0.1])]}).encode()]
    monkeypatch.setattr(video,'command',lambda *args,**kwargs:responses.pop(0))
    with pytest.raises(ValueError,match=code):
        video.probe('source')


def test_video_roles_and_general_run_fallback(accounts,clip,monkeypatch):
    from app.profiles.deepseek import snapshot
    make,store = accounts
    owner,owner_user = make()
    viewer,viewer_user = make()
    outsider,outsider_user = make()
    project_response = owner.post('/projects',json={'name':'Video permissions '+str(uuid4()),'timezone':'Europe/Moscow'})
    project = project_response.json()
    identifier,zone = project['id'],project['default_zone_id']
    with store.engine.begin() as db:
        db.execute(text("INSERT INTO project_members(project_id,user_id,role) VALUES (:project,:user,'viewer')"),{'project':identifier,'user':viewer_user['id']})
    profile_id = provision(store,'video-auth-'+str(uuid4()))
    profile,_ = store.require_authorized(profile_id)
    app = owner.app
    app.state.claim_loop = SimpleNamespace(runtime_binding=(profile_id,1))
    monkeypatch.setattr(store,'require_authorized',lambda *args:(profile,1))
    s3 = MemoryS3()
    app.state.artifacts = SimpleNamespace(client=s3,bucket='test')
    url = f'/runs/video?project_id={identifier}&zone_id={zone}&cloud_processing_consent=true&cloud_provider=yandex_ai_studio'
    assert viewer.post(url,content=clip.read_bytes(),headers={'Idempotency-Key':str(uuid4())}).status_code == 403
    assert outsider.post(url,content=clip.read_bytes(),headers={'Idempotency-Key':str(uuid4())}).status_code == 404
    submitted = owner.post(url,content=clip.read_bytes(),headers={'Idempotency-Key':str(uuid4())})
    assert submitted.status_code == 202,submitted.text
    job = submitted.json()['id']
    s3.data['test-result'] = b'0123456789'
    video.update(store.engine,job,state='failed',error='video_gpu_failed_retry_cpu_available',result={'artifact_key':'test-result'})
    for client in (owner,viewer):
        assert client.get(f'/video-runs/{job}').status_code == 200
        assert client.get(f'/runs/{job}').status_code == 200
        media = client.get(f'/video-runs/{job}/media',headers={'Range':'bytes=1-3'})
        assert media.status_code == 206 and media.content == b'123'
    for route in (f'/video-runs/{job}',f'/runs/{job}',f'/video-runs/{job}/media'):
        assert outsider.get(route).status_code == 404
    assert viewer.post(f'/video-runs/{job}/retry-cpu',headers={'Idempotency-Key':str(uuid4())}).status_code == 403
    assert outsider.post(f'/video-runs/{job}/retry-cpu',headers={'Idempotency-Key':str(uuid4())}).status_code == 404
    with store.engine.begin() as db:
        db.execute(text("UPDATE profile_authorizations SET state='revoked' WHERE profile_id=:id"),{'id':profile_id})
    denied = owner.post(f'/video-runs/{job}/retry-cpu',headers={'Idempotency-Key':str(uuid4())})
    assert denied.status_code == 409 and denied.json()['detail'] == 'profile_unauthorized'
    with store.engine.begin() as db:
        db.execute(text("UPDATE profile_authorizations SET state='enabled',revision=2 WHERE profile_id=:id"),{'id':profile_id})
    denied = owner.post(f'/video-runs/{job}/retry-cpu',headers={'Idempotency-Key':str(uuid4())})
    assert denied.status_code == 409 and denied.json()['detail'] == 'profile_unauthorized'
    with store.engine.begin() as db:
        db.execute(text("UPDATE profile_authorizations SET revision=1 WHERE profile_id=:id"),{'id':profile_id})
    key = str(uuid4())
    def retry(request_key):
        return owner.post(f'/video-runs/{job}/retry-cpu',headers={'Idempotency-Key':request_key})
    with ThreadPoolExecutor(max_workers=4) as pool:
        simultaneous = list(pool.map(retry,[key,key,str(uuid4()),str(uuid4())]))
    assert all(response.status_code == 202 for response in simultaneous),[r.text for r in simultaneous]
    assert len({response.json()['run_id'] for response in simultaneous}) == 1
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM video_jobs WHERE retry_of=:id'),{'id':job}).scalar_one() == 1
    retried = owner.post(f'/video-runs/{job}/retry-cpu',headers={'Idempotency-Key':key})
    assert retried.status_code == 202,retried.text
    assert owner.post(f'/video-runs/{job}/retry-cpu',headers={'Idempotency-Key':key}).json()['run_id'] == retried.json()['run_id']
    video.update(store.engine,retried.json()['run_id'],state='failed',error='test_cleanup')
    assert any(r['id'] == job for r in store.list_ordinary(user_id=owner_user['id'])['runs'])
    assert not any(r['id'] == job for r in store.list_ordinary(user_id=outsider_user['id'])['runs'])



def test_worker_recovers_transient_claim_and_unlock(monkeypatch):
    attempts = []
    ready = SimpleNamespace(value=True)
    ready.is_set = lambda:ready.value
    app = SimpleNamespace(state=SimpleNamespace(readiness=SimpleNamespace(ready=ready),store=SimpleNamespace(engine=None)))
    class Connection:
        invalidated = False
        closed = False
        def execute(self,*args):
            raise RuntimeError('database disconnected during unlock')
        def invalidate(self): self.invalidated = True
        def close(self): self.closed = True
    connection = Connection()
    def claim(_):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError('temporary database outage')
        ready.value = False
        return connection,None
    async def sleep(_): pass
    monkeypatch.setattr(video,'claim_video',claim)
    monkeypatch.setattr(video.asyncio,'sleep',sleep)
    asyncio.run(video.video_worker(app))
    assert len(attempts) == 2
    assert connection.invalidated and connection.closed


@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='isolated PostgreSQL required')
def test_claim_marks_interrupted_paid_job_failed():
    from app.adapters.postgres import PostgresStore
    store = PostgresStore(os.environ['TEST_DATABASE_URL'])
    row = persisted_job(store)
    identifier = row['id']
    with store.engine.begin() as db:
        db.execute(text("INSERT INTO video_calls(job_id,call_key,context) VALUES (:id,'paid-unknown','{}')"),{'id':identifier})
    connection,_ = video.claim_video(store.engine)
    if connection:
        connection.execute(text('SELECT pg_advisory_unlock(71903147)'))
        connection.close()
    with store.engine.connect() as db:
        row = db.execute(text('SELECT state,error FROM video_jobs WHERE id=:id'),{'id':identifier}).one()
        assert row.state == 'failed' and row.error == 'video_interrupted'
        assert db.execute(text('SELECT result FROM video_calls WHERE job_id=:id'),{'id':identifier}).one().result is None
    store.close()



def test_decoder_deadline_kills_stalled_process():
    process = subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],stdout=subprocess.PIPE,bufsize=0)
    try:
        with pytest.raises(ValueError,match='video_decode_timeout'):
            video.read_decoder(process,1,timeout=0.05)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()


def test_probe_selects_real_stream_after_cover(monkeypatch):
    commands = []
    responses = [json.dumps({'format':{'duration':1,'format_name':'mov,mp4'},'streams':[
        {'index':0,'codec_type':'video','codec_name':'mjpeg','disposition':{'attached_pic':1}},
        {'index':2,'codec_type':'video','codec_name':'h264','avg_frame_rate':'2/1','width':160,'height':96}]}).encode(),
        json.dumps({'frames':[{'best_effort_timestamp_time':'0'},{'best_effort_timestamp_time':'0.5'}]}).encode()]
    def command(args,**kwargs):
        commands.append(args)
        return responses.pop(0)
    monkeypatch.setattr(video,'command',command)
    assert video.probe('source')['stream_index'] == 2
    assert commands[1][commands[1].index('-select_streams')+1] == '2'
    for args in commands:
        assert args[args.index('-protocol_whitelist')+1] == 'file,pipe'
        assert args[args.index('-f')+1] == 'mov'


@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='isolated PostgreSQL required')
def test_cloud_calls_revalidate_authorization_and_revision(monkeypatch):
    from app.adapters.postgres import PostgresStore
    store = PostgresStore(os.environ['TEST_DATABASE_URL'])
    row = persisted_job(store)
    identifier,profile_id = row['id'],row['profile_id']
    calls = []
    class Observer:
        def call(self,*args,**kwargs):
            calls.append(1)
            return {'valid':True,'value':{}}
    observer = Observer()
    video.cloud_call(store.engine,row,observer,'frame-1','frame',{})
    with store.engine.begin() as db:
        db.execute(text("UPDATE profile_authorizations SET state='revoked' WHERE profile_id=:id"),{'id':profile_id})
    with pytest.raises(ValueError,match='profile_unauthorized'):
        video.cloud_call(store.engine,row,observer,'frame-2','frame',{})
    with store.engine.begin() as db:
        db.execute(text("UPDATE profile_authorizations SET state='enabled',revision=revision+1 WHERE profile_id=:id"),{'id':profile_id})
    with pytest.raises(ValueError,match='profile_unauthorized'):
        video.cloud_call(store.engine,row,observer,'assessment','assessment',{})
    assert len(calls) == 1
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM video_calls WHERE job_id=:id'),{'id':identifier}).scalar_one() == 1
    video.update(store.engine,identifier,state='failed',error='test_cleanup')
    store.close()



def test_playlist_rejected_with_forced_mov_demuxer(tmp_path):
    path = tmp_path/'fake.mp4'
    path.write_text('#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nhttps://127.0.0.1:1/never-fetch.ts\n#EXT-X-ENDLIST\n')
    with pytest.raises(ValueError,match='video_decode_failed'):
        video.probe(path)


@pytest.mark.parametrize('phase', ['probe', 'publication'])
@pytest.mark.parametrize('next_role', ['viewer', None])
def test_video_upload_rechecks_membership_in_both_publication_transactions(accounts, monkeypatch, phase, next_role):
    import hashlib
    from test_accounts import project
    make, store = accounts
    owner, _ = make()
    editor, user = make()
    own = project(owner)
    invitation = owner.post(f'/projects/{own["id"]}/invitations', json={'email': user['email'], 'role': 'editor'}).json()
    assert editor.post('/invitations/accept', json={'token': invitation['token']}).status_code == 200
    profile_id = provision(store, 'video-role-race-'+str(uuid4()))
    _, revision = store.require_authorized(profile_id)
    editor.app.state.claim_loop.runtime_binding = (profile_id, revision)
    editor.app.state.artifacts = SimpleNamespace()
    mutations = []

    def revoke_role():
        route = f'/projects/{own["id"]}/members/{user["id"]}'
        response = owner.delete(route) if next_role is None else owner.patch(route, json={'role': next_role})
        assert response.status_code == 200, response.text
        mutations.append(True)

    def probe(path):
        if phase == 'probe':
            revoke_role()
        return {'frame_count': 1}

    def put_file(artifacts, path, content_type):
        if phase == 'publication':
            revoke_role()
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        return 'video/sha256/'+digest, digest, len(payload)

    monkeypatch.setattr(video, 'probe', probe)
    monkeypatch.setattr(video, 'put_file', put_file)
    key = str(uuid4())
    response = editor.post('/runs/video', params={'project_id': own['id'], 'zone_id': own['default_zone_id'],
        'cloud_processing_consent': 'true', 'cloud_provider': 'yandex_ai_studio'},
        headers={'Idempotency-Key': key, 'Content-Type': 'video/mp4'}, content=b'local test upload')
    assert mutations == [True]
    assert response.status_code == (404 if next_role is None else 403), response.text
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM video_jobs WHERE project_id=:p'), {'p': own['id']}).scalar_one() == 0
        admission = db.execute(text('SELECT state FROM video_admissions WHERE project_id=:p AND request_key=:key'), {'p': own['id'], 'key': key}).scalar()
    assert admission == ('failed' if phase == 'publication' else None)
