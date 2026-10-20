"""Cookie accounts and project membership authority."""
import hashlib
import os
import re
import secrets
import uuid
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.application.admin_password import hash_password, verify_password

router = APIRouter()
COOKIE = 'account_session'


def auth_required():
    return os.getenv('AUTH_REQUIRED', 'true').lower() != 'false'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def engine(request):
    return request.app.state.store.engine


def public(row):
    return {key: str(row[key]) if key == 'id' else row[key] for key in ('id', 'email', 'name', 'theme', 'verified')}


def current_user(request):
    if hasattr(request.state, 'account_user'):
        return request.state.account_user
    token = request.cookies.get(COOKIE, '')
    with engine(request).connect() as conn:
        row = conn.execute(text('''SELECT u.* FROM account_users u JOIN account_sessions s ON s.user_id=u.id
            WHERE s.token_hash=:token AND s.expires_at>clock_timestamp()'''), {'token': digest(token)}).mappings().first()
    if not row:
        raise HTTPException(401, 'authentication_required')
    request.state.account_user = public(row)
    return request.state.account_user


def require_project(request, project_id, write=False, owner=False):
    if not auth_required():
        return 'owner'
    user = current_user(request)
    with engine(request).connect() as conn:
        role = conn.execute(text('SELECT role FROM project_members WHERE project_id=:p AND user_id=:u'),
                            {'p': project_id, 'u': user['id']}).scalar()
    if not role:
        raise HTTPException(404, 'project_not_found')
    if (owner and role != 'owner') or (write and role == 'viewer'):
        raise HTTPException(403, 'insufficient_project_role')
    return role


def require_entity(request, kind, identifier, write=False):
    if not auth_required():
        return
    if kind == 'run':
        with engine(request).connect() as conn:
            row = conn.execute(text("SELECT purpose,request_context->>'project_id' AS project_id FROM analysis_runs WHERE id=:id"),
                               {'id': identifier}).mappings().first()
        if row is None:
            with engine(request).connect() as conn:
                video_project = conn.execute(text('SELECT project_id FROM video_jobs WHERE id=:id'), {'id':identifier}).scalar()
            if video_project:
                return require_project(request, video_project, write=write)
        if row and row['purpose'] == 'comparison_campaign' and not write:
            from app.application.engagement import admin_session
            admin_session(request)
            return
        if not row or row['purpose'] != 'ordinary' or not row['project_id']:
            raise HTTPException(404, 'run_not_found')
        return require_project(request, row['project_id'], write=write)
    queries = {
        'zone': 'SELECT project_id FROM site_zones WHERE id=:id',
        'signal': 'SELECT z.project_id FROM site_signals s JOIN site_zones z ON z.id=s.zone_id WHERE s.id=:id',
    }
    with engine(request).connect() as conn:
        project = conn.execute(text(queries[kind]), {'id': identifier}).scalar()
    if not project:
        raise HTTPException(404, f'{kind}_not_found')
    return require_project(request, project, write=write)


def email(value):
    if not isinstance(value, str) or len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise HTTPException(400, 'invalid_email')
    return value.strip().lower()


def password(value):
    if not isinstance(value, str) or not 9 <= len(value) <= 1024:
        raise HTTPException(400, 'invalid_password')
    try:
        return hash_password(value)
    except (ValueError, TypeError):
        raise HTTPException(400, 'invalid_password') from None


def throttle(request, operation, address=''):
    key = digest(f'{operation}:{request.client.host if request.client else "unknown"}:{address}')
    with engine(request).begin() as conn:
        attempts = conn.execute(text('''INSERT INTO account_throttles(key,attempts) VALUES (:key,1)
            ON CONFLICT(key) DO UPDATE SET attempts=CASE WHEN account_throttles.started_at < clock_timestamp()-interval '15 minutes'
            THEN 1 ELSE account_throttles.attempts+1 END,
            started_at=CASE WHEN account_throttles.started_at < clock_timestamp()-interval '15 minutes'
            THEN clock_timestamp() ELSE account_throttles.started_at END RETURNING attempts'''), {'key': key}).scalar_one()
    if attempts > 15:
        raise HTTPException(429, 'too_many_attempts')


@router.get('/account/session')
def session(request: Request):
    try:
        return {'user': current_user(request)}
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        return {'user': None}


@router.post('/account/register')
def register(request: Request, body: dict):
    address = email(body.get('email'))
    throttle(request, 'register', address)
    name = body.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
        raise HTTPException(400, 'invalid_name')
    encoded = password(body.get('password'))
    try:
        with engine(request).begin() as conn:
            identifier = uuid.uuid4()
            conn.execute(text('INSERT INTO account_users(id,email,name,password_hash,recovery_hash,verified) VALUES (:id,:e,:n,:p,:recovery,true)'),
                         {'id': identifier, 'e': address, 'n': name.strip(), 'p': encoded, 'recovery': digest(secrets.token_urlsafe(32))})
    except IntegrityError:
        raise HTTPException(409, 'email_unavailable') from None
    return {'verification_required': False}


@router.post('/account/login')
def login(request: Request, response: Response, body: dict):
    address = email(body.get('email'))
    throttle(request, 'login', address)
    with engine(request).begin() as conn:
        row = conn.execute(text('SELECT * FROM account_users WHERE email=:e FOR UPDATE'), {'e': address}).mappings().first()
        if not row or not verify_password(body.get('password'), row['password_hash']):
            raise HTTPException(401, 'invalid_credentials')
        token = secrets.token_urlsafe(32)
        conn.execute(text('INSERT INTO account_sessions VALUES (:t,:u,:e)'),
                     {'t': digest(token), 'u': row['id'], 'e': datetime.now(timezone.utc) + timedelta(hours=8)})
    response.set_cookie(COOKIE, token, httponly=True, secure=request.url.scheme == 'https' or os.getenv('PUBLIC_APP_URL', '').startswith('https://'), samesite='strict', max_age=28800, path='/')
    return {'user': public(row)}


@router.post('/account/logout')
def logout(request: Request, response: Response):
    with engine(request).begin() as conn:
        conn.execute(text('DELETE FROM account_sessions WHERE token_hash=:t'), {'t': digest(request.cookies.get(COOKIE, ''))})
    response.delete_cookie(COOKIE, path='/')
    return {'accepted': True}


@router.patch('/account/profile')
def profile(request: Request, body: dict):
    try:
        return update_profile(request, body)
    except IntegrityError:
        raise HTTPException(409, 'email_unavailable') from None


def update_profile(request, body):
    user = current_user(request)
    throttle(request, 'profile', user['id'])
    with engine(request).begin() as conn:
        row = conn.execute(text('SELECT * FROM account_users WHERE id=:u FOR UPDATE'), {'u': user['id']}).mappings().one()
        if 'email' in body or 'password' in body:
            if not verify_password(body.get('current_password'), row['password_hash']):
                raise HTTPException(403, 'invalid_current_password')
            conn.execute(text('DELETE FROM account_sessions WHERE user_id=:u AND token_hash<>:t'), {'u': user['id'], 't': digest(request.cookies.get(COOKIE, ''))})
        if 'name' in body:
            value = body['name']
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= 200:
                raise HTTPException(400, 'invalid_name')
            conn.execute(text('UPDATE account_users SET name=:n WHERE id=:u'), {'n': value.strip(), 'u': user['id']})
        if 'theme' in body:
            if body['theme'] not in ('light', 'dark', 'system'):
                raise HTTPException(400, 'invalid_theme')
            conn.execute(text('UPDATE account_users SET theme=:t WHERE id=:u'), {'t': body['theme'], 'u': user['id']})
        if 'password' in body:
            conn.execute(text('UPDATE account_users SET password_hash=:p WHERE id=:u'), {'p': password(body['password']), 'u': user['id']})
        if 'email' in body:
            address = email(body['email'])
            if conn.execute(text('SELECT 1 FROM account_users WHERE email=:e AND id<>:u'), {'e': address, 'u': user['id']}).first():
                raise HTTPException(409, 'email_unavailable')
            conn.execute(text('UPDATE account_users SET email=:e WHERE id=:u'), {'e': address, 'u': user['id']})
        updated = conn.execute(text('SELECT * FROM account_users WHERE id=:u'), {'u': user['id']}).mappings().one()
    return {'user': public(updated)}


@router.get('/projects/{project_id}/members')
def members(project_id: uuid.UUID, request: Request):
    require_project(request, project_id)
    with engine(request).connect() as conn:
        rows = conn.execute(text('''SELECT u.id AS user_id,u.name,u.email,m.role FROM project_members m
            JOIN account_users u ON u.id=m.user_id WHERE m.project_id=:p ORDER BY u.name,u.id'''), {'p': project_id}).mappings()
        return {'members': [{**row, 'user_id': str(row['user_id'])} for row in rows]}


@router.delete('/projects/{project_id}/members/{user_id}')
def remove_member(project_id: uuid.UUID, user_id: uuid.UUID, request: Request):
    require_project(request, project_id, owner=True)
    with engine(request).begin() as conn:
        conn.execute(text("DELETE FROM project_members WHERE project_id=:p AND user_id=:u AND role<>'owner'"), {'p': project_id, 'u': user_id})
    return {'accepted': True}


@router.get('/projects/{project_id}/invitations')
def invitations(project_id: uuid.UUID, request: Request):
    require_project(request, project_id, owner=True)
    with engine(request).connect() as conn:
        rows = conn.execute(text('SELECT id,email,role,expires_at,revoked FROM project_invitations WHERE project_id=:p'), {'p': project_id}).mappings()
        return {'invitations': [{**row, 'id': str(row['id']), 'expires_at': row['expires_at'].isoformat()} for row in rows]}


@router.post('/projects/{project_id}/invitations')
def invite(project_id: uuid.UUID, request: Request, body: dict):
    require_project(request, project_id, owner=True)
    role = body.get('role')
    if role not in ('editor', 'viewer'):
        raise HTTPException(400, 'invalid_role')
    address = email(body['email']) if body.get('email') else None
    token, identifier = secrets.token_urlsafe(32), uuid.uuid4()
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    with engine(request).begin() as conn:
        recipient = conn.execute(text('SELECT id FROM account_users WHERE email=:e'), {'e': address}).first() if address else None
        if address and not recipient:
            raise HTTPException(400, 'recipient_not_registered')
        conn.execute(text('INSERT INTO project_invitations(id,project_id,token_hash,email,recipient_id,role,expires_at) VALUES (:id,:p,:t,:e,:recipient,:r,:x)'),
                     {'id': identifier, 'p': project_id, 't': digest(token), 'e': address, 'recipient': recipient.id if recipient else None, 'r': role, 'x': expires})
        if recipient:
            conn.execute(text('INSERT INTO account_notifications(id,user_id,invitation_id) VALUES (:id,:u,:i)'), {'id': uuid.uuid4(), 'u': recipient.id, 'i': identifier})
    return {'id': str(identifier), 'url': f'/invite/{token}', 'token': token, 'expires_at': expires.isoformat(), 'role': role}


@router.delete('/projects/{project_id}/invitations/{invitation_id}')
def revoke(project_id: uuid.UUID, invitation_id: uuid.UUID, request: Request):
    require_project(request, project_id, owner=True)
    with engine(request).begin() as conn:
        conn.execute(text('UPDATE project_invitations SET revoked=true WHERE id=:i AND project_id=:p'), {'i': invitation_id, 'p': project_id})
    return {'accepted': True}


def invitation(conn, user, token=None, identifier=None):
    row = conn.execute(text('''SELECT i.*,p.name AS project_name FROM project_invitations i
        JOIN site_projects p ON p.id=i.project_id WHERE
        (i.token_hash=:t OR (i.id=CAST(:id AS uuid) AND i.recipient_id=:u))
        AND NOT i.revoked AND i.expires_at>clock_timestamp() FOR UPDATE OF i'''),
        {'t': digest(str(token or '')), 'id': identifier, 'u': user['id']}).mappings().first()
    if not row or row['recipient_id'] and str(row['recipient_id']) != user['id']:
        raise HTTPException(404, 'invitation_not_found')
    return row


@router.get('/invitations/{token}')
def preview(token: str, request: Request):
    user = current_user(request)
    with engine(request).begin() as conn:
        row = invitation(conn, user, token=token)
        return {'project_name': row['project_name'], 'role': row['role'], 'expires_at': row['expires_at'].isoformat()}


@router.post('/invitations/accept')
def accept(request: Request, body: dict):
    user = current_user(request)
    try:
        identifier = str(uuid.UUID(body['invitation_id'])) if body.get('invitation_id') else None
    except (ValueError, TypeError):
        raise HTTPException(400, 'invalid_invitation') from None
    with engine(request).begin() as conn:
        row = invitation(conn, user, token=body.get('token'), identifier=identifier)
        conn.execute(text('''INSERT INTO project_members VALUES (:p,:u,:r)
            ON CONFLICT(project_id,user_id) DO NOTHING'''), {'p': row['project_id'], 'u': user['id'], 'r': row['role']})
        role = conn.execute(text('SELECT role FROM project_members WHERE project_id=:p AND user_id=:u'), {'p': row['project_id'], 'u': user['id']}).scalar_one()
    return {'project_id': str(row['project_id']), 'role': role}


@router.get('/notifications')
def notifications(request: Request):
    user = current_user(request)
    with engine(request).connect() as conn:
        rows = conn.execute(text('''SELECT n.id,n.invitation_id,p.name AS project_name,i.role,n.created_at,n.read,
            (NOT i.revoked AND i.expires_at>clock_timestamp() AND i.recipient_id=:u AND NOT EXISTS
            (SELECT 1 FROM project_members m WHERE m.project_id=i.project_id AND m.user_id=:u)) AS actionable
            FROM account_notifications n JOIN project_invitations i ON i.id=n.invitation_id
            JOIN site_projects p ON p.id=i.project_id WHERE n.user_id=:u ORDER BY n.created_at DESC'''), {'u': user['id'], 'e': user['email']}).mappings()
        return {'notifications': [{**row, 'id': str(row['id']), 'invitation_id': str(row['invitation_id']), 'created_at': row['created_at'].isoformat()} for row in rows]}


@router.post('/notifications/{notification_id}/read')
def read_notification(notification_id: uuid.UUID, request: Request):
    user = current_user(request)
    with engine(request).begin() as conn:
        conn.execute(text('UPDATE account_notifications SET read=true WHERE id=:id AND user_id=:u'), {'id': notification_id, 'u': user['id']})
    return {'accepted': True}


def require_origin(request):
    configured = urlsplit(os.getenv('PUBLIC_APP_URL') or str(request.base_url))
    expected = f'{configured.scheme}://{configured.netloc}'
    if request.headers.get('origin') != expected or request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'invalid_origin')


async def authorize_request(request: Request):
    """Authorize identifiers before endpoint execution, including file and write routes."""
    if not auth_required():
        return
    path = request.url.path.removeprefix(request.scope.get('root_path', ''))
    unsafe = request.method not in ('GET', 'HEAD', 'OPTIONS')
    if unsafe:
        require_origin(request)
    if path.startswith('/health/') or path in ('/account/session', '/account/register', '/account/login', '/account/logout'):
        return
    if path.startswith('/admin/') or path in ('/feedback', '/analytics/events'):
        return
    if request.method == 'GET' and (path in ('/trial/project.zip', '/trial/photos.zip', '/trial/preview') or path.startswith('/trial/photos/')):
        return
    if path == '/assistant/messages' and request.method == 'POST':
        return
    if path in ('/stages/summary', '/readiness', '/hybrid-budget', '/hybrid-readiness', '/provider-comparison'):
        from app.application.engagement import admin_session
        admin_session(request)
        return
    parts = path.strip('/').split('/')
    write = unsafe
    if len(parts) > 1 and parts[0] == 'runs' and parts[1] not in ('single-image', 'series', 'video'):
        try:
            identifier = uuid.UUID(parts[1])
        except ValueError:
            raise HTTPException(404, 'run_not_found') from None
        require_entity(request, 'run', identifier, write=write)
        return
    current_user(request)
    try:
        if len(parts) > 1 and parts[0] in ('projects', 'zones', 'runs', 'signals') and parts[1] not in ('single-image', 'series', 'video'):
            identifier = uuid.UUID(parts[1])
            if parts[0] == 'projects':
                require_project(request, identifier, write=write)
            else:
                require_entity(request, {'zones': 'zone', 'runs': 'run', 'signals': 'signal'}[parts[0]], identifier, write=write)
        for field, kind in (('project_id', 'project'), ('zone_id', 'zone')):
            value = request.query_params.get(field)
            if value:
                identifier = uuid.UUID(value)
                require_project(request, identifier, write=write) if kind == 'project' else require_entity(request, kind, identifier, write=write)
    except (ValueError, TypeError):
        raise HTTPException(404, 'resource_not_found') from None
