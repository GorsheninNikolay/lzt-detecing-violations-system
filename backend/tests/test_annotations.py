import io
import json
import os
import secrets
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DatabaseError

from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import PostgresStore
from app.application import annotations
from app.application.admin_password import hash_password
from app.application.engagement import router as engagement_router
from app.config import Config


def test_geometry_and_rotation_identity():
    item = {'id': str(uuid4()), 'class_name': 'truck', 'box': [.1, .2, .8, .9]}
    assert annotations.objects([item, {**item, 'id': str(uuid4())}])
    for invalid in ([item, item], [{**item, 'box': [0, 0, float('nan'), 1]}], [{**item, 'box': [0, 0, 0, 1]}], [{**item, 'class_name': 'unsupported'}]):
        with pytest.raises(HTTPException):
            annotations.objects(invalid)
    image = Image.new('RGB', (30, 20), 'red')
    ImageDraw.Draw(image).rectangle((1, 1, 10, 8), fill='blue')
    assert annotations.pixel_hash(image) == annotations.pixel_hash(image.transpose(Image.Transpose.ROTATE_90))


@pytest.fixture
def service():
    test_url = os.environ['TEST_DATABASE_URL']
    assert make_url(test_url).database != make_url(os.environ['DATABASE_URL']).database
    assert os.environ['TEST_S3_BUCKET'] != os.environ['S3_BUCKET']
    store = PostgresStore(test_url)
    artifacts = ArtifactStore(replace(Config.from_env(), database_url=test_url, s3_bucket=os.environ['TEST_S3_BUCKET']))
    app = FastAPI()
    app.state.store, app.state.artifacts = store, artifacts
    app.include_router(annotations.router)
    app.include_router(engagement_router)
    with store.engine.begin() as connection:
        connection.execute(text('TRUNCATE admin_sessions,admin_credentials,request_limits'))
        password = secrets.token_urlsafe(24)
        connection.execute(text("INSERT INTO admin_credentials VALUES ('gorshenin-nik',:hash)"), {'hash': hash_password(password)})
    with TestClient(app, base_url='https://testserver') as client:
        response = client.post('/admin/login', headers={'origin':'https://testserver'}, json={'login':'gorshenin-nik','password':password})
        assert response.status_code == 200
        headers = {'origin':'https://testserver','x-csrf-token':response.json()['csrf']}
        yield client, store, artifacts, headers
    store.close()


def seed(store, artifacts, payload=None):
    if payload is None:
        image = Image.new('RGB', (40, 20), (30, 70, 100))
        ImageDraw.Draw(image).rectangle((0, 0, 10, 10), fill='red')
        exif = Image.Exif(); exif[274] = 6
        output = io.BytesIO(); image.save(output, format='JPEG', exif=exif)
        payload = output.getvalue()
    sha = annotations.digest(payload)
    run, frame, artifact, intent = [uuid4() for _ in range(4)]
    artifacts.client.put_object(Bucket=artifacts.bucket, Key=f'sha256/{sha}', Body=payload)
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO analysis_runs(id,state,purpose) VALUES (:id,'queued','ordinary')"), {'id':run})
        connection.execute(text("INSERT INTO publication_intents(id,state,run_id,idempotency_key,media_type) VALUES (:id,'published',:run,:key,'image/jpeg')"), {'id':intent,'run':run,'key':str(intent)})
        connection.execute(text("INSERT INTO artifact_metadata(id,run_id,intent_id,key,sha256,size,media_type) VALUES (:id,:run,:intent,:key,:sha,:size,'image/jpeg')"), {'id':artifact,'run':run,'intent':intent,'key':f'sha256/{sha}','sha':sha,'size':len(payload)})
        connection.execute(text("INSERT INTO run_inputs(run_id,ordinal,input_id,sha256,size,context,artifact_id) VALUES (:run,0,:input,:sha,:size,'{}',:artifact)"), {'run':run,'input':frame,'sha':sha,'size':len(payload),'artifact':artifact})
    return run, frame, artifact, sha


def test_roundtrip_retry_concurrency_export_orientation_and_immutability(service):
    client, store, artifacts, auth = service
    run, frame, artifact, sha = seed(store, artifacts)
    endpoint = f'/runs/{run}/frames/{frame}/annotations'
    assert client.get(endpoint).json()['objects'] == []
    corrected = [{'id':str(uuid4()),'class_name':'excavator','box':[.1,.2,.6,.8]}, {'id':str(uuid4()),'class_name':'excavator','box':[.65,.1,.9,.5]}]
    body = {'input_sha256':sha,'objects':corrected}
    key = str(uuid4())
    response = client.post(endpoint,headers={'idempotency-key':key},json=body)
    assert response.status_code == 200, response.text
    proposal = response.json()['id']
    assert client.post(endpoint,headers={'idempotency-key':key},json=body).json() == response.json()
    assert client.post(endpoint,headers={'idempotency-key':key},json={**body,'objects':[]}).status_code == 409
    review = f'/admin/annotations/{proposal}/review'
    decision = {'expected_revision':1,'objects':corrected,'status':'approved','whole_frame_verified':True,'reason':''}
    assert client.post(review,json=decision).status_code == 403
    assert client.post(review,headers={**auth,'idempotency-key':str(uuid4())},json={**decision,'whole_frame_verified':False}).status_code == 400
    headers = {**auth,'idempotency-key':str(uuid4())}
    accepted = client.post(review,headers=headers,json=decision)
    assert accepted.status_code == 200, accepted.text
    assert client.post(review,headers=headers,json=decision).json() == accepted.json()
    assert client.post(review,headers={**auth,'idempotency-key':str(uuid4())},json=decision).status_code == 409
    version = accepted.json()['version_id']
    exported = client.post('/admin/annotations/export',headers=auth,json={'version_ids':[version,version]})
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        coco = json.loads(archive.read('annotations.json'))
        assert len(coco['images']) == 1 and len(coco['annotations']) == 2
        assert coco['images'][0]['width'] == 20 and coco['images'][0]['height'] == 40
        assert coco['annotations'][0]['bbox'] == pytest.approx([2,8,10,24])
        assert Image.open(io.BytesIO(archive.read('images/1.png'))).size == (20,40)
        assert json.loads(archive.read('provenance.json'))['versions'][0]['input_sha256'] == sha
    preview = client.get(f'/runs/{run}/artifacts/{artifact}/thumbnail')
    assert preview.status_code == 200 and Image.open(io.BytesIO(preview.content)).size == (20,40)
    with store.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM detected_objects WHERE run_id=:run'), {'run':run}).scalar_one() == 0
        assert connection.execute(text('SELECT count(*) FROM annotation_proposals WHERE id=:id'), {'id':proposal}).scalar_one() == 1
    with pytest.raises(DatabaseError), store.engine.begin() as connection:
        connection.execute(text("UPDATE annotation_versions SET objects='[]' WHERE id=:id"), {'id':version})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client.post,review,headers={**auth,'idempotency-key':str(uuid4())},json={**decision,'expected_revision':2,'status':'pending'}) for _ in range(2)]
        assert sorted(f.result().status_code for f in futures) == [200,409]
    pending_version = next(row['version_id'] for row in client.get('/admin/annotations').json()['annotations'] if row['id'] == proposal)
    assert client.post('/admin/annotations/export',headers=auth,json={'version_ids':[pending_version]}).status_code == 409
    assert client.post(review,headers={**auth,'idempotency-key':str(uuid4())},json={**decision,'expected_revision':3,'status':'rejected','reason':'Missing object'}).status_code == 200


def test_export_fails_closed_for_missing_inventory_and_reserved_decoded_copy(service, monkeypatch):
    client, store, artifacts, auth = service
    run, frame, artifact, sha = seed(store, artifacts)
    with store.engine.connect() as connection:
        hashes, pixels = annotations.reserved_images(connection, artifacts)
        assert len(hashes) >= 11 and len(pixels) >= 11
    body = {'input_sha256':sha,'objects':[]}
    proposal = client.post(f'/runs/{run}/frames/{frame}/annotations',headers={'idempotency-key':str(uuid4())},json=body).json()['id']
    version = client.post(f'/admin/annotations/{proposal}/review',headers={**auth,'idempotency-key':str(uuid4())},json={'objects':[],'status':'approved','whole_frame_verified':True,'reason':'','expected_revision':1}).json()['version_id']
    with store.engine.connect() as connection:
        image = annotations.image_bytes(artifacts,annotations.source(connection,run,frame))
    monkeypatch.setattr(annotations,'reserved_images',lambda *_: (set(),{annotations.pixel_hash(image)}))
    assert client.post('/admin/annotations/export',headers=auth,json={'version_ids':[version]}).status_code == 409
    monkeypatch.undo()
    monkeypatch.setattr(annotations,'INVENTORY',annotations.INVENTORY.with_name('missing.json'))
    assert client.post('/admin/annotations/export',headers=auth,json={'version_ids':[version]}).status_code == 503
    client.cookies.clear()
    assert client.get('/admin/annotations').status_code == 401
    assert client.post('/admin/annotations/export',headers=auth,json={'version_ids':[version]}).status_code == 401


def test_export_deduplicates_distinct_selected_proposals_and_keeps_provenance(service):
    client, store, artifacts, auth = service
    versions = []
    for _ in range(2):
        run, frame, artifact, sha = seed(store, artifacts)
        corrected = [{'id':str(uuid4()),'class_name':'truck','box':[.1,.1,.5,.5]}]
        proposal = client.post(f'/runs/{run}/frames/{frame}/annotations',headers={'idempotency-key':str(uuid4())},json={'input_sha256':sha,'objects':corrected}).json()['id']
        version = client.post(f'/admin/annotations/{proposal}/review',headers={**auth,'idempotency-key':str(uuid4())},json={'objects':corrected,'status':'approved','whole_frame_verified':True,'reason':'','expected_revision':1}).json()['version_id']
        assert client.get(f'/admin/annotations/{proposal}').json()['revision'] == 2
        versions.append(version)
    response = client.post('/admin/annotations/export',headers=auth,json={'version_ids':versions})
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert len(json.loads(archive.read('annotations.json'))['images']) == 1
        provenance = json.loads(archive.read('provenance.json'))
        assert {item['version_id'] for item in provenance['versions']} == set(versions)
        assert provenance['versions'][1]['deduplicated']
    conflicting = client.post(f'/admin/annotations/{proposal}/review', headers={**auth,'idempotency-key':str(uuid4())},
        json={'objects':[{**corrected[0],'box':[.2,.2,.7,.7]}],'status':'approved',
              'whole_frame_verified':True,'reason':'','expected_revision':2}).json()['version_id']
    rejected = client.post('/admin/annotations/export',headers=auth,json={'version_ids':[versions[0],conflicting]})
    assert rejected.status_code == 409 and rejected.json()['detail'] == 'duplicate_frame_versions'


def test_db_reserved_frame_excludes_rotated_copy_and_fails_closed_on_missing_bytes(service):
    client, store, artifacts, auth = service
    image = Image.frombytes('RGB',(11,7),secrets.token_bytes(11*7*3))
    payload = io.BytesIO();image.save(payload,format='PNG');original = payload.getvalue()
    original_run, original_frame, _, sha = seed(store,artifacts,original)
    with store.engine.begin() as connection:
        connection.execute(text('''INSERT INTO evaluation_set_revisions
            (id,revision_number,manifest_hash,manifest,inventory_evidence)
            VALUES (:id,(SELECT coalesce(max(revision_number),0)+1 FROM evaluation_set_revisions),:hash,
                    CAST(:manifest AS jsonb),'[]')'''),
            {'id':uuid4(),'hash':str(uuid4()),'manifest':json.dumps({'frames':[{'image':{'sha256':sha}}]})})
    rotated = io.BytesIO();image.transpose(Image.Transpose.ROTATE_90).save(rotated,format='PNG')
    rotated_run, rotated_frame, _, rotated_sha = seed(store,artifacts,rotated.getvalue())
    assert sha != rotated_sha
    for run, frame, checksum in ((original_run,original_frame,sha),(rotated_run,rotated_frame,rotated_sha)):
        proposal = client.post(f'/runs/{run}/frames/{frame}/annotations',headers={'idempotency-key':str(uuid4())},
            json={'input_sha256':checksum,'objects':[]}).json()['id']
        version = client.post(f'/admin/annotations/{proposal}/review',headers={**auth,'idempotency-key':str(uuid4())},
            json={'objects':[],'status':'approved','whole_frame_verified':True,'reason':'','expected_revision':1}).json()['version_id']
        exported = client.post('/admin/annotations/export',headers=auth,json={'version_ids':[version]})
        assert exported.status_code == 409 and exported.json()['detail'] == 'reserved_frame'
    try:
        artifacts.client.delete_object(Bucket=artifacts.bucket,Key=f'sha256/{sha}')
        unavailable = client.post('/admin/annotations/export',headers=auth,json={'version_ids':[version]})
        assert unavailable.status_code == 503 and unavailable.json()['detail'] == 'exclusion_evidence_unavailable'
    finally:
        artifacts.client.put_object(Bucket=artifacts.bucket,Key=f'sha256/{sha}',Body=original)
