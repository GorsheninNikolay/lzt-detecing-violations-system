"""Read-only video runtime verification, run as the backend service account."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-cuda', action='store_true')
    parser.add_argument('--force-cpu', action='store_true')
    parser.add_argument('--release', type=Path, default=Path('/opt/lzt/current'))
    args = parser.parse_args()
    release = args.release.resolve()
    sys.path.insert(0, str(release / 'backend'))
    import torch
    from app.application.video import video_detectors
    programs = {name: shutil.which(name) for name in ('ffmpeg', 'ffprobe')}
    if not all(programs.values()):
        raise RuntimeError('video_ffmpeg_unavailable')
    detector, evidence = video_detectors(force_cpu=args.force_cpu)
    import io
    from PIL import Image
    image = io.BytesIO()
    Image.new('RGB', (64, 64)).save(image, format='JPEG')
    prediction = detector.detect(image.getvalue(), 'runtime-check')
    if len(prediction['models']) != 2:
        raise RuntimeError('expected_two_detectors')
    driver = shutil.which('nvidia-smi')
    if not driver and Path('/usr/lib/wsl/lib/nvidia-smi').is_file():
        driver = '/usr/lib/wsl/lib/nvidia-smi'
    driver_check = subprocess.run([driver, '--query-gpu=name,driver_version', '--format=csv,noheader'],
                                  capture_output=True, text=True, timeout=15) if driver else None
    print(json.dumps({'uid': os.getuid(), 'release': str(release), 'platform': platform.platform(),
                      'tools': programs, 'cuda_available': torch.cuda.is_available(),
                      'driver': driver_check.stdout.strip() if driver_check and driver_check.returncode == 0 else None,
                      'driver_access': bool(driver_check and driver_check.returncode == 0),
                      'detectors_checked': [m['model_id'] for m in prediction['models']],
                      'device': evidence}, ensure_ascii=False))
    if args.require_cuda and evidence['actual_device'] != 'cuda:0':
        raise SystemExit('CUDA compatibility was not verified for both detectors')


if __name__ == '__main__':
    main()
