param([switch]$DownloadWeights)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$env:UV_CACHE_DIR = Join-Path $projectRoot 'work\uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot 'work\python'
$managedPython = Join-Path $env:UV_PYTHON_INSTALL_DIR 'cpython-3.10.22-windows-x86_64-none\python.exe'
if (-not (Test-Path -LiteralPath $managedPython)) {
    uv python install 3.10.22 --no-bin --no-registry
    if ($LASTEXITCODE -ne 0) { throw 'Python preparation failed.' }
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    uv venv --python $managedPython .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
$sourcePath = 'work/vendor/Hunyuan3D-2.1'
$upstream = Get-Content -LiteralPath upstream.json -Raw | ConvertFrom-Json
if (-not (Test-Path -LiteralPath "$sourcePath/.git")) {
    git clone --depth 1 --filter=blob:none --sparse $upstream.hunyuan3d.repository $sourcePath
    if ($LASTEXITCODE -ne 0) { throw 'Official source checkout failed.' }
    git -C $sourcePath sparse-checkout set --no-cone /hy3dshape/hy3dshape/ /hy3dshape/minimal_demo.py /assets/demo.png /LICENSE /Notice.txt /requirements.txt /README.md
    if ($LASTEXITCODE -ne 0) { throw 'Shape source selection failed.' }
}
$sourceCommit = git -C $sourcePath rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Could not identify source revision.' }
if ($sourceCommit -ne $upstream.hunyuan3d.commit) {
    git -C $sourcePath fetch --depth 1 origin $upstream.hunyuan3d.commit
    if ($LASTEXITCODE -ne 0) { throw 'Pinned source fetch failed.' }
    git -C $sourcePath checkout --detach $upstream.hunyuan3d.commit
    if ($LASTEXITCODE -ne 0) { throw 'Pinned source checkout failed.' }
}
uv pip install --python .venv/Scripts/python.exe --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match -r requirements-shape.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Shape dependencies failed.' }
& .venv/Scripts/python.exe -B scripts/check_shape_environment.py
if ($LASTEXITCODE -ne 0) { throw 'Shape import/CUDA check failed.' }
if ($DownloadWeights) {
    & .venv/Scripts/python.exe -B scripts/prepare_shape_weights.py
    if ($LASTEXITCODE -ne 0) { throw 'Shape weight preparation failed.' }
}
Write-Output 'Environment prepared. No inference or model server was started.'
