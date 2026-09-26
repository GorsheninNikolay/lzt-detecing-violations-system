"""Portable dataset integrity checks, shared by packaging and training."""
import hashlib
import io
import json
import math
from pathlib import Path
from PIL import Image

TOLERANCE = 1e-6

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def labels(data, classes):
    result = []
    for line in data.decode('utf-8-sig').splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError('label_field_count')
        c = int(fields[0])
        x, y, w, h = map(float, fields[1:])
        if not 0 <= c < classes:
            raise ValueError('class_out_of_bounds')
        if not all(math.isfinite(v) for v in (x, y, w, h)):
            raise ValueError('nonfinite_box')
        if w <= 0 or h <= 0:
            raise ValueError('nonpositive_box')
        if min(x-w/2, y-h/2) < -TOLERANCE or max(x+w/2, y+h/2) > 1+TOLERANCE:
            raise ValueError('box_out_of_bounds')
        result.append((c, x, y, w, h))
    return result

def image_info(data, expected=None):
    with Image.open(io.BytesIO(data)) as im:
        if im.getexif().get(274, 1) != 1:
            raise ValueError('exif_orientation_requires_rotation')
        if expected is not None and tuple(expected) != im.size:
            raise ValueError('image_dimensions_mismatch')
        im.load()
        size = im.size
        pixel_hash = sha(str(size).encode() + im.convert('RGB').tobytes())
        return size, pixel_hash

def load_manifest(root, profile):
    root = Path(root)
    index = json.loads((root/'manifest-index.json').read_text())
    for rel, expected in index.items():
        if file_sha(root/rel) != expected:
            raise ValueError('manifest_or_metadata_tampered: ' + rel)
    return json.loads((root/'manifests'/f'{profile}.json').read_text())

def selection(rows, mode):
    if mode == 'full':
        return rows
    sizes = {'smoke': {'train': 8, 'val': 4}, 'pilot': {'train': 256, 'val': 64}}[mode]
    chosen = []
    for split, limit in sizes.items():
        candidates = [r for r in rows if r['split'] == split]
        # Prefer examples of each class before filling the deterministic subset.
        seen = set()
        selected = []
        for row in candidates:
            classes = set(map(int, row['class_boxes']))
            if classes - seen and len(selected) < limit:
                selected.append(row)
                seen.update(classes)
        keys = {r['image'] for r in selected}
        selected.extend(r for r in candidates if r['image'] not in keys)
        chosen.extend(selected[:limit])
    return chosen

def verify(root, profile, mode='full'):
    root = Path(root)
    manifest = load_manifest(root, profile)
    rows = selection(manifest['pairs'], mode)
    if not all(any(r['split'] == s for r in rows) for s in ('train', 'val')):
        raise ValueError('empty_train_or_val')
    for row in rows:
        sidecar = (root/row['image']).with_suffix('.npy')
        if sidecar.exists() or sidecar.is_symlink():
            raise ValueError('unverified_image_sidecar: ' + str(sidecar))
        for key in ('image', 'label'):
            if file_sha(root/row[key]) != row[key+'_sha256']:
                raise ValueError('pair_tampered: ' + row[key])
        boxes = labels((root/row['label']).read_bytes(), len(manifest['names']))
        if len(boxes) != row['box_count']:
            raise ValueError('box_count_mismatch')
        image_info((root/row['image']).read_bytes(), row['dimensions'])
    return manifest, rows


def backup_label_caches(root, rows, run_name):
    root = Path(root)
    backups = []
    caches = {(root/r['label']).parent.with_suffix('.cache') for r in rows if r['split'] in ('train', 'val')}
    for cache in sorted(caches):
        if cache.exists() or cache.is_symlink():
            destination = root/'runtime'/'cache-backups'/run_name/cache.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise FileExistsError(destination)
            digest = file_sha(cache)
            cache.rename(destination)
            backups.append(dict(source=str(cache), backup=str(destination), sha256=digest))
    return backups
