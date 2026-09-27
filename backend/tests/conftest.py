import json
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def synthetic_diagnostic_reservations(request, tmp_path, monkeypatch):
    if request.module.__name__ not in {
        'test_hybrid_readiness', 'test_hybrid_quality_components', 'test_hybrid_control_runner',
    }:
        return
    from app.application import hybrid_readiness
    from app.shared.cloud import digest
    queue = Path(__file__).resolve().parents[2] / 'evaluation/hybrid/control-review-queue.json'
    frames = []
    for index, row in enumerate(json.loads(queue.read_text())['images']):
        image = Image.new('RGB', (16, 16), (200 + index, 202, 203))
        if index == 0:
            image.save(tmp_path / 'diagnostic-original.png')
        frames.append({'id': row['id'], 'sha256': row['sha256'],
                       'rgb_sha256': digest(str(image.size).encode() + image.tobytes())})
    path = tmp_path / 'diagnostic-reservations.json'
    path.write_text(json.dumps({'frames': frames}))
    monkeypatch.setattr(hybrid_readiness, 'DIAGNOSTIC_RESERVATIONS_PATH', path)
