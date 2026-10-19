"""Curated examples, validated archives, and isolated owned trial projects."""
import hashlib
import io
import json
import stat
import warnings
from datetime import datetime
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from PIL import Image
from sqlalchemy import text

from app.application.accounts import current_user, require_project, require_origin

router = APIRouter()
FIXTURE = Path(__file__).resolve().parents[3] / 'shared/trial-project'
MAX_ARCHIVE = 20_000_000
MAX_EXPANDED = 30_000_000


def archive_bytes(photos_only=False):
    output = io.BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for path in sorted(FIXTURE.rglob('*')):
            if path.is_file() and (path.suffix == '.jpg' or path.name == 'manifest.json' and not photos_only):
                info = ZipInfo(str(path.relative_to(FIXTURE)), (2026, 10, 19, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    return output.getvalue()


def _string(value, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError()


def _annotations(annotations):
    if not isinstance(annotations,list) or not 1 <= len(annotations) <= 100:
        raise ValueError()
    for annotation in annotations:
        if not isinstance(annotation,dict) or set(annotation) != {'label','box'}:
            raise ValueError()
        _string(annotation['label'])
        box = annotation['box']
        if not isinstance(box,list) or len(box) != 4 or any(type(n) not in (int,float) or not 0 <= n <= 1 for n in box) or not box[0] < box[2] or not box[1] < box[3]:
            raise ValueError()


def validate_archive(data):
    try:
        if not data or len(data) > MAX_ARCHIVE:
            raise ValueError()
        with ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) > 50 or len(names) != len(set(names)) or 'manifest.json' not in names:
                raise ValueError()
            if sum(info.file_size for info in infos) > MAX_EXPANDED:
                raise ValueError()
            for info in infos:
                path = PurePosixPath(info.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in info.filename
                        or str(path) != info.filename or info.is_dir()
                        or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1
                        or info.file_size > 10_000_000):
                    raise ValueError()
            raw = archive.read('manifest.json')
            if len(raw) > 100_000:
                raise ValueError()
            manifest = json.loads(raw)
            if set(manifest) != {'schema_version','name','description','plan','examples','files'} or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1:
                raise ValueError()
            _string(manifest['name'], 180)
            _string(manifest['description'])
            files = manifest['files']
            if not isinstance(files, dict) or not 1 <= len(files) <= 20 or set(names) != {'manifest.json', *files}:
                raise ValueError()
            photos = {}
            for name, expected in files.items():
                if not name.startswith('photos/') or PurePosixPath(name).suffix.lower() != '.jpg':
                    raise ValueError()
                payload = archive.read(name)
                if hashlib.sha256(payload).hexdigest() != expected:
                    raise ValueError()
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(payload)) as image:
                        if image.format != 'JPEG' or image.width * image.height > 25_000_000:
                            raise ValueError()
                        image.verify()
                photos[name] = payload
            examples = manifest['examples']
            if not isinstance(examples, list) or not 1 <= len(examples) <= 20:
                raise ValueError()
            referenced = set()
            for item in examples:
                if not isinstance(item, dict) or set(item) != {'title','found','expected','check','outcome','photos','annotations','signals','corrections'}:
                    raise ValueError()
                for key in ('title','found','expected','check','outcome'):
                    _string(item[key])
                if not isinstance(item['photos'], list) or not item['photos'] or any(name not in photos for name in item['photos']):
                    raise ValueError()
                referenced.update(item['photos'])
                if not isinstance(item['annotations'], list) or len(item['annotations']) > 100 or not isinstance(item['signals'], list) or len(item['signals']) > 20:
                    raise ValueError()
                _annotations(item['annotations'])
                corrections = item['corrections']
                if not isinstance(corrections,list) or not 1 <= len(corrections) <= 20:
                    raise ValueError()
                for correction in corrections:
                    if not isinstance(correction,dict) or set(correction) != {'photo','original_annotations','corrected_annotations','comment'} or correction['photo'] not in item['photos']:
                        raise ValueError()
                    _string(correction['comment'])
                    _annotations(correction['original_annotations'])
                    _annotations(correction['corrected_annotations'])
                    if correction['original_annotations'] == correction['corrected_annotations']:
                        raise ValueError()
                for signal in item['signals']:
                    if set(signal) != {'kind','state','comment'} or signal['state'] not in ('new','in_progress','closed'):
                        raise ValueError()
                    _string(signal['kind'], 100)
                    _string(signal['comment'])
            if referenced != set(photos) or not isinstance(manifest['plan'], list) or not 1 <= len(manifest['plan']) <= 20:
                raise ValueError()
            for entry in manifest['plan']:
                if set(entry) != {'title','starts_at','ends_at','state','expected_equipment'} or entry['state'] not in ('planned','active','completed'):
                    raise ValueError()
                _string(entry['title'])
                start, end = (datetime.fromisoformat(entry[key]) for key in ('starts_at','ends_at'))
                if start.tzinfo is None or end.tzinfo is None or start > end or not isinstance(entry['expected_equipment'], list) or len(entry['expected_equipment']) > 20:
                    raise ValueError()
                for equipment in entry['expected_equipment']:
                    _string(equipment,100)
            return manifest, photos
    except (RecursionError, BadZipFile, ValueError, TypeError, KeyError, OSError, RuntimeError, NotImplementedError, OverflowError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, 'invalid_trial_archive') from None


def preview(manifest, photos):
    return {'name': manifest['name'], 'description': manifest['description'], 'illustrative': True,
            'plan': manifest['plan'], 'examples': [{**item, 'illustrative': True,
            'photos': [photos[name] for name in item['photos']],
            'corrections':[{**correction,'photo':photos[correction['photo']],'illustrative':True}
                           for correction in item.get('corrections',[])]} for item in manifest['examples']]}


@router.get('/trial/project.zip')
def download_project():
    return Response(archive_bytes(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="trial-project.zip"'})


@router.get('/trial/photos.zip')
def download_photos():
    return Response(archive_bytes(True), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="trial-photos.zip"'})


@router.get('/trial/preview')
def trial_preview():
    manifest, photos = validate_archive(archive_bytes())
    return preview(manifest, {name: '/trial/photos/' + PurePosixPath(name).name for name in photos})


@router.get('/trial/photos/{filename}')
def public_photo(filename: str):
    manifest = json.loads((FIXTURE / 'manifest.json').read_text())
    name = 'photos/' + filename
    if name not in manifest['files']:
        raise HTTPException(404, 'photo_not_found')
    return Response((FIXTURE / name).read_bytes(), media_type='image/jpeg')


@router.get('/projects/{project_id}/trial')
def imported_preview(project_id: UUID, request: Request):
    require_project(request, project_id)
    with request.app.state.store.engine.connect() as connection:
        manifest = connection.execute(text('SELECT manifest FROM trial_imports WHERE project_id=:id'), {'id': project_id}).scalar_one_or_none()
        if manifest is None:
            raise HTTPException(404, 'trial_not_found')
        rows = connection.execute(text('SELECT id,filename FROM trial_photos WHERE project_id=:id'), {'id': project_id}).all()
    return preview(manifest, {row.filename: f'/projects/{project_id}/trial/photos/{row.id}' for row in rows})


@router.get('/projects/{project_id}/trial/photos/{photo_id}')
def imported_photo(project_id: UUID, photo_id: UUID, request: Request):
    require_project(request, project_id)
    with request.app.state.store.engine.connect() as connection:
        payload = connection.execute(text('SELECT data FROM trial_photos WHERE project_id=:project AND id=:id'), {'project': project_id, 'id': photo_id}).scalar_one_or_none()
    if payload is None:
        raise HTTPException(404, 'photo_not_found')
    return Response(bytes(payload), media_type='image/jpeg', headers={'Cache-Control':'private, no-store'})


@router.post('/trial/import')
async def import_trial(request: Request):
    user = current_user(request)
    require_origin(request)
    try:
        key = UUID(request.headers.get('idempotency-key', ''))
    except ValueError:
        raise HTTPException(400, 'invalid_idempotency_key') from None
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_ARCHIVE:
            raise HTTPException(413, 'trial_archive_too_large')
    data = bytes(raw)
    if request.headers.get('content-type','').startswith('multipart/form-data'):
        from email.parser import BytesParser
        from email.policy import default
        message = BytesParser(policy=default).parsebytes(b'Content-Type: ' + request.headers['content-type'].encode() + b'\r\nMIME-Version: 1.0\r\n\r\n' + data)
        parts = list(message.iter_parts())
        if len(parts) != 1 or parts[0].get_param('name', header='content-disposition') != 'file':
            raise HTTPException(400, 'invalid_trial_upload')
        data = parts[0].get_payload(decode=True)
    elif data:
        raise HTTPException(415, 'multipart_file_required')
    else:
        data = archive_bytes()
    manifest, photos = validate_archive(data)
    body_hash = hashlib.sha256(data).hexdigest()
    project, zone = uuid4(), uuid4()
    with request.app.state.store.engine.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(:lock)'), {'lock': key.int % (2**63)})
        previous = connection.execute(text('SELECT body_sha256,project_id FROM trial_imports WHERE user_id=:user AND request_key=:key'), {'user':user['id'], 'key':key}).first()
        if previous:
            if previous.body_sha256 != body_hash:
                raise HTTPException(409, 'idempotency_key_conflict')
            return {'project_id': str(previous.project_id)}
        connection.execute(text("INSERT INTO site_projects(id,name,timezone) VALUES (:id,:name,'Europe/Moscow')"), {'id':project, 'name':'Учебный пример: ' + manifest['name']})
        connection.execute(text("INSERT INTO site_zones(id,project_id,name) VALUES (:id,:project,'Учебный участок')"), {'id':zone,'project':project})
        connection.execute(text("INSERT INTO project_members(project_id,user_id,role) VALUES (:project,:user,'owner')"), {'project':project,'user':user['id']})
        _seed_trial(connection, user['id'], key, project, zone, manifest, photos, body_hash)
    return {'project_id':str(project)}


def _seed_trial(connection, user_id, key, project, zone, manifest, photos, body_hash):
    source_hash = hashlib.sha256(json.dumps(manifest['plan'],sort_keys=True).encode()).hexdigest()
    connection.execute(text('SELECT pg_advisory_xact_lock(804298270115)'))
    connection.execute(text("INSERT INTO catalog_sources(sha256,filename,sheet_name,row_count) VALUES (:hash,'trial-manifest.json','Учебный план',:count) ON CONFLICT DO NOTHING"), {'hash':source_hash,'count':len(manifest['plan'])})
    revision = uuid4()
    connection.execute(text('INSERT INTO zone_plan_revisions(id,zone_id,revision_number) VALUES (:id,:zone,(SELECT coalesce(max(revision_number),0)+1 FROM zone_plan_revisions WHERE zone_id=:zone))'), {'id':revision,'zone':zone})
    for index, entry in enumerate(manifest['plan'],1):
        work = connection.execute(text('SELECT id FROM catalog_works WHERE source_sha256=:hash AND source_row=:row'), {'hash':source_hash,'row':index}).scalar_one_or_none()
        if work is None:
            work = uuid4()
            connection.execute(text("""INSERT INTO catalog_works(id,source_sha256,source_row,title,code_cell,title_cell,applicability,applicability_cells)
                VALUES (:id,:hash,:row,:title,'trial','trial','{}','{}')"""), {'id':work,'hash':source_hash,'row':index,'title':'Учебный пример: '+entry['title']})
        connection.execute(text("""INSERT INTO zone_plan_entries(id,revision_id,catalog_work_id,starts_at,ends_at,state,expected_equipment,allowed_equipment,excluded_equipment)
            VALUES (:id,:revision,:work,:start,:end,:state,CAST(:equipment AS jsonb),'[]','[]')"""), {'id':uuid4(),'revision':revision,'work':work,'start':datetime.fromisoformat(entry['starts_at']),'end':datetime.fromisoformat(entry['ends_at']),'state':entry['state'],'equipment':json.dumps(entry['expected_equipment'])})
    connection.execute(text('INSERT INTO trial_imports(user_id,request_key,body_sha256,project_id,manifest) VALUES (:user,:key,:hash,:project,CAST(:manifest AS jsonb))'), {'user':user_id,'key':key,'hash':body_hash,'project':project,'manifest':json.dumps(manifest,ensure_ascii=False)})
    for name, payload in photos.items():
        connection.execute(text('INSERT INTO trial_photos(id,project_id,filename,sha256,data) VALUES (:id,:project,:name,:hash,:data)'), {'id':uuid4(),'project':project,'name':name,'hash':hashlib.sha256(payload).hexdigest(),'data':payload})


@router.post('/projects/{project_id}/trial')
def seed_project_trial(project_id: UUID, request: Request):
    user = current_user(request)
    require_origin(request)
    require_project(request, project_id, owner=True)
    try:
        key = UUID(request.headers.get('idempotency-key', ''))
    except ValueError:
        raise HTTPException(400, 'invalid_idempotency_key') from None
    data = archive_bytes()
    manifest, photos = validate_archive(data)
    body_hash = hashlib.sha256(b'tutorial-seed:' + str(project_id).encode() + b':' + data).hexdigest()
    with request.app.state.store.engine.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(:lock)'), {'lock': key.int % (2**63)})
        role = connection.execute(text('SELECT role FROM project_members WHERE project_id=:project AND user_id=:user FOR UPDATE'), {'project':project_id,'user':user['id']}).scalar_one_or_none()
        if role is None:
            raise HTTPException(404, 'project_not_found')
        if role != 'owner':
            raise HTTPException(403, 'insufficient_project_role')
        previous = connection.execute(text('SELECT body_sha256,project_id FROM trial_imports WHERE user_id=:user AND request_key=:key'), {'user':user['id'],'key':key}).first()
        if previous:
            if previous.project_id != project_id or previous.body_sha256 != body_hash:
                raise HTTPException(409, 'idempotency_key_conflict')
            return {'project_id':str(project_id)}
        connection.execute(text('SELECT id FROM site_projects WHERE id=:project FOR UPDATE'), {'project':project_id}).one()
        zones = connection.execute(text('SELECT id,name FROM site_zones WHERE project_id=:project ORDER BY created_at,id FOR UPDATE'), {'project':project_id}).all()
        occupied = connection.execute(text("""SELECT EXISTS(SELECT 1 FROM site_projects WHERE id=:project AND cover_sha256 IS NOT NULL)
            OR EXISTS(SELECT 1 FROM trial_imports WHERE project_id=:project)
            OR EXISTS(SELECT 1 FROM analysis_runs WHERE request_context->>'project_id'=:project_text)
            OR EXISTS(SELECT 1 FROM zone_plan_revisions r JOIN site_zones z ON z.id=r.zone_id WHERE z.project_id=:project)
            OR EXISTS(SELECT 1 FROM site_signals s JOIN site_zones z ON z.id=s.zone_id WHERE z.project_id=:project)"""), {'project':project_id,'project_text':str(project_id)}).scalar_one()
        if occupied or len(zones)>1 or zones and zones[0].name != 'Основной участок':
            raise HTTPException(409, 'project_not_empty')
        if zones:
            zone = zones[0].id
        else:
            zone = uuid4()
            connection.execute(text("INSERT INTO site_zones(id,project_id,name) VALUES (:id,:project,'Основной участок')"), {'id':zone,'project':project_id})
        _seed_trial(connection, user['id'], key, project_id, zone, manifest, photos, body_hash)
    return {'project_id':str(project_id)}
