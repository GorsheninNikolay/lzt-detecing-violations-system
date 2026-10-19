import json
import os
from pathlib import Path
import sys

from sqlalchemy import text


config = json.loads(Path('/etc/lzt/runtime.json').read_text())
os.environ.update(config)
sys.path.insert(0, '/opt/lzt/current/backend')
from app.adapters.postgres import PostgresStore

store = PostgresStore(config['DATABASE_URL'])
try:
    with store.engine.connect() as db:
        submissions = [dict(row) for row in db.execute(text('SELECT idempotency_key,state,run_id,error_code FROM submission_requests LIMIT 8')).mappings()]
        runs = [dict(row) for row in db.execute(text('SELECT id,state,error_code FROM analysis_runs ORDER BY created_at DESC LIMIT 8')).mappings()]
        calls = db.execute(text('SELECT count(*) FROM deepseek_calls')).scalar_one()
    print(json.dumps({'admission_manifest_present': Path('/opt/lzt/current/backend/admission/manifest.json').is_file(),
                      'submissions': submissions, 'runs': runs, 'provider_calls': calls}, default=str))
finally:
    store.close()
