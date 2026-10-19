"""Reset only LztEvidence's active data after verifying a protected backup."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from setup_app import CONFIG, WINDOWS, sql


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--operation', required=True)
    parser.add_argument('--confirm', choices=['RESET_LZT_EVIDENCE'], required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9_]{1,35}', args.operation):
        raise RuntimeError('invalid_operation_id')
    backup = args.backup.resolve()
    if not backup.is_relative_to((WINDOWS / 'backups').resolve()):
        raise RuntimeError('protected_backup_required')
    manifest = json.loads((backup / 'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        item = (backup / name).resolve()
        if not item.is_relative_to(backup) or hashlib.file_digest(item.open('rb'), 'sha256').hexdigest() != digest:
            raise RuntimeError('backup_checksum_mismatch')
    subprocess.run(['pg_restore', '--list', str(backup / 'database.dump')], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    config = json.loads((CONFIG / 'runtime.json').read_text())
    if not config['DATABASE_URL'].endswith('/lzt_evidence') or config['S3_BUCKET'] != 'lzt-evidence':
        raise RuntimeError('unexpected_active_data_target')
    journal = WINDOWS / 'backups' / ('reset-' + args.operation + '.json')
    retired_db = 'lzt_retired_' + args.operation
    retired_storage = Path('/var/backups/lzt/retired-storage') / args.operation
    if journal.exists():
        state = json.loads(journal.read_text())
        if state.get('status') == 'complete':
            print(json.dumps(state))
            return
        raise RuntimeError('incomplete_reset_requires_journal_reconciliation')
    state = {'operation': args.operation, 'backup': str(backup), 'retired_database': retired_db,
             'retired_storage': str(retired_storage), 'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'starting'}
    journal.write_text(json.dumps(state, indent=2))
    subprocess.run(['systemctl', 'stop', 'lzt-web', 'lzt-backend', 'lzt-minio'], check=True)
    sql("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='lzt_evidence' AND pid<>pg_backend_pid();")
    sql('ALTER DATABASE lzt_evidence RENAME TO ' + retired_db + ';')
    state['status'] = 'database_archived'
    journal.write_text(json.dumps(state, indent=2))
    retired_storage.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    storage = Path('/var/lib/lzt/artifacts')
    if retired_storage.exists():
        raise RuntimeError('retired_storage_already_exists')
    shutil.move(str(storage), str(retired_storage))
    storage.mkdir(mode=0o700)
    shutil.chown(storage, user='lzt', group='lzt')
    sql("CREATE DATABASE lzt_evidence OWNER lzt_evidence ENCODING 'UTF8' LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8' TEMPLATE template0;")
    state['status'] = 'complete'
    journal.write_text(json.dumps(state, indent=2))
    print(json.dumps(state))


if __name__ == '__main__':
    main()
