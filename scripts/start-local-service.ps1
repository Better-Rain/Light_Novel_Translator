param(
    [string]$ModelPath = "D:\models\opus-mt-ja-zh",
    [string]$PythonExe = "D:\anaconda3\envs\ln-translator\python.exe",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 7860,
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$checkScript = Join-Path $PSScriptRoot "check-local-model.ps1"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python executable does not exist: $PythonExe"
}

if (-not $SkipValidation) {
    & $checkScript -ModelPath $ModelPath -PythonExe $PythonExe
}

$resolvedModelPath = (Resolve-Path -LiteralPath $ModelPath).Path
$env:JA_ZH_MODEL_PATH = $resolvedModelPath
$env:HF_LOCAL_FILES_ONLY = "1"

Push-Location $projectRoot
try {
    Write-Host "Starting service with model: $resolvedModelPath"
    Write-Host "Docs: http://$BindHost`:$Port/docs"
    & $PythonExe -m uvicorn app.main:app --host $BindHost --port $Port
}
finally {
    Pop-Location
}
