"""Download the pinned official multi-view checkpoint, verify its SHA-256."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = '3a761b539b29fe4ff64714813aa9560fd66f5de0'
BASE = f'https://huggingface.co/tencent/Hunyuan3D-2mv/resolve/{REVISION}/'
WEIGHT = 'hunyuan3d-dit-v2-mv/model.fp16.safetensors'
EXPECTED = 'd36f5881bcdc56726b73e517cd444c13c60732431622da7268145355c8d38e9c'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def download(url, path, checksum=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (checksum is None or sha256(path) == checksum):
        print(f'Already present: {path.name}', flush=True)
        return
    temporary = path.with_suffix(path.suffix + '.partial')
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as stream:
        total = 0
        while block := response.read(8 * 1024 * 1024):
            stream.write(block)
            total += len(block)
            if total % (256 * 1024 * 1024) < len(block):
                print(f'{path.name}: {total / 2**30:.2f} GiB downloaded', flush=True)
    if checksum and sha256(temporary) != checksum:
        raise ValueError(f'Checksum mismatch: {path.name}; partial file retained')
    temporary.replace(path)
    print(f'Prepared {path.name}', flush=True)


if __name__ == '__main__':
    for name in ('hunyuan3d-dit-v2-mv/config.yaml', 'README.md', 'LICENSE', 'NOTICE', WEIGHT):
        download(BASE + name, ROOT / 'models/hunyuan3d-2mv' / name,
                 EXPECTED if name == WEIGHT else None)
    for filename, md5 in [('u2net.onnx', '60024c5c889badc19c04ad937298a77b'),
                          ('u2net_human_seg.onnx', 'c09ddc2e0104f800e3e1bb4652583d1f')]:
        path = ROOT / 'models/segmentation' / filename
        if path.exists() and hashlib.md5(path.read_bytes()).hexdigest() == md5:
            continue
        if path.exists():
            raise ValueError(f'Existing segmentation checksum mismatch: {filename}')
        download('https://github.com/danielgatis/rembg/releases/download/v0.0.0/' + filename, path)
        if hashlib.md5(path.read_bytes()).hexdigest() != md5:
            raise ValueError(f'Segmentation checksum mismatch: {filename}')
