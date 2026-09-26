"""Human corrections are immutable versions, never edits to analysis evidence."""
import asyncio
import io
import json
import math
import warnings
import zipfile
from pathlib import Path
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from PIL import Image, ImageOps
from sqlalchemy import text

from app.application.engagement import admin_session, body, digest, engine, identifier, limit

router = APIRouter()
CLASSES = ('excavator', 'dump_truck', 'road_roller', 'truck_mounted_crane',
           'concrete_mixer_truck', 'bulldozer', 'truck', 'mobile_crane')
INVENTORY = Path(__file__).resolve().parents[2] / 'admission/exclusions/held_out_evaluation.json'
MAX_IMAGE_BYTES = 16_000_000
MAX_EXPORT_BYTES = 128_000_000


def objects(value):
    if not isinstance(value, list) or len(value) > 300:
        raise HTTPException(400, 'invalid_objects')
    result, identities = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise HTTPException(400, 'invalid_objects')
        identity = str(identifier(item.get('id')))
        box = item.get('box')
        if (identity in identities or item.get('class_name') not in CLASSES
                or not isinstance(box, list) or len(box) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in box)
                or box[0] >= box[2] or box[1] >= box[3]):
            raise HTTPException(400, 'invalid_objects')
        identities.add(identity)
        result.append({'id': identity, 'class_name': item['class_name'], 'box': box})
    return result


def image_bytes(artifacts, row):
    if not 0 < row['size'] <= MAX_IMAGE_BYTES:
        raise HTTPException(413, 'image_too_large')
    try:
        payload = artifacts.read_verified(row['key'], row['sha256'], row['size'])
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as source:
                if source.width * source.height > 40_000_000:
                    raise ValueError()
                return ImageOps.exif_transpose(source).convert('RGB')
    except Exception:
        raise HTTPException(503, 'image_unavailable') from None


def pixel_hash(image):
    # Rotation-invariant decoded identity also catches EXIF-only orientation copies.
    hashes = []
    for rotation in (None, Image.Transpose.ROTATE_90, Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_270):
        rotated = image if rotation is None else image.transpose(rotation)
        hashes.append(digest(f'{rotated.width}x{rotated.height}:'.encode() + rotated.tobytes()))
    return min(hashes)


def source(connection, run_id, input_id):
    row = connection.execute(text('''SELECT i.input_id,i.sha256,a.id AS artifact_id,a.key,a.size,
        r.profile_id,r.profile_snapshot FROM run_inputs i JOIN analysis_runs r ON r.id=i.run_id
        JOIN artifact_metadata a ON a.id=i.artifact_id AND a.run_id=i.run_id
        WHERE i.run_id=:run AND i.input_id=:input AND r.purpose='ordinary'
        AND a.sha256=i.sha256 AND a.size=i.size'''), {'run': run_id, 'input': input_id}).mappings().first()
    if row is None:
        raise HTTPException(404, 'frame_not_found')
    return dict(row)


def original_objects(connection, run_id, input_id):
    return [dict(item) | {'id': str(item['id'])} for item in connection.execute(text('''
        SELECT id,class_name,box FROM detected_objects WHERE run_id=:run AND input_id=:input
        ORDER BY ordinal'''), {'run': run_id, 'input': input_id}).mappings()]


@router.get('/runs/{run_id}/frames/{input_id}/annotations')
def frame_annotations(run_id: UUID, input_id: UUID, request: Request):
    with engine(request).connect() as connection:
        row = source(connection, run_id, input_id)
        return {'run_id': str(run_id), 'input_id': str(input_id), 'input_sha256': row['sha256'],
                'objects': original_objects(connection, run_id, input_id), 'classes': CLASSES}


@router.post('/runs/{run_id}/frames/{input_id}/annotations')
async def propose(run_id: UUID, input_id: UUID, request: Request):
    await asyncio.to_thread(limit, request, 'annotations', 30, 3600)
    key = identifier(request.headers.get('idempotency-key'))
    value, body_hash = await body(request, 150_000)
    return await asyncio.to_thread(save_proposal, request, run_id, input_id, key, value, body_hash)


def save_proposal(request, run_id, input_id, key, value, body_hash):
    corrected = objects(value.get('objects'))
    with engine(request).begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(:lock)'), {'lock': key.int % 2**63})
        existing = connection.execute(text('SELECT * FROM annotation_proposals WHERE request_key=:key'), {'key': key}).mappings().first()
        if existing:
            if existing['body_sha256'] != body_hash or existing['run_id'] != run_id or existing['input_id'] != input_id:
                raise HTTPException(409, 'idempotency_key_conflict')
            return {'id': str(existing['id']), 'status': 'pending'}
        row = source(connection, run_id, input_id)
        if value.get('input_sha256') != row['sha256']:
            raise HTTPException(409, 'source_changed')
        proposal_id = uuid5(NAMESPACE_URL, f'annotation/{key}')
        connection.execute(text('''INSERT INTO annotation_proposals
            (id,request_key,body_sha256,run_id,input_id,input_sha256,artifact_id,profile_id,profile_snapshot,original_objects)
            VALUES (:id,:key,:hash,:run,:input,:sha,:artifact,:profile,CAST(:snapshot AS jsonb),CAST(:original AS jsonb))'''),
            {'id': proposal_id, 'key': key, 'hash': body_hash, 'run': run_id, 'input': input_id,
             'sha': row['sha256'], 'artifact': row['artifact_id'], 'profile': row['profile_id'],
             'snapshot': json.dumps(row['profile_snapshot'] or {}),
             'original': json.dumps(original_objects(connection, run_id, input_id))})
        insert_version(connection, proposal_id, 1, corrected, 'pending', False, '', key, body_hash)
    return {'id': str(proposal_id), 'status': 'pending'}


def insert_version(connection, proposal, revision, corrected, status, verified, reason, key, body_hash):
    version_id = uuid4()
    connection.execute(text('''INSERT INTO annotation_versions
        (id,proposal_id,revision,objects,status,whole_frame_verified,reason,request_key,body_sha256)
        VALUES (:id,:proposal,:revision,CAST(:objects AS jsonb),:status,:verified,:reason,:key,:hash)'''),
        {'id': version_id, 'proposal': proposal, 'revision': revision, 'objects': json.dumps(corrected),
         'status': status, 'verified': verified, 'reason': reason, 'key': key, 'hash': body_hash})
    return {'id': str(proposal), 'version_id': str(version_id), 'revision': revision, 'status': status}


@router.get('/admin/annotations')
def queue(request: Request, offset: int = 0, session=Depends(admin_session)):
    if offset < 0:
        raise HTTPException(400, 'invalid_offset')
    with engine(request).connect() as connection:
        rows = connection.execute(text('''SELECT p.*,v.id AS version_id,v.revision,v.objects,v.status,
            v.whole_frame_verified,v.reason FROM annotation_proposals p
            JOIN LATERAL (SELECT * FROM annotation_versions WHERE proposal_id=p.id ORDER BY revision DESC LIMIT 1) v ON true
            ORDER BY p.created_at DESC,p.id LIMIT 50 OFFSET :offset'''), {'offset': offset}).mappings().all()
    return {'annotations': [dict(row) for row in rows], 'next_offset': offset + 50 if len(rows) == 50 else None}


@router.get('/admin/annotations/{proposal_id}')
def annotation_detail(proposal_id: UUID, request: Request, session=Depends(admin_session)):
    with engine(request).connect() as connection:
        row = connection.execute(text('''SELECT p.*,v.id AS version_id,v.revision,v.objects,v.status,
            v.whole_frame_verified,v.reason FROM annotation_proposals p
            JOIN LATERAL (SELECT * FROM annotation_versions WHERE proposal_id=p.id ORDER BY revision DESC LIMIT 1) v ON true
            WHERE p.id=:id'''), {'id': proposal_id}).mappings().first()
    if row is None:
        raise HTTPException(404, 'annotation_not_found')
    return dict(row)


@router.post('/admin/annotations/{proposal_id}/review')
async def review(proposal_id: UUID, request: Request, session=Depends(admin_session)):
    key = identifier(request.headers.get('idempotency-key'))
    value, body_hash = await body(request, 150_000)
    return await asyncio.to_thread(save_review, request, proposal_id, key, value, body_hash)


def save_review(request, proposal_id, key, value, body_hash):
    corrected = objects(value.get('objects'))
    status, verified, reason = value.get('status'), value.get('whole_frame_verified'), value.get('reason', '')
    if (status not in ('pending', 'approved', 'rejected') or type(verified) is not bool
            or not isinstance(reason, str) or len(reason) > 3000 or type(value.get('expected_revision')) is not int
            or status == 'approved' and not verified or status == 'rejected' and not reason.strip()):
        raise HTTPException(400, 'invalid_review')
    with engine(request).begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(:lock)'), {'lock': key.int % 2**63})
        proposal = connection.execute(text('SELECT id FROM annotation_proposals WHERE id=:id FOR UPDATE'), {'id': proposal_id}).first()
        if proposal is None:
            raise HTTPException(404, 'annotation_not_found')
        existing = connection.execute(text('SELECT * FROM annotation_versions WHERE request_key=:key'), {'key': key}).mappings().first()
        if existing:
            if existing['body_sha256'] != body_hash or existing['proposal_id'] != proposal_id:
                raise HTTPException(409, 'idempotency_key_conflict')
            return {'id': str(proposal_id), 'version_id': str(existing['id']), 'revision': existing['revision'], 'status': existing['status']}
        revision = connection.execute(text('SELECT max(revision) FROM annotation_versions WHERE proposal_id=:id'), {'id': proposal_id}).scalar_one()
        if value['expected_revision'] != revision:
            raise HTTPException(409, 'stale_revision')
        return insert_version(connection, proposal_id, revision + 1, corrected, status, verified, reason.strip(), key, body_hash)


def reserved_images(connection, artifacts):
    try:
        inventory = json.loads(INVENTORY.read_text())
        if inventory['schema_revision'] != 'exclusion-inventory-v1' or inventory['tier'] != 'held_out_evaluation':
            raise ValueError()
        entries = list(inventory['fixtures'])
        if not entries:
            raise ValueError()
        for manifest in connection.execute(text('SELECT manifest FROM evaluation_set_revisions')).scalars():
            entries.extend(manifest['frames'])
        hashes = {item[name]['sha256'] for item in entries for name in ('image', 'derived_image') if item.get(name)}
        fingerprints_payload = INVENTORY.with_name('held_out_pixel_fingerprints.json').read_bytes()
        if digest(fingerprints_payload) != 'e755020e71e0e10ac590d080b8ee354d2666b9943f95447c4ddc8980225c9b42':
            raise ValueError()
        fingerprints = {item['sha256']: item['pixel_sha256'] for item in json.loads(fingerprints_payload)['fixtures']}
        hashes.update(fingerprints)
        canonical = set()
        for sha in hashes:
            if sha in fingerprints:
                canonical.add(fingerprints[sha])
                continue
            row = connection.execute(text('SELECT key,sha256,size FROM artifact_metadata WHERE sha256=:sha LIMIT 1'), {'sha': sha}).mappings().first()
            if row is None:
                raise ValueError()
            canonical.add(pixel_hash(image_bytes(artifacts, row)))
        return hashes, canonical
    except Exception:
        raise HTTPException(503, 'exclusion_evidence_unavailable') from None


@router.post('/admin/annotations/export')
async def export(request: Request, session=Depends(admin_session)):
    await asyncio.to_thread(limit, request, 'annotation_export', 6)
    value, _ = await body(request, 8192)
    ids = value.get('version_ids')
    if not isinstance(ids, list) or not 0 < len(ids) <= 32:
        raise HTTPException(400, 'invalid_selection')
    selected = list(dict.fromkeys(identifier(item) for item in ids))
    return await asyncio.to_thread(export_versions, request, selected)


def export_versions(request, selected):
    archive = io.BytesIO()
    coco = {'images': [], 'annotations': [], 'categories': [{'id': index + 1, 'name': name} for index, name in enumerate(CLASSES)]}
    provenance, seen, total = [], {}, 0
    with engine(request).connect().execution_options(isolation_level='REPEATABLE READ') as connection, zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        reserved, canonical = reserved_images(connection, request.app.state.artifacts)
        for version in selected:
            row = connection.execute(text('''SELECT v.*,p.run_id,p.input_id,p.input_sha256,p.artifact_id,
                p.profile_id,p.profile_snapshot,a.key,a.sha256,a.size FROM annotation_versions v
                JOIN annotation_proposals p ON p.id=v.proposal_id JOIN artifact_metadata a ON a.id=p.artifact_id
                WHERE v.id=:id'''), {'id': version}).mappings().first()
            if row is None or row['status'] != 'approved' or not row['whole_frame_verified']:
                raise HTTPException(409, 'version_not_approved')
            if row['sha256'] != row['input_sha256'] or row['sha256'] in reserved:
                raise HTTPException(409, 'reserved_frame')
            image = image_bytes(request.app.state.artifacts, row)
            identity = pixel_hash(image)
            if identity in canonical:
                raise HTTPException(409, 'reserved_frame')
            identity = digest(f'{image.width}x{image.height}:'.encode() + image.tobytes())
            signature = sorted((item['class_name'], tuple(item['box'])) for item in objects(row['objects']))
            if identity in seen:
                previous = seen[identity]
                if previous['signature'] != signature:
                    raise HTTPException(409, 'duplicate_frame_versions')
                provenance.append({**previous['provenance'], 'version_id': str(version),
                    'proposal_id': str(row['proposal_id']), 'revision': row['revision'],
                    'run_id': str(row['run_id']), 'input_id': str(row['input_id']),
                    'input_sha256': row['input_sha256'], 'profile_id': str(row['profile_id']) if row['profile_id'] else None,
                    'profile_snapshot': row['profile_snapshot'], 'objects': row['objects'], 'deduplicated': True})
                continue
            encoded = io.BytesIO()
            image.save(encoded, format='PNG')
            total += encoded.tell()
            if total > MAX_EXPORT_BYTES:
                raise HTTPException(413, 'export_too_large')
            image_id = len(coco['images']) + 1
            filename = f'images/{image_id}.png'
            output.writestr(filename, encoded.getvalue())
            coco['images'].append({'id': image_id, 'file_name': filename, 'width': image.width, 'height': image.height})
            for item in objects(row['objects']):
                x1, y1, x2, y2 = item['box']
                box = [x1 * image.width, y1 * image.height, (x2 - x1) * image.width, (y2 - y1) * image.height]
                coco['annotations'].append({'id': len(coco['annotations']) + 1, 'image_id': image_id,
                    'category_id': CLASSES.index(item['class_name']) + 1, 'bbox': box, 'area': box[2] * box[3], 'iscrowd': 0})
            provenance.append({'image_id': image_id, 'version_id': str(version), 'proposal_id': str(row['proposal_id']),
                'revision': row['revision'], 'run_id': str(row['run_id']), 'input_id': str(row['input_id']),
                'input_sha256': row['input_sha256'], 'export_sha256': digest(encoded.getvalue()),
                'profile_id': str(row['profile_id']) if row['profile_id'] else None,
                'profile_snapshot': row['profile_snapshot'], 'objects': row['objects'],
                'orientation': 'EXIF-transposed RGB; normalized xyxy converted to COCO pixel xywh'})
            seen[identity] = {'signature': signature, 'provenance': provenance[-1]}
        output.writestr('annotations.json', json.dumps(coco))
        output.writestr('provenance.json', json.dumps({'versions': provenance, 'selected_version_ids': [str(v) for v in selected],
            'exclusion': 'Exact and decoded rotation-invariant reserved images excluded. Unknown source groups cannot be verified.'}))
    return Response(archive.getvalue(), media_type='application/zip', headers={'Cache-Control': 'no-store', 'Content-Disposition': 'attachment; filename="annotations.zip"'})


@router.get('/runs/{run_id}/artifacts/{artifact_id}/thumbnail')
def thumbnail(run_id: UUID, artifact_id: UUID, request: Request):
    with engine(request).connect() as connection:
        row = connection.execute(text('''SELECT a.key,a.sha256,a.size FROM artifact_metadata a
            JOIN run_inputs i ON i.artifact_id=a.id AND i.run_id=a.run_id
            JOIN analysis_runs r ON r.id=i.run_id
            WHERE a.id=:artifact AND a.run_id=:run AND r.purpose IN ('ordinary','comparison_campaign')'''),
            {'artifact': artifact_id, 'run': run_id}).mappings().first()
    if row is None:
        raise HTTPException(404, 'artifact_not_found')
    image = image_bytes(request.app.state.artifacts, row)
    image.thumbnail((480, 480))
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=80)
    return Response(output.getvalue(), media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=3600', 'X-Content-Type-Options': 'nosniff'})
