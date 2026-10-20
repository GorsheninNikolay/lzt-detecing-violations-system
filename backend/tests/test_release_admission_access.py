import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tarfile
import subprocess
import sys

import pytest


@pytest.fixture
def installer(monkeypatch, tmp_path):
    source = Path(__file__).resolve().parents[2] / 'infra/windows11/setup_app.py'
    spec = importlib.util.spec_from_file_location('lzt_setup_test', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'BASE', tmp_path / 'app')
    monkeypatch.setattr(module, 'WINDOWS', tmp_path / 'windows')
    module.WINDOWS.mkdir()
    monkeypatch.setattr(module.grp, 'getgrnam', lambda name: SimpleNamespace(gr_gid=123))
    monkeypatch.setattr(module.os, 'chown', lambda *args: None)
    return module


@pytest.mark.parametrize('service_can_read', [False, True])
def test_release_checks_service_access_before_switching(installer, tmp_path, monkeypatch, service_can_read):
    source = tmp_path / 'source'
    inventory = source / 'backend/admission/exclusions/held_out_evaluation.json'
    inventory.parent.mkdir(parents=True)
    inventory.write_text('{"fixtures": []}' if service_can_read else 'corrupt')
    inventory.chmod(0o600)
    manifest = source / 'backend/admission/manifest.json'
    manifest.write_text('{"fixtures": []}')
    entries = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (inventory, manifest)}
    release_manifest = source / 'release.json'
    release_manifest.write_text(json.dumps({'source_tree_sha256': 'a' * 64, 'files': entries}))
    archive = tmp_path / 'release.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for path in (inventory, manifest, release_manifest):
            bundle.add(path, arcname=str(path.relative_to(source)))
    installer.BASE.mkdir()
    old = installer.BASE / 'previous'
    old.mkdir()
    current = installer.BASE / 'current'
    current.symlink_to(old)
    (installer.WINDOWS / 'current.txt').write_text('previous\n')
    checks = []

    def check(command):
        assert current.resolve() == old
        assert command[:6] == ['runuser', '-u', 'lzt', '--', '/usr/bin/python3', '-c']
        admission = Path(command[-1])
        assert (admission / 'exclusions/held_out_evaluation.json').stat().st_mode & 0o777 == 0o640
        assert admission.stat().st_mode & 0o777 == 0o750
        checks.append(True)
        subprocess.run([sys.executable, *command[5:]], check=True, capture_output=True)

    monkeypatch.setattr(installer, 'run', check)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if service_can_read:
        result = installer.unpack_release(archive, digest)
        assert current.resolve() == result.resolve()
        assert (installer.WINDOWS / 'current.txt').read_text() == 'a' * 16 + '\n'
    else:
        with pytest.raises(subprocess.CalledProcessError):
            installer.unpack_release(archive, digest)
        assert current.resolve() == old
        assert (installer.WINDOWS / 'current.txt').read_text() == 'previous\n'
    assert checks == [True]
