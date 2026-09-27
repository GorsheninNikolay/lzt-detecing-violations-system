"""Optional local experiment cap, shared by every process using the same ledger."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

UPPER_RUB = Decimal('318.6688')
CAP_RUB = Decimal('1000')
BASELINE_PATH = Path(__file__).resolve().parents[3] / 'evaluation/hybrid/history/cba5bbcdac16c41845cd55e29d9c52c9a987640d2e6d1cb5f6c374054e9d0256/budget.json'
if not BASELINE_PATH.is_file():
    BASELINE_PATH = Path(__file__).resolve().parents[3] / 'evaluation/hybrid/budget.json'
BASELINE_SHA256 = 'bc304775ec4e831c0f69b5cff9fd94a8690cffaae900e2efb9e8b6383f9d117d'


def verify_history(ledger):
    raw = BASELINE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASELINE_SHA256:
        raise ValueError('quality_budget_history_invalid')
    historical = json.loads(raw)
    calls = {row['id']: row for row in ledger['calls']}
    if len(calls) != len(ledger['calls']) or any(calls.get(row['id']) != row for row in historical['calls']):
        raise ValueError('historical_budget_exposure_missing')


def money(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('quality_budget_invalid')
    return result


@contextmanager
def locked(path):
    path = Path(path).resolve()
    with path.with_suffix(path.suffix + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger = json.loads(path.read_text())
        if money(ledger['limit_rub']) != CAP_RUB or not isinstance(ledger['calls'], list):
            raise ValueError('quality_budget_invalid')
        verify_history(ledger)
        yield ledger


def exposure(ledger):
    total = Decimal(0)
    for call in ledger['calls']:
        upper = money(call['upper_rub'])
        if upper != UPPER_RUB:
            raise ValueError('quality_budget_invalid')
        actual = call.get('actual_estimate_rub')
        if actual is not None:
            actual = money(actual).quantize(Decimal('0.0000001'))
            if actual > upper:
                raise ValueError('quality_budget_invalid')
        total += upper if actual is None else actual
    return total


def persist(path, ledger):
    path = Path(path).resolve()
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.budget-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(ledger, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def reserve(path, purpose, request_sha256):
    with locked(path) as ledger:
        if exposure(ledger) + UPPER_RUB > CAP_RUB:
            raise ValueError('quality_budget_exhausted')
        identity = str(uuid.uuid4())
        ledger['calls'].append({'id': identity, 'purpose': purpose, 'request_sha256': request_sha256,
                                'upper_rub': str(UPPER_RUB), 'status': 'reserved_or_uncertain',
                                'at': datetime.now(timezone.utc).isoformat()})
        persist(path, ledger)
    return identity


def settle(path, identity, usage, response_id=None):
    incoming, outgoing = usage['input_tokens'], usage['output_tokens']
    if (type(incoming) is not int or type(outgoing) is not int
            or not 0 <= incoming <= 1048576 or not 0 <= outgoing <= 8192):
        raise ValueError('quality_budget_usage_invalid')
    actual = (Decimal(incoming) * Decimal('0.3') + Decimal(outgoing) * Decimal('0.5')) / 1000
    with locked(path) as ledger:
        rows = [row for row in ledger['calls'] if row['id'] == identity]
        if len(rows) != 1 or rows[0]['status'] != 'reserved_or_uncertain' or actual > money(rows[0]['upper_rub']):
            raise ValueError('quality_budget_settlement_invalid')
        rows[0].update(status='received_usage', usage=usage, actual_estimate_rub=str(actual))
        if isinstance(response_id, str) and response_id.strip():
            rows[0]['response_id'] = response_id
        persist(path, ledger)


def status(path):
    with locked(path) as ledger:
        used = exposure(ledger)
        return {'configured': True, 'limit_rub': str(CAP_RUB), 'exposure_rub': format(used.normalize(), 'f'),
                'remaining_rub': str(max(Decimal(0), CAP_RUB - used)), 'next_call_upper_rub': str(UPPER_RUB),
                'can_reserve': used + UPPER_RUB <= CAP_RUB}
