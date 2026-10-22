"""Autonomous bounded job; independent of Codex and the browser tab."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import time
import zipfile

import psutil
from controller import ROOT, resources, save
from native_process import OwnedProcess
from strata_plan import validate_plan
from runtime_paths import blender_executable

PYTHON = ROOT / '.venv/Scripts/python.exe'
BLENDER = blender_executable()


def progress(folder, state, message, **extra):
    data = {'stage': state, 'message': message, 'updated_at': datetime.now(timezone.utc).isoformat(), **extra}
    temp = folder / 'progress.tmp'
    save(temp, data)
    os.replace(temp, folder / 'progress.json')


def stage(folder, command, name, timeout, log_dir=None, env=None):
    if (folder / 'CANCEL').exists():
        raise InterruptedError('Job cancelled')
    target = log_dir or folder
    record = {'stage': name, 'started_at': datetime.now(timezone.utc).isoformat(), 'timeout': timeout}
    owned = OwnedProcess(list(map(str, command)), target / f'{name}.log', cwd=str(ROOT), env=env)
    record['pid'] = owned.proc.pid
    def observe(pid, elapsed):
        sample = resources()
        sample.update(stage=name, elapsed_seconds=elapsed, pid=pid)
        with (folder / 'telemetry.jsonl').open('a') as stream:
            stream.write(json.dumps(sample) + '\n')
    try:
        code = owned.wait(timeout, observe=observe, cancel=folder / 'CANCEL')
        record['exit_code'] = code
        if code:
            tail = (target / f'{name}.log').read_text(errors='replace')[-1800:]
            print(tail, file=sys.stderr, flush=True)
            if 'out of memory' in tail.lower():
                raise RuntimeError('GPU memory was exhausted. Close other GPU apps and try Balanced quality.')
            raise RuntimeError(f'{name.capitalize()} could not finish. Diagnostic details were saved in the local job folder.')
    finally:
        owned.close()
        record['owned_shutdown_confirmed'] = owned.shutdown_confirmed
        with (folder / 'stages.jsonl').open('a') as stream:
            stream.write(json.dumps(record) + '\n')


def plan_job(folder, job):
    settings = job['settings']
    plan = {'seed': secrets.randbelow(2**31), 'steps': 30 if settings['quality'] == 'balanced' else 50,
            'octree_resolution': 256 if settings['quality'] == 'balanced' else 384,
            'guidance_scale': 5.0, 'num_chunks': 2048}
    if settings['planner'] == 'strata':
        progress(folder, 'planning', 'Strata is choosing generation settings')
        planning = folder / 'planning'
        planning.mkdir()
        from PIL import Image
        with Image.open(folder / 'prepared/front.png') as image:
            dimensions = list(image.size)
        save(planning / 'input.json', {'dimensions': dimensions, 'quality': settings['quality'],
            'subject': job['name'], 'model': 'Hunyuan3D-2mv' if len(job['views']) > 1 else 'Hunyuan3D-2.1',
            'views': job['views']})
        config_path = ROOT / 'work/strata-native.json'
        config = json.loads(config_path.read_text())
        baseline = resources()
        stage(folder, [PYTHON, '-B', 'scripts/strata_plan.py', 'prepare', '--run-dir', planning,
                       '--config', config_path], 'prepare-plan', 30, planning)
        env = dict(os.environ)
        env['PATH'] = os.pathsep.join(config.get('lib_dirs', []) + [env.get('PATH', '')])
        stage(folder, [config['exe'], *config['args'], '--gpu', '0', '--tokens-file', planning / 'prompt-tokens.txt',
                       '--max-new', '512', '--stop-eos'], 'strata', 600, planning, env)
        after = resources()
        if after.get('gpu_used_mib', float('inf')) > baseline.get('gpu_used_mib', 0) + 512:
            raise RuntimeError('Strata GPU allocation was not released; stopped before shape loading')
        stage(folder, [PYTHON, '-B', 'scripts/strata_plan.py', 'decode', '--run-dir', planning,
                       '--config', config_path], 'decode-plan', 30, planning)
        plan = validate_plan(json.loads((planning / 'plan.json').read_text()))
    save(folder / 'plan.json', plan)
    return plan


def run(folder):
    job = json.loads((folder / 'job.json').read_text())
    lock = ROOT / 'work/controller.lock'
    # Do not disturb another live controller, including the original CLI.
    if lock.exists():
        try:
            live = psutil.pid_exists(int(lock.read_text()))
        except (ValueError, OSError):
            live = True
        if live:
            raise RuntimeError('Another local generation is active. Wait until it finishes.')
        lock.unlink()
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    try:
        snapshot = folder / 'source-snapshot'
        snapshot.mkdir()
        hashes = {}
        for source in [*sorted((ROOT / 'scripts').glob('*.py')), ROOT / 'upstream.json',
                       ROOT / 'requirements-shape.lock.txt', ROOT / 'requirements-segmentation.txt']:
            if source.is_file():
                shutil.copy2(source, snapshot / source.name)
                hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        save(snapshot / 'hashes.json', hashes)
        baseline = resources()
        save(folder / 'baseline.json', baseline)
        if baseline['ram_available_bytes'] < 8 * 2**30:
            raise RuntimeError('Less than 8 GiB RAM available. Close other apps and submit again.')
        if baseline.get('gpu_free_mib', 0) < 10000:
            raise RuntimeError('Less than 10 GB GPU memory free. Close other GPU workloads and submit again.')
        progress(folder, 'preparing', 'Isolating the subject in each uploaded view')
        stage(folder, [PYTHON, '-B', 'scripts/app_images.py', '--job-dir', folder], 'cutouts', 240)
        plan = plan_job(folder, job)
        accepted = None
        for attempt in range(1, job['settings']['max_attempts'] + 1):
            target = folder / f'attempt-{attempt}'
            target.mkdir()
            attempt_plan = dict(plan)
            attempt_plan['seed'] = (plan['seed'] + (attempt - 1) * 104729) % 2**31
            save(target / 'plan.json', attempt_plan)
            progress(folder, 'generating', f'Building geometry · attempt {attempt} of {job["settings"]["max_attempts"]}', attempt=attempt)
            stage(folder, [PYTHON, '-B', 'scripts/app_shape.py', '--job-dir', folder,
                           '--attempt-dir', target], 'shape', 1200, target)
            report = json.loads((target / 'shape-report.json').read_text())
            if report['quality_pass']:
                accepted = target
                break
            progress(folder, 'checking', report['rejection_reason'], attempt=attempt)
        if accepted is None:
            raise ValueError('Both geometry checks rejected the result.' if job['settings']['max_attempts'] == 2
                             else 'Geometry check rejected the result. Try clearer views or allow flat objects if appropriate.')
        progress(folder, 'exporting', 'Preparing Unity scale, reducing geometry and checking the FBX export')
        stage(folder, [BLENDER, '--background', '--factory-startup', '--python-exit-code', '1',
            '--python', 'scripts/blender_unity.py', '--', '--input', accepted / 'raw.glb',
            '--output-dir', folder / 'asset', '--height', str(job['settings']['height']),
            '--triangles', str(job['settings']['triangles'])], 'blender', 300)
        export = json.loads((folder / 'asset/export-report.json').read_text())
        report = {'name': job['name'], 'model': report['model'], 'views_used': job['views'],
            'attempts': attempt, 'plan': attempt_plan, 'shape': report, 'export': export,
            'visual_acceptance': 'Inspect likeness in the viewer; automated checks only validate basic geometry',
            'seconds': time.time() - job['created_at'], 'textures': False, 'rigged': False,
            'source_sha256': hashes, 'model_provenance': json.loads((ROOT / 'upstream.json').read_text()),
            'post_run_resources': resources(),
            'all_owned_stages_stopped': all(json.loads(line)['owned_shutdown_confirmed']
                for line in (folder / 'stages.jsonl').read_text().splitlines())}
        save(folder / 'report.json', report)
        (folder / 'asset/UNITY_README.txt').write_text(
            'Drag asset.fbx into your Unity project Assets folder.\n'
            'Static mesh, no skeleton, animation or generated PBR textures.\n'
            'Export axes: -Z forward, Y up. Height is in meters; FBX scale/unit metadata applied.\n'
            'Use a material in Unity, inspect orientation and review mesh collider/LOD needs.\n'
            'Automated file checks do not establish likeness or game readiness.\n')
        with zipfile.ZipFile(folder / 'asset/unity-package.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in ('asset.fbx', 'UNITY_README.txt', 'export-report.json'):
                archive.write(folder / 'asset' / name, name)
            archive.write(folder / 'report.json', 'generation-report.json')
        progress(folder, 'completed', 'FBX ready · inspect the model before importing it into Unity', attempt=attempt)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.job_dir)
    except BaseException as error:
        progress(args.job_dir, 'failed', str(error))
        raise
