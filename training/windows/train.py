#!/usr/bin/env python3
"""Train either independently namespaced detector from verified local pairs."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import shutil
from integrity import verify, file_sha, backup_label_caches

ROOT = Path(__file__).resolve().parent

def preserve_resume_best(root, profile, mode, checkpoint, run, load_checkpoint):
    checkpoint = checkpoint.resolve()
    if checkpoint.name != 'last.pt' or checkpoint.parent.name != 'weights':
        raise ValueError('resume requires a run/weights/last.pt checkpoint')
    previous = checkpoint.parent.parent
    invocation = previous/'invocation.json'
    saved = json.loads(invocation.read_text())
    if saved['profile'] != profile or saved['mode'] != mode or saved['manifest_sha256'] != file_sha(root/'manifests'/f'{profile}.json'):
        raise ValueError('resume dataset/profile/mode mismatch')
    best = checkpoint.with_name('best.pt')
    if not best.is_file():
        raise FileNotFoundError('resume requires predecessor best.pt: ' + str(best))
    last_args = load_checkpoint(checkpoint)['train_args']
    if last_args.get('name') != saved['config']['name'] or last_args.get('data') != saved['config']['data']:
        raise ValueError('resume checkpoint does not belong to predecessor invocation')
    best_digest = file_sha(best)
    inherited = (saved.get('resume_provenance') or {}).get('best_sha256') == best_digest
    if not inherited:
        best_args = load_checkpoint(best)['train_args']
        if any(best_args.get(k) != last_args.get(k) for k in ('name', 'project', 'data')):
            raise ValueError('best.pt does not belong to predecessor run')
    destination = run/'weights'/'best.pt'
    destination.parent.mkdir(exist_ok=True)
    with best.open('rb') as source, destination.open('xb') as target:
        shutil.copyfileobj(source, target)
    return dict(last_source=str(checkpoint), last_sha256=file_sha(checkpoint), best_source=str(best), best_sha256=best_digest, invocation_sha256=file_sha(invocation), inherited_best=inherited)


def checkpoint_results(run):
    checkpoints = {p.name:file_sha(p) for p in (run/'weights').glob('*.pt')}
    if not {'best.pt', 'last.pt'} <= checkpoints.keys():
        raise RuntimeError('training returned without expected best.pt and last.pt')
    return checkpoints


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=['kaggle','apoce'], required=True)
    parser.add_argument('--mode', choices=['smoke','pilot','full'], default='full')
    parser.add_argument('--device', choices=['cuda','mps','cpu'], default='cuda')
    parser.add_argument('--name', default=None)
    parser.add_argument('--resume', type=Path, help='Explicit last.pt from an interrupted run of this kit')
    args = parser.parse_args()
    runtime = ROOT/'runtime'
    runtime.mkdir(exist_ok=True)
    os.environ['YOLO_CONFIG_DIR'] = str(runtime/'ultralytics-settings')
    os.environ['YOLO_OFFLINE'] = 'true'
    import torch
    from ultralytics import YOLO, settings
    settings.update({k:False for k in ('sync','clearml','comet','mlflow','wandb')})
    if args.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable. Install a compatible NVIDIA driver and run setup_windows.cmd; CPU fallback is disabled.')
    if args.device == 'mps' and not torch.backends.mps.is_available():
        raise RuntimeError('MPS unavailable')
    check = float((torch.ones(16,device=args.device)*3).sum().item())
    if check != 48:
        raise RuntimeError('device arithmetic check failed')
    manifest, rows = verify(ROOT,args.profile,args.mode)
    name = args.name or f'{args.profile}-{args.mode}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}'
    if Path(name).name != name or name in ('.','..') or any(c in name for c in '\\/:'):
        raise ValueError('run name must be one safe directory name')
    run = runtime/'runs'/name
    run.mkdir(parents=True,exist_ok=False)
    config_dir = run/'inputs'
    config_dir.mkdir()
    for split in ('train','val'):
        (config_dir/f'{split}.txt').write_text(''.join(str((ROOT/r['image']).resolve())+'\n' for r in rows if r['split']==split),encoding='utf-8')
    data = config_dir/'data.yaml'
    # JSON strings and arrays are also valid YAML scalars and sequences.
    data.write_text('path: '+json.dumps(str(ROOT))+'\ntrain: '+json.dumps(str(config_dir/'train.txt'))+'\nval: '+json.dumps(str(config_dir/'val.txt'))+'\nnames: '+json.dumps(manifest['names'])+'\n',encoding='utf-8')
    weights = ROOT/'models'/'yolo26s.pt'
    if not weights.is_file(): raise FileNotFoundError(weights)
    resume_provenance = None
    if args.resume:
        resume_provenance = preserve_resume_best(ROOT, args.profile, args.mode, args.resume, run, lambda path: torch.load(path, map_location='cpu', weights_only=False))
        model = YOLO(str(args.resume.resolve()))
    else:
        model = YOLO(str(weights))
    cache_backups = backup_label_caches(ROOT, rows, run.name)
    options = dict(data=str(data),epochs={'smoke':1,'pilot':15,'full':100}[args.mode],imgsz=320 if args.mode=='smoke' else 640,batch=2 if args.mode=='smoke' else (0.7 if args.device=='cuda' else 2),patience=20,optimizer='auto',amp=args.device=='cuda',workers=0,cache=False,seed=42,deterministic=True,device=0 if args.device=='cuda' else args.device,project=str(run.parent),name=run.name,exist_ok=True,plots=args.mode!='smoke',save=True)
    record = dict(resume_provenance=resume_provenance,cache_backups=cache_backups,command=sys.argv,profile=args.profile,mode=args.mode,device_arithmetic=check,manifest_sha256=file_sha(ROOT/'manifests'/f'{args.profile}.json'),manifest_index_sha256=file_sha(ROOT/'manifest-index.json'),initial_weights_sha256=file_sha(weights),selected_pairs=[r['image'] for r in rows],config=options,torch_version=torch.__version__,resume=str(args.resume) if args.resume else None,note='Operational smoke only; not an accuracy evaluation' if args.mode=='smoke' else 'Starting configuration; not claimed optimal')
    (run/'invocation.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    if args.resume:
        # Ultralytics resume restores checkpoint hyperparameters and run directory.
        # Relocate its dataset and outputs explicitly after loading saved state.
        from ultralytics.models.yolo.detect import DetectionTrainer
        class RelocatedResumeTrainer(DetectionTrainer):
            def check_resume(self, overrides):
                super().check_resume(overrides)
                self.args.data = str(data)
                self.args.project = str(run.parent)
                self.args.name = run.name
                self.args.exist_ok = True
                self.args.save_dir = str(run)
        model.train(trainer=RelocatedResumeTrainer,resume=str(args.resume.resolve()),**options)
    else:
        model.train(**options)
    checkpoints = checkpoint_results(run)
    (run/'result.json').write_text(json.dumps({'checkpoints':checkpoints,'run':str(run)},indent=2),encoding='utf-8')
    print('Completed:', run)

if __name__ == '__main__':
    main()
