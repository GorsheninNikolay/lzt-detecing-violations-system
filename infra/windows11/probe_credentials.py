import json
from pathlib import Path
import sys
from urllib import request


sys.path.insert(0, '/opt/lzt/current/backend')
from app.shared.cloud import NoRedirect

config = json.loads(Path('/etc/lzt/runtime.json').read_text())
req = request.Request('https://api.deepseek.com/user/balance',
                      headers={'Authorization': 'Bearer ' + config['DEEPSEEK_API_KEY']})
with request.build_opener(NoRedirect).open(req, timeout=30) as response:
    data = json.load(response)
print(json.dumps({'authorized': True, 'is_available': data.get('is_available'),
                  'balances': [{'currency': b.get('currency'), 'total_balance': b.get('total_balance')}
                               for b in data.get('balance_infos', [])]}))
