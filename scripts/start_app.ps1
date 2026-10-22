param([switch]$NoBrowser, [ValidateRange(1024, 65535)][int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$localUrl = "http://127.0.0.1:$Port"
$pythonPath = if ($env:LOCAL3D_PYTHON) { $env:LOCAL3D_PYTHON } else { Join-Path $projectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts\setup_native.ps1 first.' }
$ready = $false
try { $ready = (Invoke-RestMethod "$localUrl/api/health" -TimeoutSec 2).ready } catch { }
if (-not $ready) {
    $workerFile = Join-Path $PSScriptRoot 'web_app.py'
    $workFolder = Join-Path $projectRoot 'work'
    New-Item -ItemType Directory -Force -Path $workFolder | Out-Null
    Start-Process -FilePath $pythonPath -ArgumentList @('-B', ('"' + $workerFile + '"'), '--port', $Port) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $workFolder 'web-app.log') -RedirectStandardError (Join-Path $workFolder 'web-app-errors.log')
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        try { $ready = (Invoke-RestMethod "$localUrl/api/health" -TimeoutSec 2).ready } catch { }
        if ($ready) { break }
    }
}
if (-not $ready) { throw 'The app did not start. Check work\web-app-errors.log.' }
Write-Output "Local 3D Generator is running at $localUrl"
if (-not $NoBrowser) { Start-Process $localUrl }
