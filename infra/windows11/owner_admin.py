import json
import os
from pathlib import Path
import secrets
import sys

from sqlalchemy import text


os.environ.update(json.loads(Path('/etc/lzt/runtime.json').read_text()))
sys.path.insert(0, '/opt/lzt/current/backend')
from app.adapters.postgres import PostgresStore
from app.application.admin_password import hash_password

credentials = Path('/mnt/c/ProgramData/LztEvidence/secrets/admin-login.json')
store = PostgresStore(os.environ['DATABASE_URL'])
try:
    with store.engine.begin() as db:
        existing = db.execute(text("SELECT 1 FROM admin_credentials WHERE login='gorshenin-nik'")).first()
        if existing:
            if not credentials.is_file():
                raise RuntimeError('Existing admin credential has no local owner handoff; do not reset it')
        else:
            if credentials.is_file():
                saved = json.loads(credentials.read_text())
                if saved.get('login') != 'gorshenin-nik' or not isinstance(saved.get('password'), str) or len(saved['password']) < 12:
                    raise RuntimeError('Stored administrator credential is invalid')
                password = saved['password']
            else:
                password = secrets.token_urlsafe(24)
                credentials.write_text(json.dumps({'login': 'gorshenin-nik', 'password': password}))
            db.execute(text('INSERT INTO admin_credentials(login,password_hash) VALUES (:login,:hash)'),
                       {'login': 'gorshenin-nik', 'hash': hash_password(password)})
    print(json.dumps({'admin': 'configured', 'credential_file': str(credentials)}))
finally:
    store.close()
