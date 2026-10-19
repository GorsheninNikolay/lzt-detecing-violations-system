import grp
import json
import os
from pathlib import Path

root = Path('/opt/lzt/current/backend/admission')
backup = Path('/mnt/c/ProgramData/LztEvidence/backups/admission-permission-metadata.json')
files = list(root.rglob('*.json'))
if not backup.exists():
    backup.write_text(json.dumps({str(p): {'mode': p.stat().st_mode & 0o777, 'uid': p.stat().st_uid, 'gid': p.stat().st_gid} for p in files}, indent=2))
for p in files:
    os.chown(p, 0, grp.getgrnam('lzt').gr_gid)
    p.chmod(0o640)
print(json.dumps({'normalized_files': len(files)}))
