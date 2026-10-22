"""Download the pinned matching encoder and create a project-owned vision config."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPO = 'ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF'
REVISION = 'ed59f92082b1e93c0e96d60a8b11aab089b52f09'
FILENAME = 'mmproj-Qwen3.8-Flash-Next-BF16.gguf'
SHA256 = 'b1a82259702816a5330d7bd7607cd9676b11780e79ff7348c21103ff3ce49bd0'
SIZE = 907543008


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-config', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'work/strata-vision.json')
    parser.add_argument('--cpu', action='store_true')
    args = parser.parse_args()
    if args.output.resolve() == args.base_config.resolve():
        raise ValueError('Vision config must not overwrite the base config')
    original = args.base_config.read_bytes()
    config = json.loads(original.decode('utf-8-sig'))
    if config.get('model_name') != 'qwen3.8-flash-next-coder-iq1_m':
        raise ValueError('This adapter is verified only with the existing Qwen Coder IQ1_M pack')
    engine = Path(config['exe'])
    helper = engine.with_name('strata-vision.exe')
    if not helper.is_file():
        raise FileNotFoundError('Install the matching Strata vision helper first')
    native = Path(config['args'][config['args'].index('--native') + 1])
    folder = ROOT / 'models/strata-vision'
    folder.mkdir(parents=True, exist_ok=True)
    encoder = folder / FILENAME
    if not encoder.exists():
        partial = encoder.with_suffix('.partial')
        print(f'Downloading pinned encoder ({SIZE} bytes)', flush=True)
        with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{FILENAME}', timeout=60) as response, partial.open('wb') as stream:
            while True:
                block = response.read(8 * 1024 * 1024)
                if not block:
                    break
                stream.write(block)
        if partial.stat().st_size != SIZE or digest(partial) != SHA256:
            raise ValueError('Vision encoder integrity check failed; partial download retained')
        partial.replace(encoder)
    if encoder.stat().st_size != SIZE or digest(encoder) != SHA256:
        raise ValueError('Existing vision encoder failed integrity verification')
    config['vision'] = {'exe': str(helper), 'mmproj': str(encoder), 'model': str(native),
                        'gpu': not args.cpu, 'threads': 4, 'max_tokens': 384}
    if '--vision' not in config['args']:
        config['args'].append('--vision')
    # Encoder loads first; reserve is additional free VRAM, not its allocation.
    # A larger expert cache also reduces pressure on mapped host pages.
    for flag, value in (('--vram-reserve-mib', '1536'), ('--prefill', '256'), ('--resident-budget-gib', '1')):
        if flag in config['args']:
            config['args'][config['args'].index(flag) + 1] = value
        else:
            config['args'].extend([flag, value])
    config.update(cwd=str(ROOT / 'work'), log=str(ROOT / 'work/strata-vision-engine.log'),
                  open_browser=False, api_monitor=False)
    config.setdefault('env', {})['STRATA_FILE_RELEASE'] = '1'
    # With a small explicit RAM tier, direct expert reads avoid filling the host
    # working set with the entire mapped expert file during a visual prompt.
    config['env']['STRATA_UNBUFFERED_LOAD'] = '1'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2), encoding='utf-8')
    (folder / 'provenance.json').write_text(json.dumps({'repository': REPO, 'revision': REVISION,
        'filename': FILENAME, 'sha256': SHA256, 'bytes': SIZE,
        'upstream_license': 'https://huggingface.co/' + REPO,
        'note': 'Upstream encoder terms apply; not relicensed by this project'}, indent=2))
    if args.base_config.read_bytes() != original:
        raise RuntimeError('Base config changed during setup')
    print('Vision configured; encoder verified; base config unchanged; no inference started', flush=True)


if __name__ == '__main__':
    main()
