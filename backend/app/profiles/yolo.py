"""Pinned, serialized CPU detectors over the same oriented pixels as DeepSeek."""
import io
import json
import os
import threading
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from time import monotonic

from PIL import Image

from app.profiles.deepseek import oriented_image
from app.shared.cloud import digest

MANIFEST_PATH = Path(__file__).resolve().parents[1] / 'data' / 'yolo-manifest.json'
_LOCK = threading.Lock()


def manifest():
    return json.loads(MANIFEST_PATH.read_text())


class Detectors:
    def __init__(self):
        self.manifest = manifest()
        for package, required in self.manifest['dependencies'].items():
            if version(package).split('+')[0] != required:
                raise ValueError('detector_dependency_mismatch')
        root = Path(os.environ.get('YOLO_MODELS_DIR', str(Path(__file__).resolve().parents[3] / 'artifacts' / 'Models')))
        for model in self.manifest['models']:
            path = root / model['filename']
            if not path.is_file() or digest(path.read_bytes()) != model['sha256']:
                raise ValueError('detector_weights_invalid')
        from ultralytics import YOLO
        self.models = []
        for model in self.manifest['models']:
            detector = YOLO(str(root / model['filename']), task='detect')
            if [detector.names[i] for i in range(len(detector.names))] != model['classes']:
                raise ValueError('detector_classes_mismatch')
            detector.to('cpu')
            self.models.append((model, detector))

    def detect(self, payload, input_id):
        oriented, _, dimensions = oriented_image(payload)
        result = []
        with _LOCK, Image.open(io.BytesIO(oriented)) as image:
            for model, detector in self.models:
                started = monotonic()
                prediction = detector.predict(image, **self.manifest['settings'])[0]
                detections = []
                for i, box in enumerate(prediction.boxes):
                    class_id = int(box.cls.item())
                    raw_name = model['classes'][class_id]
                    bounds = box.xyxyn[0].tolist()
                    score = float(box.conf.item())
                    if not (0 <= score <= 1 and len(bounds) == 4 and all(0 <= v <= 1 for v in bounds)
                            and bounds[0] < bounds[2] and bounds[1] < bounds[3]):
                        raise ValueError('detector_output_invalid')
                    detections.append({'id': f'{input_id}/{model["id"]}/{i}', 'input_id': str(input_id),
                                       'model_id': model['id'], 'class_id': class_id, 'raw_class': raw_name,
                                       'catalog_class': model['mapping'][raw_name], 'score': score, 'box': bounds})
                result.append({'model_id': model['id'], 'weights_sha256': model['sha256'],
                               'image_size': dimensions, 'latency_ms': (monotonic() - started) * 1000,
                               'detections': detections})
        return {'manifest': self.manifest, 'oriented_sha256': digest(oriented), 'models': result}


@lru_cache(maxsize=1)
def detectors():
    return Detectors()
