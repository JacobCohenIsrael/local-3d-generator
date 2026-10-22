"""Verify bounded geometry retries without GPU inference or Blender."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import app_pipeline


class PipelineTests(unittest.TestCase):
    def test_photo_failure_preserves_mesh_but_deadline_or_cancel_stops_export(self):
        for error in (app_pipeline.StageError('coverage failed'), TimeoutError('deadline'),
                      InterruptedError('cancelled')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory(
                    dir=app_pipeline.ROOT/'work') as directory:
                root = Path(directory)
                (root/'work').mkdir()
                (root/'scripts').mkdir()
                (root/'upstream.json').write_text('{}')
                folder = root/'job'
                folder.mkdir()
                (folder/'job.json').write_text(json.dumps({'name':'test','views':['front'],
                    'created_at':time.time(),'settings':{'quality':'balanced','planner':'preset',
                        'max_attempts':1,'height':1.8,'triangles':50000,'texture':'photo_basecolor'}}))
                stages = []
                def fake_stage(job_folder, command, name, timeout, log_dir=None, env=None):
                    stages.append(name)
                    if name == 'shape':
                        target = Path(log_dir)
                        (target/'raw.glb').write_bytes(b'preserved raw')
                        (target/'shape-report.json').write_text(json.dumps({'model':'test','quality_pass':True}))
                    elif name == 'photo-bake':
                        raise error
                    elif name == 'blender':
                        self.assertIn('--prepared-blend',command)
                        self.assertNotIn('--texture-dir',command)
                        asset = folder/'asset'
                        asset.mkdir()
                        (asset/'asset.fbx').write_bytes(b'test FBX')
                        (asset/'export-report.json').write_text('{}')
                    with (folder/'stages.jsonl').open('a') as stream:
                        stream.write(json.dumps({'owned_shutdown_confirmed':True})+'\n')
                with patch.object(app_pipeline,'ROOT',root), patch.object(app_pipeline,'stage',side_effect=fake_stage), \
                     patch.object(app_pipeline,'resources',return_value={'ram_available_bytes':16*2**30,'gpu_free_mib':15000}):
                    if isinstance(error,app_pipeline.StageError):
                        app_pipeline.run(folder)
                        report = json.loads((folder/'report.json').read_text())
                        self.assertFalse(report['textures'])
                        self.assertEqual(report['texture']['status'],'failed')
                        self.assertIn('blender',stages)
                    else:
                        with self.assertRaises(type(error)):
                            app_pipeline.run(folder)
                        self.assertNotIn('blender',stages)
                self.assertEqual(stages.count('photo-bake'),1)
                self.assertEqual(stages.count('shape'),1)
                self.assertEqual((folder/'attempt-1/raw.glb').read_bytes(),b'preserved raw')
                self.assertFalse((root/'work/controller.lock').exists())

    def test_reject_once_then_accept_uses_exactly_two_seeds(self):
        with tempfile.TemporaryDirectory(dir=app_pipeline.ROOT / 'work') as directory:
            root = Path(directory)
            (root / 'work').mkdir()
            (root / 'scripts').mkdir()
            (root / 'upstream.json').write_text('{}')
            folder = root / 'job'
            folder.mkdir()
            (folder / 'job.json').write_text(json.dumps({'name':'test', 'views':['front','left'],
                'created_at':time.time(), 'settings':{'quality':'balanced','planner':'preset',
                    'max_attempts':2,'height':1.8,'triangles':50000}}))
            seeds = []
            def fake_stage(job_folder, command, name, timeout, log_dir=None, env=None):
                if name == 'shape':
                    target = Path(log_dir)
                    seeds.append(json.loads((target / 'plan.json').read_text())['seed'])
                    (target / 'raw.glb').write_bytes(b'preserved raw')
                    (target / 'shape-report.json').write_text(json.dumps({'model':'test',
                        'quality_pass':len(seeds)==2, 'rejection_reason':'flat'}))
                elif name == 'blender':
                    asset = folder / 'asset'
                    asset.mkdir()
                    (asset / 'asset.fbx').write_bytes(b'test FBX')
                    (asset / 'export-report.json').write_text('{}')
                with (folder / 'stages.jsonl').open('a') as stream:
                    stream.write(json.dumps({'owned_shutdown_confirmed':True})+'\n')
            with patch.object(app_pipeline,'ROOT',root), patch.object(app_pipeline,'stage',side_effect=fake_stage), \
                 patch.object(app_pipeline,'resources',return_value={'ram_available_bytes':16*2**30,'gpu_free_mib':15000}):
                app_pipeline.run(folder)
            self.assertEqual(len(seeds),2)
            self.assertNotEqual(seeds[0],seeds[1])
            self.assertEqual(json.loads((folder/'progress.json').read_text())['stage'],'completed')
            self.assertTrue((folder/'attempt-1/raw.glb').exists())
            self.assertTrue((folder/'asset/unity-package.zip').exists())
            self.assertFalse((root/'work/controller.lock').exists())


if __name__ == '__main__':
    unittest.main()
