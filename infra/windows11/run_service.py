import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import subprocess


base = Path(__file__).resolve().parent.parent
handler = RotatingFileHandler(base / 'logs/wsl-supervisor.log', maxBytes=5_000_000, backupCount=3,
                              encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[handler])
logging.info('Starting isolated LztEvidence WSL runtime')
with subprocess.Popen(['C:\\Windows\\System32\\wsl.exe', '-d', 'LztEvidence', '-u', 'root', '--',
                       '/usr/local/sbin/lzt-keepalive'], stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT) as child:
    for line in child.stdout:
        logging.info('%s', line.decode('utf-8', errors='replace').replace('\x00', '').rstrip())
    result = child.wait()
logging.error('WSL supervisor exited with code %s', result)
raise SystemExit(1)
