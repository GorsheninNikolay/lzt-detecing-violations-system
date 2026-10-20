"""Bounded video ingestion, every-frame detection and durable one-shot cloud calls."""
import asyncio
from bisect import bisect_left
import hashlib
import io
import json
import logging
import math
import os
import re
import selectors
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
from time import monotonic

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image, ImageDraw
from sqlalchemy import text

from app.application.accounts import auth_required, current_user, require_project
from app.adapters.postgres import AdmissionStoreError
from app.config import Config
from app.profiles.deepseek import DeepSeek, EQUIPMENT, validate_consent

router = APIRouter()
MAX_BYTES = 200_000_000
SOURCE_INPUT_OPTIONS = ['-protocol_whitelist','file,pipe','-f','mov']
LIMITATIONS = ['Обе YOLO обработали каждый кадр. DeepSeek объясняет только выбранные моменты (до 8); события между ними не исключены.',
               'Звук сохранён в результате, но не анализируется и не передаётся модели.']


def command(args, timeout=60):
    try:
        return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout).stdout
    except FileNotFoundError:
        raise ValueError('video_ffmpeg_unavailable') from None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise ValueError('video_decode_failed') from None


def probe(path):
    data = json.loads(command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', *SOURCE_INPUT_OPTIONS, str(path)]))
    streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if len(streams) != 1:
        raise ValueError('video_stream_invalid')
    stream = streams[0]
    stream_index = int(stream.get('index',0))
    try:
        duration = float(data['format']['duration'])
        fps = float(Fraction(stream['avg_frame_rate']))
        width, height = int(stream['width']), int(stream['height'])
    except (KeyError, ValueError, ZeroDivisionError):
        raise ValueError('video_metadata_invalid') from None
    if (not math.isfinite(duration) or not 0 < duration <= 120 or not 0 < fps <= 60
            or min(width, height) < 2 or max(width, height) > 4096 or min(width, height) > 2160):
        raise ValueError('video_limits_exceeded')
    if stream.get('codec_name') not in ('h264', 'hevc') or not {'mov', 'mp4'} & set(data['format'].get('format_name', '').split(',')):
        raise ValueError('video_codec_unsupported')
    frames = json.loads(command(['ffprobe', '-v', 'error', '-select_streams', str(stream_index), '-show_frames', '-read_intervals', '%+#7202',
                                '-show_entries', 'frame=best_effort_timestamp_time,pkt_duration_time,duration_time', '-of', 'json', *SOURCE_INPUT_OPTIONS, str(path)]))['frames']
    timestamps = [float(f['best_effort_timestamp_time']) for f in frames]
    if (not timestamps or len(timestamps) > 7201 or any(not math.isfinite(t) for t in timestamps)
            or any(b <= a or b-a < 1/60 - 0.0001 for a,b in zip(timestamps, timestamps[1:]))):
        raise ValueError('video_timestamps_invalid')
    origin = timestamps[0]
    timestamps = [t-origin for t in timestamps]
    if timestamps[-1] > 120:
        raise ValueError('video_limits_exceeded')
    rotation = next((int(s.get('rotation', 0)) for s in stream.get('side_data_list', []) if 'rotation' in s), int(stream.get('tags', {}).get('rotate', 0)))
    if rotation % 180:
        width, height = height, width
    factor = min(1, 1280 / width, 720 / height)
    out_width, out_height = max(2, int(width*factor)//2*2), max(2, int(height*factor)//2*2)
    return {'duration_seconds': duration, 'fps': fps, 'width': width, 'height': height,
            'rotation': rotation, 'stream_index':stream_index, 'codec': stream['codec_name'], 'frame_count': len(timestamps),
            'timestamps': timestamps, 'output_width': out_width, 'output_height': out_height,
            'audio_offset_seconds':float(data['format'].get('start_time',0))-origin,
            'last_frame_duration': max(1/60, float(frames[-1].get('duration_time',frames[-1].get('pkt_duration_time', 1/fps))))}


def selected_indices(timestamps):
    if isinstance(timestamps,int):
        timestamps = range(timestamps)
    count = len(timestamps)
    if count <= 8:
        return list(range(count))
    selected = set()
    for ordinal in range(8):
        target = timestamps[0]+ordinal*(timestamps[-1]-timestamps[0])/7
        right = bisect_left(timestamps,target)
        candidates = [i for i in (right-1,right) if 0 <= i < count]
        selected.add(min(candidates,key=lambda i:(abs(timestamps[i]-target),i)))
    return sorted(selected)


def update(engine, identifier, **fields):
    allowed = {'state','stage','progress','device','result','error'}
    if not fields or not set(fields) <= allowed:
        raise ValueError('invalid_video_update')
    assignments = []
    for key in fields:
        assignments.append(f'{key}=CAST(:{key} AS jsonb)' if key in {'device','result'} else f'{key}=:{key}')
    params = {key: json.dumps(value) if key in {'device','result'} else value for key,value in fields.items()}
    with engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
        db.execute(text('UPDATE video_jobs SET ' + ','.join(assignments) + ',updated_at=clock_timestamp() WHERE id=:id'), {'id':identifier, **params})


def put_file(artifacts, path, content_type):
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    key = 'video/sha256/' + digest
    try:
        with path.open('rb') as source:
            artifacts.client.put_object(Bucket=artifacts.bucket, Key=key, Body=source, ContentType=content_type, IfNoneMatch='*')
    except Exception as exc:
        if getattr(exc,'response',{}).get('ResponseMetadata',{}).get('HTTPStatusCode') not in (409,412):
            raise
    measured = hashlib.sha256()
    response = artifacts.client.get_object(Bucket=artifacts.bucket, Key=key)
    try:
        for chunk in iter(lambda: response['Body'].read(1024*1024), b''):
            measured.update(chunk)
    finally:
        response['Body'].close()
    if measured.hexdigest() != digest:
        raise ValueError('artifact_integrity_failed')
    return key, digest, path.stat().st_size



def put_job_file(engine, artifacts, job_id, path, content_type):
    with path.open('rb') as source:
        key = 'video/sha256/' + hashlib.file_digest(source, 'sha256').hexdigest()
    with engine.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock_shared(804298270115)'))
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,804298270116))'), {'key': key})
        db.execute(text('INSERT INTO video_artifacts(job_id,object_key) VALUES (:id,:key) ON CONFLICT DO NOTHING'),
                   {'id': job_id, 'key': key})
    return put_file(artifacts, path, content_type)


def require_locked_video_writer(db, request, project):
    if not auth_required():
        return
    role = db.execute(text('SELECT role FROM project_members WHERE project_id=:project AND user_id=:user'),
                      {'project': project, 'user': current_user(request)['id']}).scalar()
    if role is None:
        raise HTTPException(404, 'project_not_found')
    if role not in ('owner', 'editor'):
        raise HTTPException(403, 'insufficient_project_role')


def load_job(request, identifier, write=False):
    with request.app.state.store.engine.connect() as db:
        row = db.execute(text('SELECT * FROM video_jobs WHERE id=:id'), {'id':identifier}).mappings().first()
    if not row:
        raise HTTPException(404, 'run_not_found')
    require_project(request, row['project_id'], write=write)
    return dict(row)


def public_job(row):
    return {'id':str(row['id']), 'run_id':str(row['id']), 'media_kind':'video',
            **{key: row[key] for key in ('state','stage','progress','device','result','error')},
            'metadata':{k:v for k,v in row['metadata'].items() if k != 'timestamps'},
            'context': row['context'], 'retry_eligible':False,
            'retry_cpu_eligible':row.get('error') == 'video_gpu_failed_retry_cpu_available'}


@router.post('/runs/video')
async def upload_video(request: Request):
    params = request.query_params
    try:
        project, zone = uuid.UUID(params['project_id']), uuid.UUID(params['zone_id'])
        key = request.headers['Idempotency-Key']
        if not re.fullmatch(r'[!-~]{1,128}', key):
            raise ValueError()
        if params.get('cloud_processing_consent') != 'true':
            raise ValueError('cloud_consent_required')
        started = params.get('capture_started_at')
        if started and datetime.fromisoformat(started).utcoffset() is None:
            raise ValueError('invalid_capture_time')
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc) if str(exc) in ('cloud_consent_required','invalid_capture_time') else 'invalid_video_request') from None
    require_project(request, project, write=True)
    with request.app.state.store.engine.connect() as db:
        actual = db.execute(text('SELECT project_id FROM site_zones WHERE id=:id'), {'id':zone}).scalar()
    if actual != project:
        raise HTTPException(400, 'invalid_plan_binding')
    context = {'project_id':str(project), 'zone_id':str(zone), 'cloud_processing_consent':True,
               'cloud_provider':params.get('cloud_provider'), 'capture_started_at':started,
               'requested_plan_revision_id':params.get('plan_revision_id')}
    with tempfile.TemporaryDirectory(prefix='video-upload-') as directory:
        path = Path(directory) / 'source'
        size = 0
        measured = hashlib.sha256()
        with path.open('wb') as target:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, 'video_size_exceeded')
                target.write(chunk)
                measured.update(chunk)
        if not size:
            raise HTTPException(400, 'invalid_video_file')
        source_hash = measured.hexdigest()
        request_hash = hashlib.sha256(json.dumps({'sha':source_hash,'context':context}, sort_keys=True).encode()).hexdigest()
        with request.app.state.store.engine.connect() as db:
            existing = db.execute(text('SELECT * FROM video_jobs WHERE project_id=:project AND request_key=:key'), {'project':project,'key':key}).mappings().first()
        if existing:
            if existing['request_hash'] != request_hash:
                raise HTTPException(409,'idempotency_key_conflict')
            return JSONResponse(public_job(existing),status_code=202)
        if not request.app.state.readiness.ready.is_set():
            raise HTTPException(503, 'service_not_ready')
        binding = request.app.state.claim_loop.runtime_binding
        if not binding:
            raise HTTPException(503, 'profile_unauthorized')
        try:
            snapshot, authorization_revision = await asyncio.to_thread(request.app.state.store.require_authorized, *binding)
        except (AdmissionStoreError,ValueError):
            raise HTTPException(503,'profile_unauthorized') from None
        try:
            validate_consent(context, snapshot)
            metadata = await asyncio.to_thread(probe, path)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            raise HTTPException(400, str(exc) if re.fullmatch(r'[a-z][a-z0-9_]{0,100}',str(exc)) else 'invalid_video_file') from None
        admission_created = False
        try:
            with request.app.state.store.engine.begin() as db:
                db.execute(text('SELECT pg_advisory_xact_lock_shared(804298270115)'))
                if not db.execute(text('SELECT id FROM site_projects WHERE id=:project FOR UPDATE'), {'project': project}).first():
                    raise HTTPException(404, 'project_not_found')
                require_locked_video_writer(db, request, project)
                if db.execute(text("SELECT 1 FROM deleted_request_keys WHERE kind='video' AND request_key=:key"), {'key': str(project)+':'+key}).first():
                    raise HTTPException(410, 'resource_deleted')
                prior = db.execute(text('SELECT request_hash,state FROM video_admissions WHERE project_id=:project AND request_key=:key FOR UPDATE'), {'project': project, 'key': key}).first()
                if prior and prior.request_hash != request_hash:
                    raise HTTPException(409, 'idempotency_key_conflict')
                if prior and prior.state == 'publishing':
                    raise HTTPException(409, 'submission_in_progress')
                db.execute(text('''INSERT INTO video_admissions(project_id,request_key,request_hash,source_key,state)
                    VALUES (:project,:key,:hash,:source,'publishing') ON CONFLICT(project_id,request_key)
                    DO UPDATE SET state='publishing' '''),
                    {'project': project, 'key': key, 'hash': request_hash, 'source': 'video/sha256/'+source_hash})
            admission_created = True
            source_key, _, _ = await asyncio.to_thread(put_file, request.app.state.artifacts,path,'video/mp4')
            identifier = uuid.uuid4()
            with request.app.state.store.engine.begin() as db:
                db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
                if db.execute(text("SELECT 1 FROM deleted_request_keys WHERE kind='video' AND request_key=:key"), {'key': str(project)+':'+key}).first():
                    raise HTTPException(410, 'resource_deleted')
                if not db.execute(text('SELECT id FROM site_projects WHERE id=:project FOR UPDATE'), {'project': project}).first():
                    raise HTTPException(404, 'project_not_found')
                require_locked_video_writer(db, request, project)
                db.execute(text('SELECT id FROM site_zones WHERE id=:zone FOR UPDATE'),{'zone':zone})
                revision = db.execute(text('SELECT id FROM zone_plan_revisions WHERE zone_id=:zone ORDER BY revision_number DESC LIMIT 1'), {'zone':zone}).scalar()
                if params.get('plan_revision_id') and str(revision) != params['plan_revision_id']:
                    raise HTTPException(409, 'plan_revision_conflict')
                context['plan_revision_id'] = str(revision) if revision else None
                db.execute(text('''INSERT INTO video_jobs(id,project_id,zone_id,request_key,request_hash,source_key,source_sha256,source_size,context,profile_snapshot,metadata,profile_id,authorization_revision)
                    VALUES (:id,:project,:zone,:key,:hash,:source,:sha,:size,CAST(:context AS jsonb),CAST(:profile AS jsonb),CAST(:metadata AS jsonb),:profile_id,:authorization_revision) ON CONFLICT(project_id,request_key) DO NOTHING'''),
                    {'id':identifier,'project':project,'zone':zone,'key':key,'hash':request_hash,'source':source_key,'sha':source_hash,'size':size,
                     'context':json.dumps(context),'profile':json.dumps(snapshot),'metadata':json.dumps(metadata),
                     'profile_id':binding[0],'authorization_revision':authorization_revision})
                saved = db.execute(text('SELECT * FROM video_jobs WHERE project_id=:project AND request_key=:key'), {'project':project,'key':key}).mappings().one()
                if saved['request_hash'] != request_hash:
                    raise HTTPException(409,'idempotency_key_conflict')
                db.execute(text('DELETE FROM video_admissions WHERE project_id=:project AND request_key=:key'), {'project': project, 'key': key})
            return JSONResponse(public_job(saved),status_code=202)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503,'video_publication_failed') from None
        finally:
            if admission_created:
                with request.app.state.store.engine.begin() as db:
                    db.execute(text('SELECT pg_advisory_xact_lock_shared(804298270115)'))
                    db.execute(text("UPDATE video_admissions SET state='failed' WHERE project_id=:project AND request_key=:key AND request_hash=:hash"), {'project': project, 'key': key, 'hash': request_hash})


@router.get('/video-runs/{identifier}')
def read_video(identifier: uuid.UUID, request: Request):
    return public_job(load_job(request, identifier))


@router.get('/video-runs/{identifier}/media')
def video_media(identifier: uuid.UUID, request: Request):
    row = load_job(request,identifier)
    key = (row.get('result') or {}).get('artifact_key')
    if not key:
        raise HTTPException(404,'video_result_missing')
    client = request.app.state.artifacts.client
    bucket = request.app.state.artifacts.bucket
    size = client.head_object(Bucket=bucket,Key=key)['ContentLength']
    value = request.headers.get('range')
    start,end = 0,size-1
    if value:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)',value)
        if not match or not any(match.groups()):
            return JSONResponse({'code':'invalid_range'},416,headers={'Content-Range':f'bytes */{size}'})
        left,right = match.groups()
        start,end = (int(left),min(int(right),size-1) if right else size-1) if left else (max(0,size-int(right)),size-1)
        if start >= size or start > end:
            return JSONResponse({'code':'invalid_range'},416,headers={'Content-Range':f'bytes */{size}'})
    response = client.get_object(Bucket=bucket,Key=key,Range=f'bytes={start}-{end}')
    def chunks():
        try:
            yield from iter(lambda:response['Body'].read(1024*1024),b'')
        finally:
            response['Body'].close()
    headers = {'Accept-Ranges':'bytes','Content-Length':str(end-start+1), 'Content-Disposition':'inline; filename="analysis.mp4"',
               'Cache-Control':'private, no-store'}
    if value:
        headers['Content-Range'] = f'bytes {start}-{end}/{size}'
    return StreamingResponse(chunks(),status_code=206 if value else 200,media_type='video/mp4',headers=headers)


def video_detectors(force_cpu=False):
    import platform
    import torch
    from importlib.metadata import version
    from app.profiles.yolo import Detectors
    device, fallback = 'cpu', 'На CPU обработка может занять значительно больше времени.'
    if not force_cpu and torch.cuda.is_available():
        try:
            candidate = Detectors('cuda:0')
            sample = io.BytesIO()
            Image.new('RGB',(64,64)).save(sample,format='JPEG')
            candidate.detect(sample.getvalue(),'gpu-compatibility-check')
            detector,device,fallback = candidate,'cuda:0',None
        except Exception:
            detector = Detectors('cpu')
            fallback = 'Проверка обеих YOLO на GPU не прошла. До запуска выбрана CPU; обработка медленнее.'
    else:
        detector = Detectors('cpu')
    driver = None
    if device.startswith('cuda'):
        try:
            driver = command(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],timeout=5).decode().splitlines()[0]
        except (ValueError,IndexError):
            driver = 'unreported'
    evidence = {'actual_device':device, 'driver_version':driver, 'torch':torch.__version__, 'cuda_build':torch.version.cuda,
                'ultralytics':version('ultralytics'), 'platform':platform.platform(),
                'gpu_name':torch.cuda.get_device_name(0) if device.startswith('cuda') else None,
                'weights':[{k:m[k] for k in ('id','sha256')} for m in detector.manifest['models']],
                'warning':fallback}
    return detector,evidence


def draw_detections(image, evidence):
    draw = ImageDraw.Draw(image)
    colors = ('#20d6ee','#ffb02e')
    for index,model in enumerate(evidence['models']):
        for detection in model['detections']:
            box = detection['box']
            bounds = (box[0]*image.width,box[1]*image.height,box[2]*image.width,box[3]*image.height)
            draw.rectangle(bounds,outline=colors[index % 2],width=3)
            label = f"{model['model_id']} {detection['raw_class']} {detection['score']:.2f}"
            draw.text((bounds[0]+3,bounds[1]+3),label,fill=colors[index % 2],stroke_width=1,stroke_fill='black')
    draw.rectangle((0,0,min(image.width,380),20),fill='black')
    draw.text((5,4),'YOLO 1 cyan | YOLO 2 orange',fill='white')


def require_video_authorization(db,row):
    allowed = db.execute(text("""SELECT profile_id FROM profile_authorizations
        WHERE profile_id=:profile AND revision=:revision AND state='enabled' FOR SHARE"""),
        {'profile':row.get('profile_id'),'revision':row.get('authorization_revision')}).scalar()
    if allowed is None:
        raise ValueError('profile_unauthorized')
    validate_consent(row['context'],row['profile_snapshot'])


def cloud_call(engine, row, observer, key, kind, context, image=None, images=None):
    # A reservation without a result is an unknown paid outcome and is never replayed.
    with engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
        previous = db.execute(text('SELECT result FROM video_calls WHERE job_id=:id AND call_key=:key'),{'id':row['id'],'key':key}).first()
        if previous:
            if previous.result is None:
                raise ValueError('video_cloud_outcome_uncertain')
            return previous.result
        require_video_authorization(db,row)
        db.execute(text('INSERT INTO video_calls(job_id,call_key,context) VALUES (:id,:key,CAST(:context AS jsonb))'),
                   {'id':row['id'],'key':key,'context':json.dumps(context)})
    result = observer.call(kind,context,image,120,images=images)
    with engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
        db.execute(text('UPDATE video_calls SET result=CAST(:result AS jsonb) WHERE job_id=:id AND call_key=:key'),
                   {'id':row['id'],'key':key,'result':json.dumps(result)})
    if result.get('valid') is not True:
        raise ValueError('deepseek_response_invalid')
    return result


def read_decoder(decoder,size,timeout=30,allow_eof=False,cancelled=lambda:False):
    deadline = monotonic()+timeout
    result = bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(decoder.stdout,selectors.EVENT_READ)
        while len(result) < size:
            remaining = deadline-monotonic()
            if cancelled() or remaining <= 0:
                decoder.kill()
                decoder.wait(timeout=5)
                raise ValueError('video_interrupted' if cancelled() else 'video_decode_timeout')
            if not selector.select(min(remaining,0.5)):
                continue
            chunk = os.read(decoder.stdout.fileno(),size-len(result))
            if not chunk:
                if allow_eof and not result:
                    return b''
                raise ValueError('video_frame_count_mismatch')
            result.extend(chunk)
    return bytes(result)


def run_video(app, row):
    engine,artifacts = app.state.store.engine,app.state.artifacts
    identifier = row['id']
    decoder = None
    try:
        with tempfile.TemporaryDirectory(prefix='video-analysis-') as directory:
            root = Path(directory)
            source = root/'source.mp4'
            response = artifacts.client.get_object(Bucket=artifacts.bucket,Key=row['source_key'])
            measured = hashlib.sha256()
            try:
                with source.open('wb') as target:
                    for chunk in iter(lambda:response['Body'].read(1024*1024),b''):
                        target.write(chunk)
                        measured.update(chunk)
            finally:
                response['Body'].close()
            if measured.hexdigest() != row['source_sha256'] or source.stat().st_size != row['source_size']:
                raise ValueError('artifact_integrity_failed')
            detector,device = video_detectors(row['context'].get('force_cpu',False))
            update(engine,identifier,stage='yolo',device=device)
            metadata = row['metadata']
            width,height = metadata['output_width'],metadata['output_height']
            timestamps = metadata['timestamps']
            selected = selected_indices(timestamps)
            selected_frames = []
            raw_size = width*height*3
            with (root/'decode.log').open('wb') as errors:
                decoder = subprocess.Popen(['ffmpeg','-v','error',*SOURCE_INPUT_OPTIONS,'-i',str(source),'-map',f'0:{metadata.get("stream_index",0)}','-an','-sn','-vf',f'scale={width}:{height}',
                    '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=errors,bufsize=0)
                with (root/'detections.jsonl').open('w') as ledger, (root/'frames.ffconcat').open('w') as concat:
                    concat.write('ffconcat version 1.0\n')
                    for index,timestamp in enumerate(timestamps):
                        raw = read_decoder(decoder,raw_size,cancelled=lambda:not app.state.readiness.ready.is_set())
                        image = Image.frombytes('RGB',(width,height),bytes(raw))
                        encoded = io.BytesIO()
                        image.save(encoded,format='JPEG',quality=92)
                        frame_id = str(uuid.uuid5(identifier,f'frame/{index}'))
                        try:
                            evidence = detector.detect(encoded.getvalue(),frame_id)
                        except Exception:
                            if device['actual_device'].startswith('cuda'):
                                raise ValueError('video_gpu_failed_retry_cpu_available') from None
                            raise
                        ledger.write(json.dumps({'frame':index,'timestamp_seconds':timestamp,'detectors':evidence})+'\n')
                        if index in selected:
                            selected_frames.append({'input_id':frame_id,'timestamp_seconds':timestamp,'ordinal':index,
                                'sha256':hashlib.sha256(encoded.getvalue()).hexdigest(),'image':encoded.getvalue(),'detectors':evidence})
                        draw_detections(image,evidence)
                        frame_path = root/f'{index:05}.jpg'
                        image.save(frame_path,format='JPEG',quality=90)
                        duration = timestamps[index+1]-timestamp if index+1 < len(timestamps) else metadata['last_frame_duration']
                        concat.write(f"file '{frame_path.name}'\noption framerate 60000\nduration {duration:.9f}\n")
                        if index % 10 == 0:
                            update(engine,identifier,progress=(index+1)/len(timestamps))
                    concat.write(f"file '{len(timestamps)-1:05}.jpg'\n")
                    if read_decoder(decoder,1,allow_eof=True,cancelled=lambda:not app.state.readiness.ready.is_set()) or decoder.wait(timeout=30) != 0:
                        raise ValueError('video_frame_count_mismatch')
            evidence_key,_,_ = put_job_file(engine,artifacts,identifier,root/'detections.jsonl','application/x-ndjson')
            update(engine,identifier,stage='assembly',progress=1)
            output = root/'analysis.mp4'
            duration = timestamps[-1]+metadata['last_frame_duration']
            # Concat retains frame PTS but needs an explicit terminal packet duration for silent MP4s.
            command(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(root/'frames.ffconcat'),*SOURCE_INPUT_OPTIONS,'-i',str(source),
                '-map','0:v:0','-map','1:a:0?','-c:v','libx264','-pix_fmt','yuv420p','-fps_mode','vfr',
                '-bsf:v',f'setts=pts=PTS:dts=DTS:duration={metadata["last_frame_duration"]}/TB',
                '-enc_time_base','1:90000','-video_track_timescale','90000',
                '-af',f'atrim=start={-metadata.get("audio_offset_seconds",0)},asetpts=PTS-({-metadata.get("audio_offset_seconds",0)})/TB,aresample=async=1:first_pts=0',
                '-c:a','aac','-t',str(duration),'-movflags','+faststart',str(output)],timeout=600)
            output_key,output_hash,output_size = put_job_file(engine,artifacts,identifier,output,'video/mp4')
            saved_frames = []
            for frame in selected_frames:
                path = root/(frame['input_id']+'.jpg')
                path.write_bytes(frame['image'])
                frame_key,_,_ = put_job_file(engine,artifacts,identifier,path,'image/jpeg')
                saved_frames.append({k:v for k,v in frame.items() if k not in ('image','detectors')} | {'artifact_key':frame_key})
            result = {'artifact_key':output_key,'sha256':output_hash,'size':output_size,
                      'video_url':f'/api/video-runs/{identifier}/media','processed_frame_count':len(timestamps),
                      'detections_artifact_key':evidence_key,'selected_frames':saved_frames,'assessment':None,
                      'limitations':LIMITATIONS,'explanation_state':'pending'}
            update(engine,identifier,result=result,stage='deepseek')
            observer = DeepSeek(row['profile_snapshot'],Config.from_env().api_key_for(row['profile_snapshot']))
            from app.application.deepseek_runtime import observation_context, class_state
            from app.domain.site_analysis import compare_equipment
            frames,images = [],[]
            started = row['context'].get('capture_started_at')
            for frame in selected_frames:
                context = {k:frame[k] for k in ('input_id','ordinal','sha256','detectors')}
                context.update({k:row['profile_snapshot'][k] for k in ('instruction_version','schema_version')})
                value = cloud_call(engine,row,observer,'frame/'+frame['input_id'],'frame',context,frame['image'])
                value['detectors'] = frame['detectors']
                summary = observation_context({**frame,'artifact_id':frame['input_id']},value)
                summary['captured_at'] = (datetime.fromisoformat(started)+timedelta(seconds=frame['timestamp_seconds'])).isoformat() if started else None
                summary['timestamp_seconds'] = frame['timestamp_seconds']
                frames.append(summary)
                images.append((frame['input_id'],frame['image']))
                result['selected_frames'][len(frames)-1]['assessment'] = value['value']
                update(engine,identifier,result=result)
            plan = None
            revision = row['context'].get('plan_revision_id')
            if revision and started:
                with engine.connect() as db:
                    entries = db.execute(text('''SELECT e.id,w.title,e.stage_key,e.starts_at,e.ends_at,e.state,
                        e.expected_equipment,e.allowed_equipment,e.excluded_equipment FROM zone_plan_entries e
                        JOIN catalog_works w ON w.id=e.catalog_work_id WHERE e.revision_id=:id ORDER BY e.starts_at,e.id'''), {'id':revision}).mappings().all()
                plan = {'revision_id':revision,'zone_id':str(row['zone_id']), 'entries':[
                    {**e,'id':str(e['id']),'starts_at':e['starts_at'].isoformat(),'ends_at':e['ends_at'].isoformat()} for e in entries]}
            rules = []
            if plan:
                entries = [{**e,'starts_at':datetime.fromisoformat(e['starts_at']),'ends_at':datetime.fromisoformat(e['ends_at'])} for e in plan['entries']]
                observations = [{'input_id':f['input_id'],'class_name':name,'state':class_state(f,name)} for f in frames for name in EQUIPMENT]
                rules = compare_equipment(entries,[f['captured_at'] for f in frames],observations,[f['input_id'] for f in frames],set(EQUIPMENT),frames=frames)
            frozen = {'frames':frames,'rule_results':rules,'plan':plan,'history':[],'zone_id':str(row['zone_id']),
                'declared_context':row['context'],'comparison_method':'video_selected_moments_only','history_eligible':False,
                **{k:row['profile_snapshot'][k] for k in ('instruction_version','schema_version')}}
            assessment = cloud_call(engine,row,observer,'assessment','assessment',frozen,images=images)
            result.update(assessment=assessment['value'],explanation_state='succeeded',rule_results=rules)
            if not started:
                result['limitations'] = [*LIMITATIONS,'Время начала съёмки неизвестно: выводы о соблюдении сроков плана не выполняются.']
            update(engine,identifier,state='succeeded',stage='complete',result=result)
    except Exception as exc:
        code = str(exc)
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,100}',code):
            code = 'video_processing_failed'
        with engine.connect() as db:
            existing = db.execute(text('SELECT result,device FROM video_jobs WHERE id=:id'),{'id':identifier}).first()
        if existing and existing.result:
            partial = dict(existing.result)
            partial['explanation_state'] = 'failed'
            partial['explanation_error'] = code
            update(engine,identifier,result=partial)
        update(engine,identifier,state='failed',error=code)
    finally:
        if decoder and decoder.poll() is None:
            decoder.kill()
            decoder.wait(timeout=5)


def claim_video(engine):
    connection = engine.connect()
    try:
        if not connection.execute(text('SELECT pg_try_advisory_lock(71903147)')).scalar():
            connection.close()
            return None,None
        with engine.begin() as db:
            db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
            db.execute(text("UPDATE video_jobs SET state='failed',error='video_interrupted',updated_at=clock_timestamp() WHERE state='running'"))
            row = db.execute(text("SELECT * FROM video_jobs WHERE state='queued' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED")).mappings().first()
            if row:
                db.execute(text("UPDATE video_jobs SET state='running' WHERE id=:id"),{'id':row['id']})
        return connection,dict(row) if row else None
    except Exception:
        connection.invalidate()
        connection.close()
        raise


async def video_worker(app):
    while app.state.readiness.ready.is_set():
        connection,row = None,None
        try:
            connection,row = await asyncio.to_thread(claim_video,app.state.store.engine)
            if row:
                await asyncio.to_thread(run_video,app,row)
        except Exception:
            logging.getLogger(__name__).exception('Video worker will retry after a transient failure')
            await asyncio.sleep(5)
        finally:
            if connection:
                try:
                    await asyncio.to_thread(connection.execute,text('SELECT pg_advisory_unlock(71903147)'))
                except Exception:
                    connection.invalidate()
                    logging.getLogger(__name__).exception('Video worker connection invalidated after unlock failure')
                finally:
                    await asyncio.to_thread(connection.close)
        if not row:
            await asyncio.sleep(1)


@router.post('/video-runs/{identifier}/retry-cpu')
def retry_video_cpu(identifier:uuid.UUID,request:Request):
    load_job(request,identifier,write=True)
    key = request.headers.get('Idempotency-Key','')
    if not re.fullmatch(r'[!-~]{1,128}',key):
        raise HTTPException(400,'invalid_idempotency_key')
    with request.app.state.store.engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
        row = dict(db.execute(text('SELECT * FROM video_jobs WHERE id=:id FOR UPDATE'),{'id':identifier}).mappings().one())
        existing_key = db.execute(text('SELECT * FROM video_jobs WHERE project_id=:project AND request_key=:key'),{'project':row['project_id'],'key':key}).mappings().first()
        if existing_key and existing_key['retry_of'] != identifier:
            raise HTTPException(409,'idempotency_key_conflict')
        successor = db.execute(text('SELECT * FROM video_jobs WHERE retry_of=:id'),{'id':identifier}).mappings().first()
        if successor:
            return JSONResponse(public_job(successor),status_code=202)
        if row['state'] != 'failed' or row['error'] != 'video_gpu_failed_retry_cpu_available' or row['context'].get('force_cpu'):
            raise HTTPException(409,'retry_ineligible')
        if db.execute(text('SELECT 1 FROM video_calls WHERE job_id=:id LIMIT 1'),{'id':identifier}).first():
            raise HTTPException(409,'provider_call_not_replayable')
        try:
            require_video_authorization(db,row)
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from None
        context = {**row['context'],'force_cpu':True,'retry_of':str(identifier)}
        identity = hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
        new_id = uuid.uuid4()
        db.execute(text("""INSERT INTO video_jobs(id,project_id,zone_id,request_key,request_hash,source_key,source_sha256,source_size,context,
            profile_snapshot,metadata,profile_id,authorization_revision,retry_of)
            VALUES (:id,:project,:zone,:key,:hash,:source,:sha,:size,CAST(:context AS jsonb),CAST(:profile AS jsonb),CAST(:metadata AS jsonb),
                :profile_id,:authorization_revision,:retry_of) ON CONFLICT(project_id,request_key) DO NOTHING"""),
            {'id':new_id,'project':row['project_id'],'zone':row['zone_id'],'key':key,'hash':identity,
             'source':row['source_key'],'sha':row['source_sha256'],'size':row['source_size'],'context':json.dumps(context),
             'profile':json.dumps(row['profile_snapshot']),'metadata':json.dumps(row['metadata']),
             'profile_id':row['profile_id'],'authorization_revision':row['authorization_revision'],'retry_of':identifier})
        saved = db.execute(text('SELECT * FROM video_jobs WHERE project_id=:project AND request_key=:key'),{'project':row['project_id'],'key':key}).mappings().one()
        if saved['retry_of'] != identifier:
            raise HTTPException(409,'idempotency_key_conflict')
        return JSONResponse(public_job(saved),status_code=202)
