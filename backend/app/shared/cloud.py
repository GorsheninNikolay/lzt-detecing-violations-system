"""Bounded JSON transport and canonical content identities."""
import hashlib
import json
import math
import time
from urllib import error, request

MAX_RESPONSE_BYTES = 262144

class CloudObserverError(RuntimeError):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CloudObserverError("observer_redirect_rejected")


def strict_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("nonfinite_json")
    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite_json")
        return parsed
    return json.loads(data, object_pairs_hook=unique, parse_constant=nonfinite, parse_float=finite_float)

def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()

def _read_json(http_request: request.Request, seconds: float) -> dict:
    started = time.monotonic()
    try:
        with request.build_opener(NoRedirect).open(http_request, timeout=seconds) as response:
            chunks = bytearray()
            while True:
                remaining = seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise CloudObserverError("observer_timeout")
                socket = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
                if socket is not None:
                    socket.settimeout(remaining)
                chunk = response.read(min(8192, MAX_RESPONSE_BYTES + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE_BYTES:
                    raise CloudObserverError("observer_response_too_large")
            if time.monotonic() - started > seconds:
                raise CloudObserverError("observer_timeout")
            payload = strict_json(chunks)
            if not isinstance(payload, dict):
                raise ValueError
            return payload
    except error.HTTPError as exc:
        raise CloudObserverError("observer_quota_failed" if exc.code == 429 else
                                 "observer_access_failed" if exc.code in (401, 403) else
                                 "observer_http_failed") from None
    except error.URLError as exc:
        raise CloudObserverError("observer_timeout" if isinstance(exc.reason, TimeoutError)
                                 else "observer_transport_failed") from None
    except (TimeoutError, OSError) as exc:
        raise CloudObserverError("observer_timeout" if isinstance(exc, TimeoutError)
                                 else "observer_transport_failed") from None
    except (ValueError, UnicodeError):
        raise CloudObserverError("observation_normalization_failed") from None
