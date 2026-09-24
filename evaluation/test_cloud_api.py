import json
from urllib import error

import pytest

from cloud_api import CloudObserverError, normalize_response, observe


MODEL = "gpt://folder/qwen3.6-35b-a3b"


def test_closed_states_usage_and_cost():
    result = normalize_response({
        "id": "response-1", "status": "completed", "model": MODEL,
        "output_text": '{"excavator":true,"dump_truck":false}',
        "usage": {"input_tokens": 1500, "output_tokens": 100},
    }, MODEL, 125)
    assert result["states"] == {"excavator": "detected", "dump_truck": "not_detected_in_frame"}
    assert result["estimated_cost_rub"] == "0.33"


def test_invalid_response_is_terminal():
    with pytest.raises(CloudObserverError, match="observation_normalization_failed"):
        normalize_response({"id": "response-1", "status": "completed", "model": MODEL,
            "output_text": '{"excavator":"yes","dump_truck":false}',
            "usage": {"input_tokens": 1, "output_tokens": 1}}, MODEL, 1)


def test_timeout_is_terminal_without_leaking_key(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise error.URLError(TimeoutError("secret key never goes here"))

    monkeypatch.setattr("cloud_api.request.urlopen", timeout)
    with pytest.raises(CloudObserverError, match="observer_timeout_or_transport_failed") as exc:
        observe(b"image", "folder", "secret-key")
    assert "secret-key" not in str(exc.value)
