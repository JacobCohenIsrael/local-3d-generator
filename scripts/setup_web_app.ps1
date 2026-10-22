$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
& "$PSScriptRoot\setup_native.ps1" -DownloadWeights
if ($LASTEXITCODE -ne 0) { throw 'Native environment setup failed.' }
uv pip install --python .venv/Scripts/python.exe --constraint requirements-shape.lock.txt -r requirements-segmentation.txt
if ($LASTEXITCODE -ne 0) { throw 'Foreground preparation dependencies failed.' }
$pin = (Get-Content upstream.json -Raw | ConvertFrom-Json).hunyuan3d_multiview
$checkout = $pin.source_directory
if (-not (Test-Path -LiteralPath "$checkout/.git")) {
    git clone --depth 1 --filter=blob:none --sparse $pin.repository $checkout
    if ($LASTEXITCODE -ne 0) { throw 'Multi-view source download failed.' }
}
$actual = git -C $checkout rev-parse HEAD
if ($actual -ne $pin.commit) {
    git -C $checkout fetch --depth 1 origin $pin.commit
    if ($LASTEXITCODE -ne 0) { throw 'Pinned source fetch failed.' }
    git -C $checkout checkout --detach $pin.commit
    if ($LASTEXITCODE -ne 0) { throw 'Pinned source checkout failed.' }
}
git -C $checkout sparse-checkout set --no-cone /hy3dgen/shapegen/ /hy3dgen/__init__.py /assets/example_mv_images/ /requirements.txt /LICENSE /NOTICE /README.md
if ($LASTEXITCODE -ne 0) { throw 'Source preparation failed.' }
& .venv/Scripts/python.exe -B scripts/prepare_multiview.py
if ($LASTEXITCODE -ne 0) { throw 'Multi-view or foreground model verification failed.' }
Write-Output 'Web app prepared. Double-click Start Local 3D.cmd.'
