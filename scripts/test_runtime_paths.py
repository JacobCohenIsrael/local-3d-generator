"""Portable Blender discovery without embedding a particular user's paths."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime_paths import blender_executable, project_python, asset_root


class RuntimePathTests(unittest.TestCase):
    def test_worktree_overrides_are_explicit_and_defaults_are_local(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(project_python(Path('checkout')),Path('checkout/.venv/Scripts/python.exe'))
            self.assertEqual(asset_root(Path('checkout')),Path('checkout'))
        with patch.dict(os.environ,{'LOCAL3D_PYTHON':'tools/python.exe','LOCAL3D_ASSET_ROOT':'assets'},clear=True):
            self.assertEqual(project_python(Path('checkout')),Path('tools/python.exe'))
            self.assertEqual(asset_root(Path('checkout')),Path('assets'))

    def test_explicit_environment_override_wins(self):
        with patch.dict(os.environ, {'LOCAL3D_BLENDER': 'custom/blender.exe'}, clear=True), \
             patch('runtime_paths.shutil.which', return_value='other/blender'):
            self.assertEqual(blender_executable(), Path('custom/blender.exe'))

    def test_path_discovery(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch('runtime_paths.shutil.which', return_value='tools/blender'):
            self.assertEqual(blender_executable(), Path('tools/blender'))

    def test_standard_installation_discovery(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / 'work') as directory:
            executable = Path(directory) / 'Blender Foundation/Blender 5.2/blender.exe'
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch.dict(os.environ, {'PROGRAMFILES': directory}, clear=True), \
                 patch('runtime_paths.shutil.which', return_value=None):
                self.assertEqual(blender_executable(), executable)

    def test_missing_executable_has_portable_fallback(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch('runtime_paths.shutil.which', return_value=None):
            self.assertEqual(blender_executable(), Path('blender'))


if __name__ == '__main__':
    unittest.main()
