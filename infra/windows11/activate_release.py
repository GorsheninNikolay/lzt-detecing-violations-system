import argparse
from datetime import datetime, timezone
import grp
import json
import os
from pathlib import Path
import shutil
import subprocess

from setup_app import unpack_release

parser = argparse.ArgumentParser()
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--sha256', required=True)
args = parser.parse_args()
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup = Path('/mnt/c/ProgramData/LztEvidence/backups') / ('release-switch-' + stamp)
backup.mkdir(mode=0o700)
(backup / 'previous-link.txt').write_text(os.readlink('/opt/lzt/current'))
shutil.copy2('/mnt/c/ProgramData/LztEvidence/current.txt', backup / 'current.txt')
subprocess.run(['systemctl', 'stop', 'lzt-web', 'lzt-backend'], check=True)
try:
    release = unpack_release(args.archive, args.sha256)
    for path in (release / 'backend/admission').rglob('*.json'):
        os.chown(path, 0, grp.getgrnam('lzt').gr_gid)
        path.chmod(0o640)
    print(json.dumps({'release': str(release), 'previous_release_backup': str(backup)}))
finally:
    subprocess.run(['systemctl', 'start', 'lzt-backend', 'lzt-web'], check=True)
