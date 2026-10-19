import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cloud-only', action='store_true')
    parser.add_argument('--models-dir', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    tracked = subprocess.check_output(['git', 'ls-files', 'backend'], cwd=root).decode().splitlines()
    files = [root / name for name in tracked if (
        name.startswith(('backend/app/', 'backend/migrations/', 'backend/admission/'))
        and Path(name).suffix in ('.py', '.json', '.md')) or name in (
            'backend/pyproject.toml', 'backend/uv.lock', 'backend/alembic.ini')]
    files = [p for p in files if p.name != 'hybrid-readiness.json']
    files += [p for p in (root / 'web/dist').rglob('*') if p.is_file()]
    catalog = list((root / 'artifacts/dataset').glob('Свод*.xlsx'))
    if len(catalog) != 1:
        raise RuntimeError('Expected one source work catalog')
    files += catalog
    files += [p for p in (root / 'shared/trial-project').rglob('*') if p.is_file() and p.suffix in ('.json', '.jpg', '.png', '.webp')]
    required = {root / 'backend/app/data/assistant-plan-guide.ru.md', root / 'shared/trial-project/manifest.json'}
    if not required.issubset(set(files)):
        raise RuntimeError('Required assistant/trial assets missing from release')
    sources = {str(path.relative_to(root)): path for path in files}
    if not args.cloud_only:
        detector_manifest = json.loads((root / 'backend/app/data/yolo-manifest.json').read_text())
        for model in detector_manifest['models']:
            path = (args.models_dir or root / 'artifacts/Models') / model['filename']
            actual = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
            if actual != model['sha256']:
                raise RuntimeError('Detector digest mismatch')
            sources['artifacts/Models/' + model['filename']] = path
    entries = {}
    for name, path in sorted(sources.items()):
        if path.is_symlink():
            raise RuntimeError('Release symlink rejected')
        entries[name] = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
    tree_hash = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()
    manifest = {'source_tree_sha256': tree_hash, 'files': entries,
                'baseline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip(),
                'dirty_source': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root)),
                'user_database_or_uploads_included': False, 'hybrid_models_included': not args.cloud_only}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        manifest_file = Path(temporary) / 'release.json'
        manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        with tarfile.open(args.output, 'w:gz') as archive:
            for name in entries:
                archive.add(sources[name], arcname=name, recursive=False)
            archive.add(manifest_file, arcname='release.json')
    print(json.dumps({'archive': str(args.output), 'files': len(entries),
                      'source_tree_sha256': tree_hash,
                      'archive_sha256': hashlib.file_digest(args.output.open('rb'), 'sha256').hexdigest()}))


if __name__ == '__main__':
    main()
