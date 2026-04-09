param(
    [string]$PythonExe = "D:\anaconda3\envs\ln-translator\python.exe",
    [string]$TextFile,
    [string]$OutputPath = "outputs\translate-smoke.json",
    [int]$BatchSize = 2,
    [int]$MaxNewTokens = 64
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot "test_translate.py"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python executable does not exist: $PythonExe"
}

Push-Location $projectRoot
try {
    $arguments = @($scriptPath, "--output", $OutputPath, "--batch-size", $BatchSize, "--max-new-tokens", $MaxNewTokens)
    if ($TextFile) {
        $arguments += @("--text-file", $TextFile)
    }

    & $PythonExe @arguments
}
finally {
    Pop-Location
}
