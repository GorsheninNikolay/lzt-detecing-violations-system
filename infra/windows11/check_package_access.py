import json
import os
from pathlib import Path


root = Path('/opt/lzt/current/backend/admission')
print(json.dumps({'uid': os.getuid(), 'files': [{'path': str(p), 'mode': oct(p.stat().st_mode & 0o777),
                  'readable': os.access(p, os.R_OK)} for p in root.rglob('*.json')]}))
