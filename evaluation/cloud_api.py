"""Isolated AI Studio image experiment; not wired into the production observer."""

import base64
import json
import time
from decimal import Decimal
from urllib import error, request


MODEL = "qwen3.6-35b-a3b"
INPUT_RUB_PER_1000 = Decimal("0.2")
CACHED_RUB_PER_1000 = Decimal("0.05")
OUTPUT_RUB_PER_1000 = Decimal("0.3")
PROMPT = (
    'Inspect this construction-site image. Mark each class true only if it is visibly present. '
    'Do not infer hidden equipment. Return the two requested booleans.'
)
RESPONSE_FORMAT = {"type": "json_schema", "name": "construction_presence", "strict": True,
                   "schema": {"type": "object", "properties": {
                       "excavator": {"type": "boolean"}, "dump_truck": {"type": "boolean"}},
                       "required": ["excavator", "dump_truck"], "additionalProperties": False}}


class CloudObserverError(RuntimeError):
    pass


def normalize_response(payload: dict, model_uri: str, latency_ms: float) -> dict:
    try:
        if payload["status"] != "completed" or payload["model"].removesuffix("/latest") != model_uri:
            raise ValueError
        output = payload.get("output_text")
        if not isinstance(output, str):
            parts = [part["text"] for item in payload["output"] if item.get("type") == "message"
                     for part in item["content"] if part.get("type") == "output_text"]
            if len(parts) != 1:
                raise ValueError
            output = parts[0]
        labels = json.loads(output)
        if set(labels) != {"excavator", "dump_truck"} or any(type(value) is not bool for value in labels.values()):
            raise ValueError
        usage = payload["usage"]
        incoming = usage.get("input_tokens", usage.get("prompt_tokens"))
        outgoing = usage.get("output_tokens", usage.get("completion_tokens"))
        details = usage.get("input_tokens_details", usage.get("prompt_tokens_details", {}))
        cached = details.get("cached_tokens", 0)
        if type(incoming) is not int or type(outgoing) is not int or incoming < 0 or outgoing < 0:
            raise ValueError
        if type(cached) is not int or not 0 <= cached <= incoming:
            raise ValueError
        response_id = payload["id"]
        if not isinstance(response_id, str) or not response_id:
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError, IndexError):
        raise CloudObserverError("observation_normalization_failed") from None
    cost = (Decimal(incoming - cached) * INPUT_RUB_PER_1000 + Decimal(cached) * CACHED_RUB_PER_1000
            + Decimal(outgoing) * OUTPUT_RUB_PER_1000) / 1000
    return {
        "response_id": response_id, "model": model_uri, "response": output,
        "states": {name: "detected" if value else "not_detected_in_frame" for name, value in labels.items()},
        "latency_ms": latency_ms,
        "usage": {"input_tokens": incoming, "cached_tokens": cached, "output_tokens": outgoing},
        "estimated_cost_rub": str(cost),
    }


def observe(image: bytes, folder_id: str, api_key: str, timeout_seconds: float = 60,
            reasoning_effort: str = "medium") -> dict:
    if reasoning_effort not in {"none", "medium"}:
        raise ValueError("unsupported_reasoning_effort")
    model_uri = f"gpt://{folder_id}/{MODEL}"
    body = json.dumps({
        "model": model_uri, "store": False, "text": {"format": RESPONSE_FORMAT},
        "reasoning": {"effort": reasoning_effort},
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": PROMPT},
            {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(image).decode(),
             "detail": "auto"},
        ]}],
    }).encode()
    http_request = request.Request(
        "https://ai.api.cloud.yandex.net/v1/responses", data=body,
        headers={"Authorization": "Api-Key " + api_key, "OpenAI-Project": folder_id,
                 "Content-Type": "application/json", "x-data-logging-enabled": "false"},
    )
    started = time.monotonic()
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            payload = json.load(response)
    except error.HTTPError as exc:
        raise CloudObserverError(f"observer_http_{exc.code}") from None
    except (TimeoutError, error.URLError):
        raise CloudObserverError("observer_timeout_or_transport_failed") from None
    except (ValueError, UnicodeError):
        raise CloudObserverError("observation_normalization_failed") from None
    result = normalize_response(payload, model_uri, (time.monotonic() - started) * 1000)
    result["reasoning_effort"] = reasoning_effort
    return result
