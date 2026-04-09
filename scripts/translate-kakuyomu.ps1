param(
    [Parameter(Mandatory = $true)]
    [string]$EpisodeUrl,
    [string]$PythonExe = "D:\anaconda3\envs\ln-translator\python.exe",
    [string]$ApiUrl = "http://127.0.0.1:7860/translate/web/kakuyomu",
    [string]$OutputDir = "outputs\kakuyomu",
    [string]$RunName,
    [string]$OutputStem,
    [int]$TimeoutSeconds = 30,
    [int]$BatchSize = 8,
    [int]$MaxNewTokens = 256
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot "translate_kakuyomu.py"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python executable does not exist: $PythonExe"
}

Push-Location $projectRoot
try {
    $arguments = @(
        $scriptPath,
        "--url", $EpisodeUrl,
        "--api-url", $ApiUrl,
        "--output-dir", $OutputDir,
        "--timeout-seconds", $TimeoutSeconds,
        "--batch-size", $BatchSize,
        "--max-new-tokens", $MaxNewTokens
    )

    if ($RunName) {
        $arguments += @("--run-name", $RunName)
    }
    if ($OutputStem) {
        $arguments += @("--output-stem", $OutputStem)
    }

    & $PythonExe @arguments
}
finally {
    Pop-Location
}
