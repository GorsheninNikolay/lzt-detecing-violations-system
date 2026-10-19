import logging
from logging.handlers import RotatingFileHandler

import uvicorn


handler = RotatingFileHandler('/var/log/lzt/backend.log', maxBytes=5_000_000, backupCount=3)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[handler])
uvicorn.run('app.main:app', host='127.0.0.1', port=8007, log_config=None,
            proxy_headers=True, forwarded_allow_ips='127.0.0.1')
