param([switch]$CheckOnly, [switch]$NoStart)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot

if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'This installer supports native 64-bit Windows. See SETUP.md.'
}
$missing = @()
foreach ($tool in @('git', 'uv', 'nvidia-smi')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { $missing += $tool }
}
$blender = $env:LOCAL3D_BLENDER
if (-not $blender) {
    $command = Get-Command blender -ErrorAction SilentlyContinue
    if ($command) { $blender = $command.Source }
    else { $blender = Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.2\blender.exe' }
}
if (-not (Test-Path -LiteralPath $blender -PathType Leaf)) { $missing += 'Blender (or LOCAL3D_BLENDER)' }
if ($missing.Count) { throw ('Missing prerequisites: ' + ($missing -join ', ') + '. See SETUP.md; reopen PowerShell after installation.') }
& nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
if ($LASTEXITCODE -ne 0) { throw 'NVIDIA driver check failed. See SETUP.md.' }
$drive = (Get-Item -LiteralPath $projectRoot).PSDrive
if ($null -ne $drive.Free -and $drive.Free -lt 40GB) {
    Write-Warning 'Less than 40 GB free. A fresh setup may run out of space; existing caches may reduce download needs.'
}
Write-Output 'Prerequisites found. See SETUP.md for supported hardware and download requirements.'
if ($CheckOnly) { exit 0 }
& "$PSScriptRoot\setup_web_app.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed. Preserve caches and review the error above.' }
& "$projectRoot\.venv\Scripts\python.exe" -B "$PSScriptRoot\check_shape_environment.py"
if ($LASTEXITCODE -ne 0) { throw 'Installation verification failed.' }
if (-not $NoStart) { & "$PSScriptRoot\start_app.ps1" }
Write-Output 'Setup complete. Use Start Local 3D.cmd next time.'
