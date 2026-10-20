"""Resumable CLI acceptance for XLSX import and one paid video analysis.

The private receipt is the source of identity across retries. Keep it and its
source clip together; an uncertain submission is reconciled with the same key.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import time
from urllib import error, request
from urllib.parse import urlencode, urlsplit
import uuid


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'w') as target:
            json.dump(value, target, ensure_ascii=False, indent=2)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_private(path, payload):
    if path.is_symlink():
        raise RuntimeError('artifact_symlink_rejected')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'wb') as target:
        target.write(payload)
    path.chmod(0o600)


class Client:
    def __init__(self, base, origin):
        self.base, self.origin = base, origin
        self.opener = request.build_opener(NoRedirect(), request.HTTPCookieProcessor(CookieJar()))

    def call(self, path, method='GET', body=None, raw=None, headers=None, allowed=(200,), timeout=60):
        if not path.startswith('/') or path.startswith('//') or urlsplit(path).netloc:
            raise RuntimeError('unexpected_response_url')
        supplied = {'Origin':self.origin, 'Content-Type':'application/json'} | (headers or {})
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        try:
            response = self.opener.open(request.Request(self.base+path, data=data, headers=supplied, method=method), timeout=timeout)
        except error.HTTPError as exc:
            response = exc
        with response:
            payload, status, returned = response.read(), response.code, dict(response.headers)
        if status not in allowed:
            raise RuntimeError(f'http_{status}_{method}_{urlsplit(path).path}')
        return payload, status, returned

    def json(self, path, method='GET', body=None, **kwargs):
        payload, _, _ = self.call(path, method, body=body, **kwargs)
        return json.loads(payload)

    def login(self, credentials):
        _, status, _ = self.call('/api/account/login','POST',body=credentials,allowed=(200,401))
        if status == 401:
            self.call('/api/account/register','POST',body=credentials,allowed=(200,409))
            self.call('/api/account/login','POST',body=credentials)
        session = self.json('/api/account/session')
        if not session.get('user',{}).get('id'):
            raise RuntimeError('account_session_missing')
        return session['user']['id']


def canonical_entry(entry):
    return {'catalog_work_id':entry['catalog_work_id'],
            'start_at':datetime.fromisoformat(entry.get('start_at',entry.get('starts_at'))).astimezone(timezone.utc).isoformat(),
            'end_at':datetime.fromisoformat(entry.get('end_at',entry.get('ends_at'))).astimezone(timezone.utc).isoformat(),
            **{key:entry[key] for key in ('state','stage_key','expected_equipment','allowed_equipment','excluded_equipment')}}


def assert_plan(plan, body):
    if (plan['revision_number'] != body['expected_revision']+1
            or sorted(map(canonical_entry,plan['entries']),key=lambda e:json.dumps(e,sort_keys=True)) !=
               sorted(map(canonical_entry,body['entries']),key=lambda e:json.dumps(e,sort_keys=True))):
        raise RuntimeError('plan_save_readback_mismatch')


def run_command(arguments):
    try:
        return subprocess.run(arguments, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError('local_ffmpeg_check_failed') from None


def probe(path):
    return json.loads(run_command(['ffprobe','-v','error','-show_streams','-show_format','-count_frames',
                                   '-protocol_whitelist','file,pipe','-f','mov','-of','json',str(path)]))


def check_video(data):
    videos = [s for s in data['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')]
    if (len(videos) != 1 or int(videos[0].get('nb_read_frames',0)) != 3
            or videos[0]['codec_name'] != 'h264' or not any(s['codec_type']=='audio' for s in data['streams'])):
        raise RuntimeError('local_video_frame_codec_audio_mismatch')
    duration = float(data['format']['duration'])
    if not 0.55 <= duration <= 0.7:
        raise RuntimeError('local_video_duration_mismatch')
    return {'frames':3,'codec':'h264','duration_seconds':duration,
            'width':videos[0]['width'],'height':videos[0]['height'],'audio':True}


def acceptance(args, receipt, persist):
    owner = Client(receipt['base'],receipt['origin'])
    if owner.json('/api/health/ready').get('ready') is not True:
        raise RuntimeError('service_not_ready')
    receipt['account_id'] = owner.login(receipt['credentials'])
    persist()
    if 'project_id' not in receipt:
        project = owner.json('/api/projects','POST',receipt['project_body'],
                             headers={'Idempotency-Key':receipt['project_key']},allowed=(200,201))
        receipt.update(project_id=project['id'],zone_id=project['default_zone_id'])
        persist()
    zone = receipt['zone_id']
    plan_path = '/api/zones/'+zone+'/plan'
    if 'plan_body' not in receipt:
        xlsx, _, _ = owner.call(plan_path+'/template.xlsx?tutorial=true')
        if not xlsx.startswith(b'PK'):
            raise RuntimeError('tutorial_xlsx_missing')
        write_private(Path(receipt['tutorial_path']),xlsx)
        preview = owner.json(plan_path+'/import-preview','POST',raw=xlsx,
            headers={'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        if preview.get('errors') or not preview.get('entries'):
            raise RuntimeError('tutorial_preview_failed')
        receipt['tutorial_sha256'] = hashlib.sha256(xlsx).hexdigest()
        receipt['plan_body'] = {key:preview[key] for key in ('expected_revision','entries')}
        receipt['plan_timezone'] = preview['timezone']
        persist()
    plan = owner.json(plan_path)
    if 'plan_revision_id' not in receipt:
        if plan['revision_number'] == receipt['plan_body']['expected_revision']:
            receipt['plan_save_started'] = True
            persist()
            owner.json(plan_path,'PUT',receipt['plan_body'])
            plan = owner.json(plan_path)
        assert_plan(plan,receipt['plan_body'])
        receipt['plan_revision_id'] = plan['revision_id']
        receipt['checks']['excel_preview_save_readback'] = True
        persist()
    else:
        plan = owner.json(plan_path+'?revision='+str(receipt['plan_body']['expected_revision']+1))
        assert_plan(plan,receipt['plan_body'])
        if plan['revision_id'] != receipt['plan_revision_id']:
            raise RuntimeError('saved_plan_revision_changed')
    clip = Path(receipt['clip_path'])
    if clip.is_symlink():
        raise RuntimeError('original_clip_symlink_rejected')
    if not clip.exists():
        if receipt.get('clip_sha256') or receipt.get('video_submission_started'):
            raise RuntimeError('original_clip_missing_do_not_resubmit')
        run_command(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x96:rate=5:duration=0.6',
            '-f','lavfi','-i','sine=frequency=880:duration=0.6','-c:v','libx264','-c:a','aac','-shortest',str(clip)])
        clip.chmod(0o600)
    clip_hash = hashlib.sha256(clip.read_bytes()).hexdigest()
    if receipt.get('clip_sha256',clip_hash) != clip_hash:
        raise RuntimeError('original_clip_hash_changed_do_not_resubmit')
    receipt['clip_sha256'] = clip_hash
    receipt['checks']['source_video'] = check_video(probe(clip))
    if 'request_context' not in receipt:
        choices = owner.json('/api/analysis-choices')
        if choices.get('cloud_provider') not in ('deepseek','yandex_ai_studio'):
            raise RuntimeError('cloud_provider_missing')
        receipt['request_context'] = {'project_id':receipt['project_id'],'zone_id':zone,
            'cloud_processing_consent':'true','cloud_provider':choices['cloud_provider'],
            'capture_started_at':receipt['capture_started_at'],'plan_revision_id':receipt['plan_revision_id']}
        receipt['profile_id'] = choices['cloud_profile_id']
    persist()
    if not receipt.get('run_id'):
        receipt['video_submission_started'] = True
        receipt['submission_attempts'] = receipt.get('submission_attempts',0)+1
        persist()
        result = owner.json('/api/runs/video?'+urlencode(receipt['request_context']),'POST',raw=clip.read_bytes(),
            headers={'Content-Type':'video/mp4','Idempotency-Key':receipt['video_key']},allowed=(202,),timeout=180)
        receipt['run_id'] = result['run_id']
        persist()
    run_id = receipt['run_id']
    deadline = time.monotonic()+args.timeout
    while True:
        job = owner.json('/api/video-runs/'+run_id)
        receipt.update(job=job,last_poll_at=datetime.now(timezone.utc).isoformat())
        persist()
        if job['state'] in ('succeeded','failed'):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('video_poll_timeout_resume_same_receipt')
        time.sleep(3)
    if job['state'] != 'succeeded':
        raise RuntimeError('video_job_failed_'+str(job.get('error','unknown')))
    device = (job.get('device') or {}).get('actual_device')
    if not device or (args.expect_device and device != args.expect_device):
        raise RuntimeError('actual_device_mismatch')
    weights = (job.get('device') or {}).get('weights',[])
    if {item.get('id') for item in weights} != {'apoce','kaggle'} or any(len(item.get('sha256','')) != 64 for item in weights):
        raise RuntimeError('dual_detector_evidence_missing')
    result = job['result']
    if (result['processed_frame_count'] != 3 or len(result['selected_frames']) != 3
            or result.get('explanation_state') != 'succeeded' or not result.get('assessment')):
        raise RuntimeError('video_result_incomplete')
    if job['context'].get('plan_revision_id') != receipt['plan_revision_id']:
        raise RuntimeError('video_plan_binding_mismatch')
    if owner.json('/api/runs/'+run_id).get('media_kind') != 'video':
        raise RuntimeError('general_run_readback_failed')
    media = result['video_url']
    partial, status, headers = owner.call(media,headers={'Range':'bytes=0-31'},allowed=(206,))
    if len(partial) != 32 or not next((v for k,v in headers.items() if k.lower()=='content-range'),'').startswith('bytes 0-31/'):
        raise RuntimeError('authorized_range_failed')
    payload, _, _ = owner.call(media)
    if not payload.startswith(partial) or hashlib.sha256(payload).hexdigest() != result['sha256'] or len(payload) != result['size']:
        raise RuntimeError('video_download_integrity_failed')
    output_video = Path(receipt['result_path'])
    write_private(output_video,payload)
    receipt['checks']['result_video'] = check_video(probe(output_video))
    outsider = Client(receipt['base'],receipt['origin'])
    receipt['outsider_id'] = outsider.login(receipt['outsider_credentials'])
    persist()
    for path in ('/api/video-runs/'+run_id,'/api/runs/'+run_id,media):
        outsider.call(path,headers={'Range':'bytes=0-31'} if path==media else None,allowed=(404,))
    receipt['checks'].update(actual_device=device,processed_frame_count=3,authorized_range=True,
                             download_sha256=result['sha256'],outsider_denial=True)
    receipt['status'] = 'passed'
    receipt.pop('failure',None)
    persist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:3000')
    parser.add_argument('--origin',help='Public Origin when base addresses the service through loopback')
    parser.add_argument('--output',type=Path,required=True,help='Private resumable receipt; contains test-account credentials')
    parser.add_argument('--expect-device',choices=('cuda:0','cpu'))
    parser.add_argument('--timeout',type=float,default=900)
    args = parser.parse_args()
    path = args.output.absolute()
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink() or (path.exists() and not stat.S_ISREG(path.stat().st_mode)):
        parser.error('receipt must be a regular file')
    lock = path.with_name(path.name+'.lock')
    if lock.is_symlink():
        parser.error('receipt lock must not be a symlink')
    descriptor = os.open(lock,os.O_RDWR|os.O_CREAT,0o600)
    with os.fdopen(descriptor,'w'):
        try:
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('receipt is already in use')
        base = args.base.rstrip('/')
        parsed = urlsplit(base)
        if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            parser.error('base must be an HTTP(S) origin')
        origin = args.origin or base
        if path.exists():
            path.chmod(0o600)
            receipt = json.loads(path.read_text())
            if receipt.get('version') != 1 or receipt['base'] != base or receipt['origin'] != origin:
                parser.error('receipt identity/base/origin mismatch')
        else:
            now = datetime.now(timezone.utc).isoformat()
            suffix = uuid.uuid4().hex
            receipt = {'version':1,'base':base,'origin':origin,'created_at':now,'capture_started_at':now,
                'credentials':{'email':'video-owner-'+suffix+'@example.test','password':secrets.token_urlsafe(32),'name':'Проверка видео и Excel'},
                'outsider_credentials':{'email':'video-outsider-'+suffix+'@example.test','password':secrets.token_urlsafe(32),'name':'Проверка доступа'},
                'project_key':str(uuid.uuid4()),'video_key':str(uuid.uuid4()),
                'project_body':{'name':'CLI video acceptance '+suffix[:8],'timezone':'Europe/Moscow'},
                'clip_path':str(path.with_suffix('.source.mp4')),'tutorial_path':str(path.with_suffix('.tutorial.xlsx')),
                'result_path':str(path.with_suffix('.result.mp4')),'status':'prepared','checks':{}}
        persist = lambda:save(path,receipt)
        persist()
        try:
            acceptance(args,receipt,persist)
        except Exception as exc:
            receipt.update(status='failed',failure=str(exc),failed_at=datetime.now(timezone.utc).isoformat())
            persist()
            print('video_acceptance=failed receipt='+str(path)+' resume_with_same_output=true',file=sys.stderr)
            return 1
        print('video_acceptance=passed run_id='+receipt['run_id']+' device='+receipt['checks']['actual_device']+' receipt='+str(path))
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
