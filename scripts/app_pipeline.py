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
from runtime_paths import blender_executable, project_python
from app_views import conditioned_views, candidates_for, HYBRID_STRATEGY, DIRECTIONS

PYTHON = project_python(ROOT)
BLENDER = blender_executable()


class StageError(RuntimeError):
    """A child exited unsuccessfully; ownership/deadline failures propagate."""


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
        if name == 'vision' and sample['ram_available_bytes'] < 2 * 2**30:
            raise MemoryError('Strata vision stopped because less than 2 GiB system RAM remained; no restart attempted')
    try:
        code = owned.wait(timeout, observe=observe, cancel=folder / 'CANCEL')
        record['exit_code'] = code
        if code:
            tail = (target / f'{name}.log').read_text(errors='replace')[-1800:]
            print(tail, file=sys.stderr, flush=True)
            if 'out of memory' in tail.lower():
                raise StageError('GPU memory was exhausted. Close other GPU apps and try Balanced quality.')
            raise StageError(f'{name.capitalize()} could not finish. Diagnostic details were saved in the local job folder.')
    finally:
        owned.close()
        record['owned_shutdown_confirmed'] = owned.shutdown_confirmed
        with (folder / 'stages.jsonl').open('a') as stream:
            stream.write(json.dumps(record) + '\n')


def plan_job(folder, job):
    settings = job['settings']
    selected_views = conditioned_views(folder, job)
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
            'subject': job['name'], 'model': 'Hunyuan3D-2mv' if len(selected_views) > 1 else 'Hunyuan3D-2.1',
            'views': selected_views, 'submitted_images': len(candidates_for(job))})
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
        if job.get('view_strategy') == HYBRID_STRATEGY and any(c['id'] not in DIRECTIONS for c in candidates_for(job)):
            config = ROOT / 'work/strata-vision.json'
            if not config.is_file():
                raise RuntimeError('Extra-photo recognition needs Strata vision. Run scripts/setup_strata_vision.py first.')
            progress(folder, 'selecting', 'Comparing extra photos with your labelled reference views')
            before_vision = resources()
            stage(folder, [PYTHON, '-B', 'scripts/strata_select.py', '--job-dir', folder,
                           '--config', config], 'vision', 900)
            after_vision = resources()
            if after_vision.get('gpu_used_mib', float('inf')) > before_vision.get('gpu_used_mib', 0) + 512:
                raise RuntimeError('Strata vision GPU allocation was not released; stopped before shape loading')
            if after_vision['ram_available_bytes'] < 8 * 2**30 or after_vision.get('gpu_free_mib', 0) < 10000:
                raise RuntimeError('Insufficient available RAM/VRAM after photo analysis; stopped before shape loading')
        selected_views = conditioned_views(folder, job)
        selection_path = folder / 'view-selection.json'
        selection = json.loads(selection_path.read_text(encoding='utf-8')) if selection_path.exists() else None
        plan = plan_job(folder, job)
        accepted = None
        for attempt in range(1, job['settings']['max_attempts'] + 1):
            target = folder / f'attempt-{attempt}'
            target.mkdir()
            attempt_plan = dict(plan)
            attempt_plan['seed'] = (plan['seed'] + (attempt - 1) * 104729) % 2**31
            save(target / 'plan.json', attempt_plan)
            progress(folder, 'generating', f'Building geometry from {len(selected_views)} selected views · attempt {attempt} of {job["settings"]["max_attempts"]}', attempt=attempt)
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
        texture = {'mode':'none','status':'not_requested'}
        export_args = []
        if job['settings'].get('texture','none') == 'photo_basecolor':
            progress(folder,'texturing','Preparing final geometry and UVs for photo color')
            stage(folder,[BLENDER,'--background','--factory-startup','--python-exit-code','1',
                '--python','scripts/blender_geometry.py','--','--input',accepted/'raw.glb',
                '--output-dir',folder/'geometry','--height',str(job['settings']['height']),
                '--triangles',str(job['settings']['triangles'])],'uv-geometry',300)
            export_args = ['--prepared-blend',folder/'geometry/geometry.blend']
            progress(folder,'texturing','Fitting photos, checking visible surfaces and baking base color')
            try:
                stage(folder,[PYTHON,'-B','scripts/photo_bake.py','--job-dir',folder,
                    '--geometry',folder/'geometry/geometry.npz','--output-dir',folder/'texture',
                    '--size',str(job['settings'].get('texture_size',1024)),
                    '--fill',job['settings'].get('texture_fill','neutral')],'photo-bake',600)
                texture = json.loads((folder/'texture/bake-report.json').read_text())
                export_args += ['--texture-dir',folder/'texture']
            except StageError as error:
                # No paint retry. Preserve evidence and the usable frozen mesh.
                texture = {'mode':'photo_basecolor','status':'failed','warnings':[
                    str(error),'Untextured mesh exported; photo baking did not succeed.']}
        progress(folder, 'exporting', 'Exporting the mesh and validating FBX geometry and material files')
        stage(folder, [BLENDER, '--background', '--factory-startup', '--python-exit-code', '1',
            '--python', 'scripts/blender_unity.py', '--', '--input', accepted / 'raw.glb',
            '--output-dir', folder / 'asset', '--height', str(job['settings']['height']),
            '--triangles', str(job['settings']['triangles']),*export_args], 'blender', 300)
        export = json.loads((folder / 'asset/export-report.json').read_text())
        report = {'name': job['name'], 'model': report['model'], 'views_used': selected_views,
            'submitted_view_count': len(candidates_for(job)), 'view_selection': selection,
            'attempts': attempt, 'plan': attempt_plan, 'shape': report, 'export': export,
            'visual_acceptance': 'Inspect likeness in the viewer; automated checks only validate basic geometry',
            'seconds': time.time() - job['created_at'], 'textures':texture['status']=='applied',
            'texture':texture, 'rigged': False,
            'source_sha256': hashes, 'model_provenance': json.loads((ROOT / 'upstream.json').read_text()),
            'post_run_resources': resources(),
            'all_owned_stages_stopped': all(json.loads(line)['owned_shutdown_confirmed']
                for line in (folder / 'stages.jsonl').read_text().splitlines())}
        save(folder / 'report.json', report)
        (folder / 'asset/UNITY_README.txt').write_text(
            'Drag asset.fbx into your Unity project Assets folder.\n'
            'Static mesh, no skeleton, animation or generated PBR maps.\n'
            'Export axes: -Z forward, Y up. Height is in meters; FBX scale/unit metadata applied.\n'
            'Use a material in Unity, inspect orientation and review mesh collider/LOD needs.\n'
            'Automated file checks do not establish likeness or game readiness.\n'
            'When textures/ exists, keep it beside asset.fbx. In Unity create a material,\n'
            'assign textures/basecolor.png to Base Map/Albedo (sRGB), metallic 0, roughness 0.8\n'
            '(smoothness 0.2). These are assumed constants, not recovered physical properties.\n'
            'coverage.png marks photo-observed color. inferred.png, when present, marks estimated\n'
            'color extended from nearby surface samples, not recovered texture detail.\n'
            'These are diagnostic masks, not opacity maps. Never use them as alpha.\n')
        with zipfile.ZipFile(folder / 'asset/unity-package.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in ('asset.fbx', 'UNITY_README.txt', 'export-report.json'):
                archive.write(folder / 'asset' / name, name)
            archive.write(folder / 'report.json', 'generation-report.json')
            if selection_path.exists():
                archive.write(selection_path, 'view-selection.json')
            if report['textures']:
                archive.write(folder/'asset/material-manifest.json','material-manifest.json')
                for name in ('basecolor','coverage','uvmask',*(['inferred'] if 'inferred' in texture['maps'] else [])):
                    archive.write(folder/f'asset/textures/{name}.png',f'textures/{name}.png')
        message = ('Textured FBX and Unity ZIP ready · inspect the photo coverage'
                   if report['textures'] else 'FBX ready · inspect the model before importing it into Unity')
        if texture['status']=='failed':
            message = 'Photo baking failed; untextured FBX available. See the report.'
        progress(folder,'completed',message,attempt=attempt)
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
