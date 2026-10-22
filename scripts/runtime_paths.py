"""Portable executable discovery; machine-specific overrides stay in the environment."""
import os
from pathlib import Path
import shutil


def blender_executable():
    override = os.environ.get('LOCAL3D_BLENDER')
    if override:
        return Path(override)
    on_path = shutil.which('blender')
    if on_path:
        return Path(on_path)
    program_files = os.environ.get('PROGRAMFILES')
    if program_files:
        candidate = Path(program_files) / 'Blender Foundation' / 'Blender 5.2' / 'blender.exe'
        if candidate.is_file():
            return candidate
    return Path('blender')
