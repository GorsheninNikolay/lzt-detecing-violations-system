from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile


config = json.loads(Path('/etc/lzt/runtime.json').read_text())
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
target = Path('/mnt/c/ProgramData/LztEvidence/backups') / stamp
target.mkdir(mode=0o700)
subprocess.run(['systemctl', 'stop', 'lzt-web', 'lzt-backend', 'lzt-minio'], check=True)
try:
    env = os.environ | {'PGPASSWORD': config['DATABASE_PASSWORD']}
    subprocess.run(['/usr/bin/pg_dump', '--no-password', '--host=127.0.0.1', '--username=lzt_evidence',
                    '--format=custom', '--file=' + str(target / 'database.dump'), 'lzt_evidence'],
                   env=env, check=True, stderr=subprocess.PIPE)
    subprocess.run(['/usr/bin/pg_restore', '--list', str(target / 'database.dump')], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    with tarfile.open(target / 'storage-config.tar.gz', 'w:gz') as archive:
        archive.add('/var/lib/lzt/artifacts', arcname='artifacts')
        archive.add('/etc/lzt', arcname='config')
        archive.add('/mnt/c/ProgramData/LztEvidence/secrets', arcname='windows-secrets')
        archive.add('/opt/lzt/current/release.json', arcname='release.json')
    manifest = {'created_at': stamp, 'files': {p.name: hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
                for p in target.iterdir() if p.is_file()}, 'database_dump_list_verified': True}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps({'backup': str(target), 'verified': True, 'files': list(manifest['files'])}))
finally:
    subprocess.run(['systemctl', 'start', 'lzt-minio', 'lzt-backend', 'lzt-web'], check=True)
