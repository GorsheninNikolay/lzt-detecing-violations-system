"""Extract the source-bound review queue without changing organizer originals."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


def prepare(archive, output):
    directory = Path(__file__).resolve().parent
    manifest = json.loads((directory / 'control-review-queue.json').read_text())
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != manifest['archive_sha256']:
            raise ValueError('source_archive_hash_mismatch')
    output.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as source:
        for row in manifest['images']:
            payload = source.read(row['archive_member'])
            if hashlib.sha256(payload).hexdigest() != row['sha256']:
                raise ValueError('source_image_hash_mismatch')
            target = output / Path(row['archive_member']).name
            if target.exists() and target.read_bytes() != payload:
                raise ValueError('refusing_to_replace_different_image')
            target.write_bytes(payload)
    print(json.dumps({'status': 'review_queue_not_ground_truth', 'images': len(manifest['images']), 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.archive, args.output)
