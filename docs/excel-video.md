# Excel plans and video analysis

The plan editor accepts `.xlsx` through selection or drag and drop. Download the
empty template or the filled tutorial example for the selected area. The first
sheet uses `Работа`, `Начало`, `Окончание` followed by optional state, stage and
equipment columns. The reference sheet lists current work IDs and supported
values. Use an ID when several catalog works have the same title. Equipment
values are separated by semicolons. Formulas are rejected rather than evaluated.

Preview is read-only. Any row error blocks replacement. Confirm `Заменить план`
to use the existing optimistic revision API; a stale revision returns a conflict.
Date-only start/end values mean the start/end of that day in the project's time
zone. Existing revisions and analysis bindings remain intact. The tutorial plan
step finishes only after the newly saved revision is read back.

Video upload accepts one MP4/MOV, at most 200,000,000 bytes and 120 seconds, with
H.264/H.265, up to 4096×2160 (or rotated), and at most 60 FPS. Validation occurs
before inference. FFmpeg/ffprobe must be installed. All decoded frames are sent
to both YOLO detectors; up to eight selected frames are sent to the configured
DeepSeek provider. Image input follows the [DeepSeek Responses API](https://api-docs.deepseek.com/guides/responses_api/).
No audio is sent to the provider. The output is H.264 MP4 up to 1280×720 with
retained audio, annotated with distinct detector labels. Relative timestamps
remain available without a known shooting start. Plan comparisons require a
confirmed start with timezone. Cloud explanations only concern sampled moments.

Video jobs and cloud call reservations are persisted in migrations `0027_video`
and `0028_video_authorization`. Every new paid reservation rechecks the stored
authorization revision; a CPU retry has one durable successor.
An unknown external call outcome must never be retried automatically. Completed
YOLO video remains accessible even when cloud explanation fails. Download and
playback use an authenticated endpoint with byte Range support. Existing photo
contracts remain unchanged; project history includes video jobs.

## Runtime and GPU verification

The standard Docker image and Windows bootstrap install FFmpeg. Existing hosts
need FFmpeg installed before activation. The standard Linux Python lock selects
CPU PyTorch. Do not assume a CUDA-capable GPU or install a different wheel
blindly. First inspect the Windows GPU/driver and WSL `nvidia-smi`, then choose a
compatible PyTorch CUDA build for the fixed torch/torchvision versions on that
host. Driver installation is a separate host operation.

Run the read-only probe with the actual service account and configured models:

```sh
sudo -u lzt env PYTHONPATH=/opt/lzt/current/backend \
  YOLO_MODELS_DIR=/opt/lzt/current/artifacts/Models \
  /opt/lzt/venv/bin/python /path/to/probe_video_runtime.py --require-cuda
```

The probe records the driver, actual execution device, package/CUDA versions and
weight hashes, and executes both models. Without `--require-cuda`, it accepts a
verified CPU fallback and records its warning. Each job records its own actual
device. GPU failure during inference stops that job; an explicit CPU successor
is available before any cloud reservation. It does not retry a paid call.

## Release

Preserve the existing URL `https://nikolay.tailaf11dc.ts.net:8443/`. Follow the
Windows deployment instructions: take and verify `backup_app.py`, package the
committed source and built assets, verify archive and release hashes, apply the
additive migration, switch the immutable release, and check readiness, existing
accounts/projects/files plus authenticated playback. Never run `reset_app.py`.
Do not treat a successful local test or package as deployment evidence.

On 2026-10-20, the initial SSH preflight timed out. Access subsequently returned;
the host reports an RTX 3060 through WSL and driver 610.88. The original Python
environment is CPU-only. Runtime and deployment acceptance are recorded separately
from local verification.

## Local verification, 2026-10-20

- Web: 307 passed, one timezone-specific test skipped in the normal full run;
  the separate Europe/Berlin video/time suite passed all 10 tests. Production
  build passed. IndexedDB tests exercise the actual recovery module, including
  File bytes and concurrent tabs.
- Backend: the broad isolated PostgreSQL/Moto run had 548 passes, one skip and
  three S3 reconciliation failures. The same three failures reproduced on the
  pristine starting commit in another isolated database using the same emulator.
  They do not establish compatibility with real MinIO and are retained as evidence.
- Final video suite: 29 passed with both real CPU YOLO detectors. Includes MOV
  rotation, VFR, audio offset verified by decoded frequency, silent trailing-frame
  duration, current authorization, concurrent CPU retries and immutable plan times.
- Excel parser: nine tests passed, including numeric date formats, explicit
  midnight, optional row/cell addresses and corrupt compressed XML. Database/API
  checks cover access, revision conflicts and atomic replacement.
- The resumable deployment acceptance CLI has two offline tests; its receipt
  contains private test credentials and must not be published.

CUDA packages use the fixed torch 2.10.0 / torchvision 0.25.0 versions from the
[official PyTorch installation matrix](https://pytorch.org/get-started/previous-versions/).
The original CPU virtual environment is preserved when preparing a separate CUDA
environment; do not replace the service interpreter before both model checks pass.
