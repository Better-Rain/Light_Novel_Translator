param(
    [Parameter(Mandatory = $true)]
    [string]$EpisodeUrl,
    [string]$PythonExe = "D:\anaconda3\envs\ln-translator\python.exe",
    [string]$OutputPath = "outputs\kakuyomu-extract.json",
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot "test_kakuyomu.py"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python executable does not exist: $PythonExe"
}

Push-Location $projectRoot
try {
    & $PythonExe $scriptPath --url $EpisodeUrl --output $OutputPath --timeout-seconds $TimeoutSeconds
}
finally {
    Pop-Location
}
