"""Public feedback and anonymous activity; a separate authenticated owner surface."""
import asyncio
import base64
import hashlib
import hmac
import io
import ipaddress
import json
import secrets
import time
import warnings
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy import text

from app.application.activity import touch_browser
from app.application.admin_password import hash_password, verify_password

router = APIRouter()
COOKIE = 'owner_session'
CATEGORIES = {'problem', 'idea', 'praise', 'other'}


def engine(request):
    return request.app.state.store.engine


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def identifier(value):
    try:
        return UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, 'invalid_identifier') from None


def limit(request, scope, maximum, seconds=60):
    identity = digest(request.client.host if request.client else 'unknown')
    bucket = int(time.time()) // seconds
    with engine(request).begin() as connection:
        count = connection.execute(text('''INSERT INTO request_limits(scope,identity,bucket,count)
            VALUES (:scope,:identity,:bucket,1) ON CONFLICT(scope,identity,bucket)
            DO UPDATE SET count=request_limits.count+1 RETURNING count'''),
            {'scope': scope, 'identity': identity, 'bucket': bucket}).scalar_one()
        connection.execute(text('DELETE FROM request_limits WHERE bucket < :old AND scope=:scope'),
                           {'old': bucket - 2, 'scope': scope})
    if count > maximum:
        raise HTTPException(429, 'too_many_requests', headers={'Retry-After': str(seconds)})


async def body(request, maximum):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > maximum:
            raise HTTPException(413, 'request_too_large')
        data.extend(chunk)
    try:
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError()
        return value, digest(data)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, 'invalid_request') from None


def require_transport(request):
    if request.url.scheme == 'https':
        return
    try:
        local_peer = ipaddress.ip_address(request.client.host).is_loopback
    except (ValueError, AttributeError):
        local_peer = False
    if not local_peer or request.url.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise HTTPException(403, 'https_required')


def require_origin(request):
    origin = request.headers.get('origin')
    expected = f'{request.url.scheme}://{request.headers.get("host", "")}'
    if origin != expected or request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'invalid_origin')


def admin_session(request: Request):
    require_transport(request)
    token = request.cookies.get(COOKIE, '')
    with engine(request).connect() as connection:
        session = connection.execute(text('''SELECT token_hash,csrf FROM admin_sessions
            WHERE token_hash=:token AND expires_at > clock_timestamp()'''), {'token': digest(token)}).mappings().first()
    if session is None:
        raise HTTPException(401, 'authentication_required')
    if request.method not in ('GET', 'HEAD'):
        require_origin(request)
        if not hmac.compare_digest(request.headers.get('x-csrf-token', '').encode(), session['csrf'].encode()):
            raise HTTPException(403, 'invalid_csrf')
    return dict(session)


@router.post('/admin/login')
async def login(request: Request):
    require_transport(request)
    require_origin(request)
    await asyncio.to_thread(limit, request, 'login', 10, 900)
    value, _ = await body(request, 8192)
    return await asyncio.to_thread(_login, request, value)


def _login(request, value):
    with engine(request).begin() as connection:
        stored = connection.execute(text("SELECT password_hash FROM admin_credentials WHERE login='gorshenin-nik' FOR UPDATE")).scalar_one_or_none()
        if stored is None:
            raise HTTPException(503, 'admin_not_configured')
        password = value.get('password')
        if value.get('login') != 'gorshenin-nik' or not isinstance(password, str) or not verify_password(password, stored):
            raise HTTPException(401, 'invalid_credentials')
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        connection.execute(text('DELETE FROM admin_sessions WHERE expires_at <= clock_timestamp()'))
        connection.execute(text('''INSERT INTO admin_sessions(token_hash,csrf,expires_at)
            VALUES (:token,:csrf,clock_timestamp()+interval '8 hours')'''), {'token': digest(token), 'csrf': csrf})
    response = JSONResponse({'csrf': csrf}, headers={'Cache-Control': 'no-store'})
    response.set_cookie(COOKIE, token, max_age=8 * 3600, httponly=True, secure=request.url.scheme == 'https', samesite='strict', path='/')
    return response


@router.get('/admin/session')
def session_info(session=Depends(admin_session)):
    return JSONResponse({'csrf': session['csrf']}, headers={'Cache-Control': 'no-store'})


@router.post('/admin/logout')
def logout(request: Request, session=Depends(admin_session)):
    with engine(request).begin() as connection:
        connection.execute(text('DELETE FROM admin_sessions WHERE token_hash=:token'), {'token': session['token_hash']})
    response = JSONResponse({'ok': True}, headers={'Cache-Control': 'no-store'})
    response.delete_cookie(COOKIE, path='/')
    return response


@router.post('/admin/password')
async def change_password(request: Request, session=Depends(admin_session)):
    await asyncio.to_thread(limit, request, 'password', 10, 900)
    value, _ = await body(request, 8192)
    return await asyncio.to_thread(_change_password, request, value)


def _change_password(request, value):
    with engine(request).begin() as connection:
        stored = connection.execute(text("SELECT password_hash FROM admin_credentials WHERE login='gorshenin-nik' FOR UPDATE")).scalar_one_or_none()
        if not verify_password(value.get('current_password'), stored):
            raise HTTPException(401, 'invalid_credentials')
        try:
            encoded = hash_password(value.get('new_password'))
        except ValueError:
            raise HTTPException(400, 'password_length') from None
        connection.execute(text("UPDATE admin_credentials SET password_hash=:hash WHERE login='gorshenin-nik'"), {'hash': encoded})
        connection.execute(text('DELETE FROM admin_sessions'))
    response = JSONResponse({'ok': True}, headers={'Cache-Control': 'no-store'})
    response.delete_cookie(COOKIE, path='/')
    return response


def validate_feedback(value):
    category, message = value.get('category'), value.get('message')
    if not isinstance(category, str) or category not in CATEGORIES or not isinstance(message, str) or not message.strip() or len(message) > 5000:
        raise HTTPException(400, 'invalid_feedback')
    context = value.get('context', {})
    if not isinstance(context, dict) or set(context) - {'pathname','project_id','analysis_id'}:
        raise HTTPException(400, 'invalid_context')
    path = context.get('pathname', '')
    if not isinstance(path, str) or len(path) > 1000 or (path and (not path.startswith('/') or '?' in path or '#' in path)):
        raise HTTPException(400, 'invalid_context')
    for key in ('project_id', 'analysis_id'):
        if key in context:
            if not isinstance(context[key], str):
                raise HTTPException(400, "invalid_context")
            identifier(context[key])
    attachments = value.get('attachments', [])
    if not isinstance(attachments, list) or len(attachments) > 5:
        raise HTTPException(400, 'invalid_attachments')
    images, total = [], 0
    for item in attachments:
        try:
            payload = base64.b64decode(item['data'], validate=True)
            if not 0 < len(payload) <= 5_000_000:
                raise ValueError()
            total += len(payload)
            if total > 15_000_000:
                raise ValueError()
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(payload)) as image:
                    media = {'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}[image.format]
                    if image.width * image.height > 40_000_000:
                        raise ValueError()
                    image.verify()
                with Image.open(io.BytesIO(payload)) as image:
                    image.load()
            images.append((payload, media))
        except (ValueError, TypeError, KeyError, OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(400, 'invalid_attachment') from None
    return category, message.strip(), context, images


@router.post('/feedback')
async def submit_feedback(request: Request):
    await asyncio.to_thread(limit, request, 'feedback', 20, 3600)
    key = identifier(request.headers.get('idempotency-key'))
    value, body_hash = await body(request, 20_100_000)
    return await asyncio.to_thread(_submit_feedback, request, key, value, body_hash)


def _submit_feedback(request, key, value, body_hash):
    category, message, context, images = validate_feedback(value)
    feedback_id = uuid5(NAMESPACE_URL, f'feedback/{key}')
    with engine(request).begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(:lock)'), {'lock': key.int % (2**63)})
        existing = connection.execute(text('SELECT id,body_sha256 FROM feedback WHERE request_key=:key'), {'key': key}).first()
        if existing:
            if existing.body_sha256 != body_hash:
                raise HTTPException(409, 'idempotency_key_conflict')
            return {'id': str(existing.id), 'message': 'Спасибо, отзыв сохранён'}
        stored = []
        try:
            artifacts = request.app.state.artifacts
            for index, (payload, media) in enumerate(images):
                attachment_id = uuid5(feedback_id, str(index))
                key_name = f'feedback/{feedback_id}/{attachment_id}/{digest(payload)}'
                artifacts.client.put_object(Bucket=artifacts.bucket, Key=key_name, Body=payload, ContentType=media)
                artifacts._verify(key_name, digest(payload), len(payload))
                stored.append({'id': attachment_id, 'feedback': feedback_id, 'key': key_name,
                               'hash': digest(payload), 'size': len(payload), 'media': media})
        except Exception:
            raise HTTPException(503, 'feedback_storage_unavailable') from None
        connection.execute(text('''INSERT INTO feedback(id,request_key,body_sha256,category,message,context)
            VALUES (:id,:key,:hash,:category,:message,CAST(:context AS jsonb))'''),
            {'id': feedback_id, 'key': key, 'hash': body_hash, 'category': category, 'message': message, 'context': json.dumps(context)})
        for item in stored:
            connection.execute(text('''INSERT INTO feedback_attachments(id,feedback_id,object_key,sha256,size,media_type)
                VALUES (:id,:feedback,:key,:hash,:size,:media)'''), item)
    return {'id': str(feedback_id), 'message': 'Спасибо, отзыв сохранён'}


@router.get('/admin/feedback')
def feedback_list(request: Request, category: str | None = None, offset: int = 0, session=Depends(admin_session)):
    if category is not None and category not in CATEGORIES or offset < 0:
        raise HTTPException(400, 'invalid_filter')
    with engine(request).connect() as connection:
        rows = connection.execute(text('''SELECT id,category,left(message,180) AS message,created_at,read_at
            FROM feedback WHERE (CAST(:category AS text) IS NULL OR category=:category)
            ORDER BY created_at DESC,id DESC LIMIT 50 OFFSET :offset'''), {'category': category, 'offset': offset}).mappings().all()
    return {'feedback': [dict(row) for row in rows], 'next_offset': offset + 50 if len(rows) == 50 else None}


@router.post('/admin/feedback/{feedback_id}/open')
def feedback_detail(feedback_id: UUID, request: Request, session=Depends(admin_session)):
    with engine(request).begin() as connection:
        row = connection.execute(text('''UPDATE feedback SET read_at=coalesce(read_at,clock_timestamp())
            WHERE id=:id RETURNING id,category,message,context,created_at,read_at'''), {'id': feedback_id}).mappings().first()
        if row is None:
            raise HTTPException(404, 'feedback_not_found')
        images = connection.execute(text('SELECT id,media_type FROM feedback_attachments WHERE feedback_id=:id ORDER BY id'), {'id': feedback_id}).mappings().all()
    return {**dict(row), 'attachments': [dict(image) for image in images]}


@router.get('/admin/attachments/{attachment_id}')
def feedback_attachment(attachment_id: UUID, request: Request, session=Depends(admin_session)):
    with engine(request).connect() as connection:
        row = connection.execute(text('SELECT * FROM feedback_attachments WHERE id=:id'), {'id': attachment_id}).mappings().first()
    if row is None:
        raise HTTPException(404, 'attachment_not_found')
    artifacts = request.app.state.artifacts
    expected = f'feedback/{row["feedback_id"]}/{row["id"]}/{row["sha256"]}'
    if row['object_key'] != expected:
        raise HTTPException(503, 'attachment_unavailable')
    try:
        payload = artifacts.client.get_object(Bucket=artifacts.bucket, Key=expected)['Body'].read(row['size'] + 1)
        if len(payload) != row['size'] or digest(payload) != row['sha256']:
            raise ValueError()
    except Exception:
        raise HTTPException(503, 'attachment_unavailable') from None
    return Response(payload, media_type=row['media_type'], headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


@router.post('/analytics/events')
async def analytics_event(request: Request):
    await asyncio.to_thread(limit, request, 'analytics', 240)
    value, _ = await body(request, 2048)
    return await asyncio.to_thread(_analytics_event, request, value)


def _analytics_event(request, value):
    browser, event = identifier(value.get('browser_id')), identifier(value.get('event_id'))
    kind = value.get('kind')
    if not isinstance(kind, str) or kind not in ('visit','wizard_started','wizard_completed','wizard_skipped'):
        raise HTTPException(400, 'invalid_event')
    with engine(request).begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(:lock)'), {'lock': browser.int % (2**63)})
        if connection.execute(text('SELECT 1 FROM anonymous_events WHERE id=:id'), {'id': event}).first():
            return {'ok': True}
        now = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
        session = touch_browser(connection, browser, now)
        connection.execute(text('''INSERT INTO anonymous_events(id,browser_id,session_id,kind)
            VALUES (:id,:browser,:session,:kind) ON CONFLICT(id) DO NOTHING'''), {'id': event, 'browser': browser, 'session': session, 'kind': kind})
    return {'ok': True}


@router.get('/admin/overview')
def overview(request: Request, period: str = '30', session=Depends(admin_session)):
    if period not in ('7','30','all'):
        raise HTTPException(400, 'invalid_period')
    now = datetime.now(ZoneInfo('Europe/Moscow'))
    start = None if period == 'all' else now.replace(hour=0,minute=0,second=0,microsecond=0) - timedelta(days=int(period)-1)
    params = {'start': start}
    bound = '(CAST(:start AS timestamptz) IS NULL OR created_at >= :start)'
    with engine(request).connect() as connection:
        runs = connection.execute(text(f'''SELECT count(*) AS launched,
            count(*) FILTER (WHERE state='succeeded') AS succeeded,
            count(*) FILTER (WHERE state='failed') AS failed,
            count(*) FILTER (WHERE created_at IS NULL) AS unknown_dates
            FROM analysis_runs WHERE purpose='ordinary' AND {bound}'''), params).mappings().one()
        projects = connection.execute(text(f'SELECT count(*) FROM site_projects WHERE {bound}'), params).scalar_one()
        feedback = connection.execute(text(f'''SELECT count(*) AS feedback,count(*) FILTER(WHERE read_at IS NULL) AS unread
            FROM feedback WHERE {bound}'''), params).mappings().one()
        visits = connection.execute(text('''SELECT count(*) AS visits,count(DISTINCT browser_id) AS visitors FROM anonymous_sessions
            WHERE CAST(:start AS timestamptz) IS NULL OR started_at>=:start'''), params).mappings().one()
        daily = connection.execute(text('''SELECT day::text,sum(visits)::int AS visits,sum(analyses)::int AS analyses FROM (
            SELECT (started_at AT TIME ZONE 'Europe/Moscow')::date AS day,count(*) AS visits,0 AS analyses
            FROM anonymous_sessions WHERE CAST(:start AS timestamptz) IS NULL OR started_at>=:start GROUP BY day
            UNION ALL SELECT (created_at AT TIME ZONE 'Europe/Moscow')::date AS day,0,count(*) FROM analysis_runs
            WHERE purpose='ordinary' AND created_at IS NOT NULL AND (CAST(:start AS timestamptz) IS NULL OR created_at>=:start) GROUP BY day
            ) activity GROUP BY day ORDER BY day'''), params).mappings().all()
        all_projects = connection.execute(text('''SELECT p.id,p.name,count(r.id) AS runs,
            greatest(p.created_at,max(r.created_at),
                (SELECT max(v.created_at) FROM zone_plan_revisions v JOIN site_zones z ON z.id=v.zone_id WHERE z.project_id=p.id),
                (SELECT max(c.created_at) FROM stage_confirmations c JOIN analysis_runs cr ON cr.id=c.run_id
                 WHERE cr.request_context->>'project_id'=p.id::text AND cr.purpose='ordinary'),
                (SELECT max(greatest(s.created_at,s.updated_at)) FROM site_signals s JOIN site_zones z ON z.id=s.zone_id WHERE z.project_id=p.id)) AS latest_activity FROM site_projects p
            LEFT JOIN analysis_runs r ON r.request_context->>'project_id'=p.id::text AND r.purpose='ordinary'
            GROUP BY p.id ORDER BY latest_activity DESC,p.id''')).mappings().all()
        funnel = connection.execute(text('''SELECT count(*) AS visited,
            count(*) FILTER(WHERE EXISTS(SELECT 1 FROM activity_attribution a JOIN site_projects p ON p.id=a.object_id
                WHERE a.browser_id=b.id AND a.kind='project' AND p.created_at>=b.first_at)) AS created_project,
            count(*) FILTER(WHERE EXISTS(SELECT 1 FROM activity_attribution a JOIN analysis_runs r ON r.id=a.object_id
                WHERE a.browser_id=b.id AND a.kind='run' AND r.purpose='ordinary' AND r.state='succeeded'
                AND EXISTS(SELECT 1 FROM activity_attribution ap JOIN site_projects p ON p.id=ap.object_id
                    WHERE ap.browser_id=b.id AND ap.kind='project' AND p.created_at>=b.first_at AND p.created_at<=r.created_at))) AS succeeded
            FROM anonymous_browsers b WHERE CAST(:start AS timestamptz) IS NULL OR b.first_at>=:start'''), params).mappings().one()
        wizard = connection.execute(text(f'''SELECT kind,count(*) AS count FROM anonymous_events WHERE kind<>'visit' AND {bound} GROUP BY kind'''), params).mappings().all()
        began = connection.execute(text('SELECT started_at FROM analytics_collection')).scalar_one()
    return {'period':period,'collection_started_at':began,'cards':{**dict(visits),'projects':projects,**dict(runs),**dict(feedback)},
            'daily':[dict(row) for row in daily],'projects':[dict(row) for row in all_projects],
            'funnel':dict(funnel),'wizard':{row['kind']:row['count'] for row in wizard}}
