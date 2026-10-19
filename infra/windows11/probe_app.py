import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
from http.cookiejar import CookieJar
import io
import json
from pathlib import Path
import re
import secrets
import sys
import time
from urllib import request, error
from urllib.parse import urljoin
import uuid

from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:3000')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live-analysis', action='store_true')
    parser.add_argument('--series', action='store_true')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--second-image', type=Path)
    parser.add_argument('--assistant', action='store_true')
    args = parser.parse_args()
    base = args.base.rstrip('/')
    opener = request.build_opener(request.HTTPCookieProcessor(CookieJar()))
    evidence = {'base': base, 'checks': {}, 'created_at': datetime.now(timezone.utc).isoformat()}

    def call(path, method='GET', body=None, headers=None, allowed=(200,)):
        data = json.dumps(body).encode() if body is not None else None
        supplied = {'Content-Type': 'application/json', 'Origin': base} | (headers or {})
        if method != 'GET':
            supplied.setdefault('Idempotency-Key', str(uuid.uuid4()))
        try:
            with opener.open(request.Request(base + path, data=data, headers=supplied, method=method), timeout=30) as response:
                payload = response.read()
                status = response.status
                media = response.headers.get('Content-Type', '')
        except error.HTTPError as exc:
            payload, status, media = exc.read(), exc.code, exc.headers.get('Content-Type', '')
        if status not in allowed:
            code = json.loads(payload).get('code') if 'application/json' in media else None
            raise RuntimeError('HTTP check failed: ' + path + ' status=' + str(status) + ' code=' + str(code))
        return json.loads(payload) if 'application/json' in media else payload

    try:
        html = call('/')
        evidence['checks']['html_sha256'] = hashlib.sha256(html).hexdigest()
        assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html.decode())
        if len(assets) < 2:
            raise RuntimeError('compiled_assets_missing')
        evidence['checks']['assets'] = [{'path': p, 'bytes': len(call(p))} for p in assets]
        if call('/projects') != html:
            raise RuntimeError('SPA route mismatch')
        ready = call('/api/health/ready')
        if ready.get('ready') is not True:
            raise RuntimeError('backend_not_ready')
        call('/api/projects', allowed=(401,))
        user = {'email': 'deployment-' + uuid.uuid4().hex + '@example.test',
                'password': secrets.token_urlsafe(24), 'name': 'Проверка развёртывания'}
        call('/api/account/register', 'POST', user)
        signed_in = call('/api/account/login', 'POST', user)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        private_credentials = args.output.with_suffix('.credentials.json')
        private_credentials.write_text(json.dumps(user))
        private_credentials.chmod(0o600)
        evidence['checks']['account_login'] = signed_in['user']['id']
        if call('/api/account/session')['user']['id'] != signed_in['user']['id']:
            raise RuntimeError('account_session_not_bound')
        choices = call('/api/analysis-choices')
        if choices.get('cloud_provider') != 'deepseek':
            raise RuntimeError('wrong_cloud_provider')
        evidence['checks']['ready'] = ready
        evidence['checks']['profile_id'] = choices['cloud_profile_id']
        call('/api/admin/session', allowed=(401,))
        credentials = json.loads(Path('/mnt/c/ProgramData/LztEvidence/secrets/admin-login.json').read_text())
        login = call('/api/admin/login', 'POST', credentials)
        session = call('/api/admin/session')
        if session['csrf'] != login['csrf']:
            raise RuntimeError('admin_session_not_bound')
        call('/api/admin/overview')
        evidence['checks']['admin_session'] = 'passed'
        for private in ('/runtime.json', '/secrets/deepseek_api_key', '/backend/app/config.py'):
            if call(private) != html:
                raise RuntimeError('unexpected_private_path_response')
        evidence['checks']['private_paths'] = 'SPA only; no private files served'
        key = str(uuid.uuid4())
        project_body = {'name': 'Windows verification ' + key[:8], 'timezone': 'Europe/Moscow'}
        project = call('/api/projects', 'POST', project_body, {'Idempotency-Key': key}, allowed=(200, 201))
        again = call('/api/projects', 'POST', project_body, {'Idempotency-Key': key}, allowed=(200, 201))
        if again['id'] != project['id']:
            raise RuntimeError('project_idempotency_failed')
        evidence['project_id'] = project['id']
        zone = project['default_zone_id']
        evidence['zone_id'] = zone
        if project['id'] not in [p['id'] for p in call('/api/projects')['projects']]:
            raise RuntimeError('created_project_not_listed')
        call('/api/projects/' + project['id'] + '/zones')
        catalog = call('/api/catalog/works')
        if not catalog['works']:
            raise RuntimeError('work_catalog_missing')
        now = datetime.now(timezone.utc)
        entries = [{'catalog_work_id': catalog['works'][0]['id'],
                    'start_at': (now - timedelta(hours=1)).isoformat(),
                    'end_at': (now + timedelta(hours=1)).isoformat(), 'state': 'active',
                    'stage_key': 'excavation', 'expected_equipment': ['excavator'],
                    'allowed_equipment': ['dump_truck'], 'excluded_equipment': []}]
        call('/api/zones/' + zone + '/plan', 'PUT', {'expected_revision': 0, 'entries': entries})
        plan = call('/api/zones/' + zone + '/plan')
        evidence['checks']['plan_revision'] = plan['revision_id']
        evidence['checks']['catalog_count'] = len(catalog['works'])
        image = io.BytesIO()
        Image.new('RGB', (64, 48), (220, 220, 220)).save(image, format='JPEG')
        payload = args.image.read_bytes() if args.image else image.getvalue()
        call('/api/projects/' + project['id'] + '/cover', 'PUT', {'data': base64.b64encode(payload).decode()})
        project_after_cover = next(p for p in call('/api/projects')['projects'] if p['id'] == project['id'])
        cover = call('/api/projects/' + project['id'] + '/cover')
        if hashlib.sha256(cover).hexdigest() != project_after_cover['cover_sha256']:
            raise RuntimeError('cover_integrity_failed')
        evidence['checks']['project_cover'] = 'saved'
        trial_key = str(uuid.uuid4())
        trial_project = call('/api/projects', 'POST', {'name':'Учебный пример · проверка деплоя','timezone':'Europe/Moscow'}, allowed=(201,))
        trial_path = '/api/projects/' + trial_project['id'] + '/trial'
        trial = call(trial_path, 'POST', headers={'Idempotency-Key':trial_key})
        if call(trial_path, 'POST', headers={'Idempotency-Key':trial_key}) != trial:
            raise RuntimeError('trial_seed_replay_changed')
        example = call(trial_path)
        if not example['illustrative'] or not example['examples']:
            raise RuntimeError('trial_materials_missing')
        for item in example['examples']:
            for url in item['photos']:
                if not call('/api' + url):
                    raise RuntimeError('private_trial_photo_missing')
        call('/api/trial/project.zip'); call('/api/trial/photos.zip')
        evidence['checks']['trial_seed_and_photos'] = 'passed'
        owner_opener = opener
        viewer_email = 'deployment-viewer-' + uuid.uuid4().hex + '@example.test'
        try:
            opener = request.build_opener(request.HTTPCookieProcessor(CookieJar()))
            viewer = {'email':viewer_email,'password':secrets.token_urlsafe(24),'name':'Проверка приглашения'}
            call('/api/account/register','POST',viewer); call('/api/account/login','POST',viewer)
            viewer_opener = opener
            call('/api/projects/' + project['id'] + '/zones', allowed=(404,))
            opener = owner_opener
            invitation = call('/api/projects/' + project['id'] + '/invitations','POST',{'email':viewer_email,'role':'viewer'},allowed=(200,201))
            opener = viewer_opener
            notifications = call('/api/notifications')['notifications']
            notification = next(item for item in notifications if item['invitation_id'] == invitation['id'])
            accepted = call('/api/invitations/accept','POST',{'invitation_id':notification['invitation_id']})
            if accepted['project_id'] != project['id']:
                raise RuntimeError('invitation_target_changed')
            call('/api/notifications/' + notification['id'] + '/read','POST')
            call('/api/projects/' + project['id'] + '/zones')
            call('/api/zones/' + zone + '/plan','PUT',{'expected_revision':1,'entries':[]},allowed=(403,))
        finally:
            opener = owner_opener
        evidence['checks']['invitations_notifications_readonly'] = 'passed'
        if args.assistant:
            reply = call('/api/assistant/messages','POST',{'message':'Что такое план работ и как его заполнить?', 'project_id':project['id'],'tutorial_context':{'version':1,'step':'plan'}})
            message = reply['messages'][-1]['content']
            if not message.strip() or 'модель сейчас недоступна' in message.lower():
                raise RuntimeError('assistant_model_unavailable')
            evidence['checks']['assistant_live_reply'] = {'characters':len(message),'history_count':len(call('/api/assistant/messages?project_id='+project['id'])['messages'])}
        if args.live_analysis:
            body = {'cloud_processing_consent': True, 'cloud_provider': 'deepseek',
                    'intent': 'observation_only', 'stage': 'excavation',
                    'scenario': 'Synthetic image used only to verify deployment and transport',
                    'observation_area': 'Synthetic test zone', 'period': now.isoformat(),
                    'project_id': project['id'], 'zone_id': zone,
                    'capture_times': [now.isoformat()], 'requested_classes': ['excavator', 'dump_truck'],
                    'image_base64': base64.b64encode(payload).decode()}
            if args.series:
                second = io.BytesIO()
                Image.new('RGB', (64, 48), (180, 180, 180)).save(second, format='PNG')
                second_payload = args.second_image.read_bytes() if args.second_image else second.getvalue()
                body['images_base64'] = [body.pop('image_base64'), base64.b64encode(second_payload).decode()]
                body['capture_times'].append((now + timedelta(seconds=1)).isoformat())
                body['plan_revision_id'] = plan['revision_id']
            submit_key = str(uuid.uuid4())
            endpoint = '/api/runs/series' if args.series else '/api/runs/single-image'
            evidence['submission_key'] = submit_key
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
            accepted = call(endpoint, 'POST', body, {'Idempotency-Key': submit_key}, allowed=(202,))
            run_id = accepted['run_id']
            evidence['run_id'] = run_id
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
            deadline = time.monotonic() + 330
            while time.monotonic() < deadline:
                run = call('/api/runs/' + run_id)
                if run['state'] in ('succeeded', 'failed'):
                    break
                time.sleep(2)
            else:
                raise RuntimeError('analysis_outcome_still_unknown; do not replay')
            evidence['checks']['analysis_state'] = run['state']
            evidence['checks']['analysis_error'] = run.get('error_code')
            evidence['checks']['calls'] = [{'kind': c['kind'], 'state': c['state'],
                'model': (c.get('result') or {}).get('model'), 'usage': (c.get('result') or {}).get('usage'),
                'rejection': (c.get('result') or {}).get('rejection')} for c in run.get('ai_evidence', [])]
            if run['state'] != 'succeeded':
                raise RuntimeError('analysis_failed: ' + str(run.get('error_code')))
            if len(run['ai_evidence']) != (3 if args.series else 2):
                raise RuntimeError('unexpected_provider_call_count')
            for c in run['ai_evidence']:
                if c['result']['valid'] is not True or c['result']['model'] != 'deepseek-flash':
                    raise RuntimeError('provider_receipt_not_valid')
            evidence['checks']['source'] = run['result_projection']['source']
            models = run['result_projection']['hybrid_frames'][0]['detectors']['models']
            evidence['checks']['detectors'] = [{'id':m['model_id'],'weights_sha256':m['weights_sha256'],'detections':len(m['detections'])} for m in models]
            if {m['model_id'] for m in models} != {'apoce','kaggle'}:
                raise RuntimeError('expected_detectors_missing')
            if args.image and any(not m['detections'] for m in models):
                raise RuntimeError('real_sample_detector_found_no_objects')
            repeat = call(endpoint, 'POST', body, {'Idempotency-Key': submit_key}, allowed=(202,))
            if repeat['run_id'] != run_id:
                raise RuntimeError('analysis_idempotency_failed')
            frame = run['inputs'][0]
            original = call('/api/runs/' + run_id + '/artifacts/' + frame['artifact_id'])
            if hashlib.sha256(original).hexdigest() != hashlib.sha256(payload).hexdigest():
                raise RuntimeError('saved_source_image_changed')
            evidence['checks']['analysis_idempotency'] = 'passed'
            evidence['checks']['image_integrity'] = 'passed'
        evidence['status'] = 'passed'
    except Exception as exc:
        evidence['status'] = 'failed'
        evidence['failure'] = str(exc)
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        print(json.dumps(evidence, ensure_ascii=False))


if __name__ == '__main__':
    main()
