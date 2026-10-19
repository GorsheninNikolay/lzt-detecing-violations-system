import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tarfile
import time
from urllib.request import urlopen


BASE = Path('/opt/lzt')
CONFIG = Path('/etc/lzt')
LOGS = Path('/var/log/lzt')
WINDOWS = Path('/mnt/c/ProgramData/LztEvidence')


def run(command, **kwargs):
    subprocess.run(command, check=True, **kwargs)


def write_config(path, data, mode=0o644):
    encoded = data.encode() if isinstance(data, str) else data
    if path.exists() and path.read_bytes() != encoded:
        backups = Path('/var/backups/lzt/config')
        backups.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(path, backups / (stamp + '-' + path.name))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.new')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(descriptor, 'wb') as file:
        file.write(encoded)
    os.chmod(temporary, mode)
    temporary.replace(path)


def unpack_release(archive, expected):
    if hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() != expected:
        raise RuntimeError('release_archive_digest_mismatch')
    with tarfile.open(archive) as bundle:
        manifest = json.load(bundle.extractfile('release.json'))
        identity = manifest['source_tree_sha256']
        if len(identity) != 64 or any(c not in '0123456789abcdef' for c in identity):
            raise RuntimeError('release_identity_invalid')
        target = BASE / 'releases' / identity[:16]
        if not target.exists():
            target.mkdir(parents=True)
            bundle.extractall(target, filter='data')
    for name, digest in manifest['files'].items():
        path = (target / name).resolve()
        if not path.is_relative_to(target.resolve()) or hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() != digest:
            raise RuntimeError('release_file_digest_mismatch')
    current = BASE / 'current'
    if current.exists() and not current.is_symlink():
        raise RuntimeError('current_release_is_not_symlink')
    if current.is_symlink():
        current.unlink()
    current.symlink_to(target)
    (WINDOWS / 'current.txt').write_text(identity[:16] + '\n')
    return target


def sql(statement):
    result = subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-v', 'ON_ERROR_STOP=1', '-At'],
                            input=statement.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('database_bootstrap_failed')
    return result.stdout.decode().strip()


def initialize_database(config):
    run(['systemctl', 'start', 'postgresql@17-main'])
    if sql("SELECT 1 FROM pg_roles WHERE rolname='lzt_evidence';") != '1':
        password = config['DATABASE_PASSWORD']
        if not all(c.isalnum() or c in '-_' for c in password):
            raise RuntimeError('database_password_format_invalid')
        sql("CREATE ROLE lzt_evidence LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '" + password + "';")
    if sql("SELECT 1 FROM pg_database WHERE datname='lzt_evidence';") != '1':
        sql("CREATE DATABASE lzt_evidence OWNER lzt_evidence ENCODING 'UTF8' LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8' TEMPLATE template0;")


def wait_http(url):
    for _ in range(60):
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError('local_dependency_not_ready')


def unit(name, text):
    write_config(Path('/etc/systemd/system') / name, text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--mode', choices=('hybrid', 'cloud'), required=True)
    args = parser.parse_args()
    if subprocess.run(['id', 'lzt'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        run(['useradd', '--system', '--create-home', '--home-dir', '/var/lib/lzt', '--shell', '/usr/sbin/nologin', 'lzt'])
    LOGS.mkdir(parents=True, exist_ok=True)
    run(['chown', 'lzt:lzt', str(LOGS)])
    release = unpack_release(args.archive, args.sha256)
    for admission_file in (release / 'backend/admission').rglob('*.json'):
        run(['chown', 'root:lzt', str(admission_file)])
        admission_file.chmod(0o640)
    config_file = CONFIG / 'runtime.json'
    config = json.loads(config_file.read_text()) if config_file.exists() else {
        'DATABASE_PASSWORD': secrets.token_urlsafe(32), 'S3_SECRET_KEY': secrets.token_urlsafe(32)}
    for directory in ('artifacts', 'ultralytics/Ultralytics', 'matplotlib'):
        (Path('/var/lib/lzt') / directory).mkdir(parents=True, exist_ok=True)
    token_file = WINDOWS / 'secrets/deepseek_api_key'
    if not token_file.is_file():
        raise RuntimeError('owner_api_key_file_missing')
    key = token_file.read_text().strip()
    if not key or any(c.isspace() for c in key):
        raise RuntimeError('owner_api_key_file_invalid')
    config.update(DATABASE_URL='postgresql+psycopg://lzt_evidence:' + config['DATABASE_PASSWORD'] + '@127.0.0.1:5432/lzt_evidence',
                  S3_ENDPOINT='http://127.0.0.1:9000', S3_BUCKET='lzt-evidence', S3_ACCESS_KEY='lzt_evidence',
                  S3_REGION='us-east-1', DEEPSEEK_API_KEY=key, CLOUD_PROVIDER='deepseek',
                  API_ROOT_PATH='/api', PYTHONPATH=str(BASE / 'current/backend'),
                  YOLO_MODELS_DIR=str(BASE / 'current/artifacts/Models'),
                  YOLO_CONFIG_DIR='/var/lib/lzt/ultralytics', MPLCONFIGDIR='/var/lib/lzt/matplotlib',
                  PROJECT_COVER_TRUST_PROXY_IP='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                  AUTH_REQUIRED='true', PUBLIC_APP_URL='https://nikolay.tailaf11dc.ts.net:8443')
    write_config(config_file, json.dumps(config, indent=2), 0o600)
    initialize_database(config)
    binary = BASE / 'bin/minio'
    if not binary.exists():
        shutil.copy2(WINDOWS / 'staging/minio-linux-amd64', binary)
    binary.chmod(0o755)
    run(['chown', '-R', 'lzt:lzt', '/var/lib/lzt'])
    write_config(CONFIG / 'minio.env', '\n'.join([
        'MINIO_ROOT_USER=lzt_evidence', 'MINIO_ROOT_PASSWORD=' + config['S3_SECRET_KEY'], 'MINIO_BROWSER=off']) + '\n', 0o600)
    unit('lzt-minio.service', '''[Unit]
Description=LztEvidence private object storage
After=network.target
StartLimitIntervalSec=0
[Service]
User=lzt
Group=lzt
EnvironmentFile=/etc/lzt/minio.env
ExecStart=/opt/lzt/bin/minio server /var/lib/lzt/artifacts --address 127.0.0.1:9000 --console-address 127.0.0.1:9001
Restart=always
RestartSec=5
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/lzt /var/log/lzt
StandardOutput=append:/var/log/lzt/minio.log
StandardError=append:/var/log/lzt/minio.log
[Install]
WantedBy=multi-user.target
''')
    unit('lzt-backend.service', '''[Unit]
Description=LztEvidence construction photo analysis
Requires=postgresql@17-main.service lzt-minio.service
After=postgresql@17-main.service lzt-minio.service
StartLimitIntervalSec=0
[Service]
User=lzt
Group=lzt
WorkingDirectory=/opt/lzt/current/backend
EnvironmentFile=/etc/lzt/runtime.env
ExecStart=/opt/lzt/venv/bin/python /mnt/c/ProgramData/LztEvidence/tools/run_backend.py
Restart=always
RestartSec=5
TimeoutStopSec=45
MemoryMax=3G
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/lzt /var/log/lzt /tmp
[Install]
WantedBy=multi-user.target
''')
    unit('lzt-web.service', '''[Unit]
Description=LztEvidence localhost web proxy
After=lzt-backend.service
StartLimitIntervalSec=0
[Service]
ExecStart=/usr/sbin/nginx -c /etc/lzt/nginx.conf -g "daemon off;"
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
''')
    write_config(CONFIG / 'nginx.conf', '''worker_processes 1;
pid /run/lzt-nginx.pid;
error_log /var/log/lzt/web-error.log;
events { worker_connections 1024; }
http {
    charset utf-8;
    charset_types application/json application/javascript text/css;
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log /var/log/lzt/web-access.log;
    map $http_host $app_scheme {
        default $scheme;
        "nikolay.tailaf11dc.ts.net:8443" https;
    }
    server {
        listen 127.0.0.1:3000;
        server_name _;
        client_max_body_size 220m;
        location /api/ {
            proxy_pass http://127.0.0.1:8007/;
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-Proto $app_scheme;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_read_timeout 300s;
        }
        location / {
            root /opt/lzt/current/web/dist;
            try_files $uri $uri/ /index.html;
        }
    }
}
''')
    write_config(Path('/etc/logrotate.d/lzt'), '''/var/log/lzt/*.log {
    daily
    maxsize 5M
    rotate 3
    missingok
    notifempty
    copytruncate
    su lzt lzt
}
''')
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'start', 'lzt-minio'])
    wait_http('http://127.0.0.1:9000/minio/health/live')
    env = os.environ | {k: str(v) for k, v in config.items()}
    env.pop('OBSERVER_PROFILE_ID', None)
    run([str(BASE / 'venv/bin/python'), '-m', 'alembic', 'upgrade', 'head'], cwd=release / 'backend', env=env)
    import sys
    sys.path.insert(0, str(release / 'backend'))
    os.environ.update(env)
    from app.adapters.postgres import PostgresStore
    from app.adapters.artifacts import ArtifactStore
    from app.application.site import ensure_catalog
    from app.application.deepseek_runtime import provision
    from app.config import Config as AppConfig
    artifacts = ArtifactStore(AppConfig.from_env())
    if artifacts.bucket not in [b['Name'] for b in artifacts.client.list_buckets()['Buckets']]:
        artifacts.client.create_bucket(Bucket=artifacts.bucket)
    store = PostgresStore(config['DATABASE_URL'])
    try:
        ensure_catalog(store.engine)
        if args.mode == 'hybrid':
            from app.profiles.yolo import detectors
            detectors()
        profile_id = provision(store, hybrid=args.mode == 'hybrid', provider='deepseek')
        config['OBSERVER_PROFILE_ID'] = str(profile_id)
    finally:
        store.close()
    run(['chown', '-R', 'lzt:lzt', '/var/lib/lzt'])
    write_config(config_file, json.dumps(config, indent=2), 0o600)
    exported = {k: v for k, v in config.items() if k != 'DATABASE_PASSWORD'}
    for value in exported.values():
        if '\n' in value or '\r' in value:
            raise RuntimeError('runtime_environment_value_invalid')
    write_config(CONFIG / 'runtime.env', '\n'.join(k + '=' + json.dumps(v) for k, v in exported.items()) + '\n', 0o600)
    write_config(Path('/usr/local/sbin/lzt-keepalive'), '''#!/bin/sh
set -eu
systemctl start postgresql@17-main lzt-minio lzt-backend lzt-web
while :; do
    for service in postgresql@17-main lzt-minio lzt-backend lzt-web; do
        systemctl is-active --quiet "$service" || systemctl start "$service"
    done
    sleep 30
done
''', 0o755)
    run(['nginx', '-t', '-c', str(CONFIG / 'nginx.conf')])
    run(['systemctl', 'enable', 'postgresql@17-main', 'lzt-minio', 'lzt-backend', 'lzt-web'])
    run(['systemctl', 'restart', 'lzt-backend', 'lzt-web'])
    wait_http('http://127.0.0.1:8007/health/ready')
    wait_http('http://127.0.0.1:3000/')
    print(json.dumps({'status': 'local_ready', 'profile_id': str(profile_id),
                      'mode': args.mode, 'release': release.name, 'port': 3000}))


if __name__ == '__main__':
    main()
