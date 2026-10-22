"""Read-only texture prerequisites inventory; never load models or build/install."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def command(arguments):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return {'exit_code': result.returncode, 'stdout': result.stdout.strip(), 'stderr': result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'error': str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('work/texture-readiness.json'))
    parser.add_argument('--asset-root', type=Path, help='Optional existing project to inspect read-only')
    args = parser.parse_args()
    report = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.executable,
        'inference_started': False, 'installed_or_modified_dependencies': False,
        'tools_on_path': {name: shutil.which(name) for name in ('nvcc', 'cl', 'cmake', 'ninja')}}
    distributions = ('torch','torchvision','diffusers','accelerate','xatlas','realesrgan','basicsr',
        'cupy-cuda12x','pybind11','ninja','open3d','pygltflib','deepspeed','setuptools','bpy')
    report['packages'] = {}
    for name in distributions:
        try:
            report['packages'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report['packages'][name] = None
    report['native_modules'] = {name: importlib.util.find_spec(name) is not None
        for name in ('custom_rasterizer','custom_rasterizer_kernel','mesh_processor','mesh_inpaint_processor')}
    import psutil
    memory = psutil.virtual_memory()
    report['ram'] = {'total_bytes': memory.total, 'available_bytes': memory.available}
    report['nvidia_smi'] = command(['nvidia-smi','--query-gpu=name,memory.total,memory.used,memory.free,driver_version',
                                  '--format=csv,noheader,nounits'])
    import torch
    report['torch'] = {'version':torch.__version__, 'cuda_runtime':torch.version.cuda,
        'cuda_available':torch.cuda.is_available()}
    try:
        from torch.utils.cpp_extension import CUDA_HOME
        report['torch']['cuda_toolkit_detected_by_torch'] = CUDA_HOME
    except ImportError as error:
        report['torch']['cpp_extension_import_error'] = str(error)
    conventional_cuda = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'NVIDIA GPU Computing Toolkit/CUDA'
    report['cuda_toolkit_directories'] = [str(p) for p in conventional_cuda.glob('*')] if conventional_cuda.exists() else []
    vswhere = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if vswhere.exists():
        report['msvc_cxx_component'] = command([str(vswhere),'-products','*','-requires',
            'Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'])
    if args.asset_root:
        report['inspected_asset_root'] = str(args.asset_root.resolve())
        report['paint_weight_directories_present'] = {
            name: (args.asset_root/'models'/name).exists() for name in
            ('hunyuan3d-2.1/hunyuan3d-paintpbr-v2-1', 'hunyuan3d-2/hunyuan3d-paint-v2-0',
             'hunyuan3d-2/hunyuan3d-paint-v2-0-turbo','hunyuan3d-2/hunyuan3d-delight-v2-0')}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
