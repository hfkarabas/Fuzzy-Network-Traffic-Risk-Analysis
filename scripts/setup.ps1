$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $PWD '.cache/pip'
py -m venv --without-pip .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
# Offline research pipeline (dataset preparation, fitting, reports).
py -m pip --python .venv install -r requirements-research.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
