from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess


for directory in ('ultralytics/Ultralytics', 'matplotlib'):
    target = Path('/var/lib/lzt') / directory
    target.mkdir(parents=True, exist_ok=True)
subprocess.run(['chown', '-R', 'lzt:lzt', '/var/lib/lzt'], check=True)
config = Path('/etc/lzt/nginx.conf')
text = config.read_text()
if 'charset utf-8;' not in text:
    backup = Path('/var/backups/lzt/config')
    backup.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    shutil.copy2(config, backup / (stamp + '-nginx.conf'))
    config.write_text(text.replace('http {', 'http {\n    charset utf-8;\n    charset_types application/json application/javascript text/css;'))
subprocess.run(['nginx', '-t', '-c', str(config)], check=True)
subprocess.run(['systemctl', 'restart', 'lzt-web'], check=True)
for path in Path('/var/log/lzt').glob('*.log'):
    shutil.chown(path, user='lzt', group='lzt')
print('Owned runtime directories, UTF-8 HTTP and log permissions verified')
