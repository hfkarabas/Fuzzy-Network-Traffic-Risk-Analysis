param([switch]$Install, [switch]$Build, [switch]$Dev)
$ErrorActionPreference = 'Stop'
$repoPath = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoPath
$pythonPath = Join-Path $repoPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create the project .venv first; see docs/web_application.md.' }
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $repoPath '.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $repoPath '.cache\pip'
$env:NPM_CONFIG_CACHE = Join-Path $repoPath '.cache\npm'
if ($Install) {
    py -m pip --python .venv install -r requirements-web.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    npm --prefix web ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
}
& $pythonPath -c 'import fastapi, uvicorn'
if ($LASTEXITCODE -ne 0) { throw 'Install web dependencies with scripts/start-web.ps1 -Install -Build.' }
if ($Build -or (-not $Dev -and -not (Test-Path -LiteralPath 'web/dist/index.html'))) {
    npm --prefix web run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
$existing = $null
try { $existing = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 } catch { }
$expectedModel = (Get-Content -Raw -LiteralPath 'config/fuzzy/task02b/selected_manifest.json' | ConvertFrom-Json).model_id
if ($existing -and $existing.model_id -ne $expectedModel) { throw 'Port 8000 belongs to a different service. Stop it or use manual documented commands.' }
if ($Dev) {
    $ownedBackend = $null
    try {
        if (-not $existing) {
            $ownedBackend = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','fuzzy_network_risk.webapp.api:app','--app-dir','src','--host','127.0.0.1','--port','8000') -WorkingDirectory $repoPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $repoPath '.tmp/web-backend.log') -RedirectStandardError (Join-Path $repoPath '.tmp/web-backend-error.log')
            $ready = $false
            for ($attempt = 0; $attempt -lt 20; $attempt++) {
                try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 1; $ready = $true; break } catch { Start-Sleep -Milliseconds 250 }
                if ($ownedBackend.HasExited) { throw 'Backend exited; inspect .tmp/web-backend-error.log.' }
            }
            if (-not $ready) { throw 'Backend startup timed out.' }
        }
        Write-Host 'Development UI: http://127.0.0.1:5173 | API: http://127.0.0.1:8000'
        npm --prefix web run dev
    } finally {
        if ($ownedBackend -and -not $ownedBackend.HasExited) { Stop-Process -Id $ownedBackend.Id }
    }
} elseif ($existing) {
    Write-Host 'Application already running: http://127.0.0.1:8000'
} else {
    Write-Host 'Application: http://127.0.0.1:8000 | Offline API docs: http://127.0.0.1:8000/docs'
    & $pythonPath -m uvicorn fuzzy_network_risk.webapp.api:app --app-dir src --host 127.0.0.1 --port 8000
}
