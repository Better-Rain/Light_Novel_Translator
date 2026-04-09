param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [string]$PythonExe = "D:\anaconda3\envs\ln-translator\python.exe",
    [string]$OutputDir = "outputs\batch",
    [string]$RunName,
    [string]$Pattern = "*.txt",
    [switch]$NoRecursive,
    [switch]$NoPreserveStructure,
    [string]$NameTemplate = "{stem}",
    [string]$Encoding = "utf-8",
    [int]$BatchSize = 8,
    [int]$MaxNewTokens = 256,
    [string]$Url = "http://127.0.0.1:7860/translate/ja"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $PSScriptRoot "batch_translate.py"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python executable does not exist: $PythonExe"
}

Push-Location $projectRoot
try {
    $arguments = @(
        $scriptPath,
        "--input", $InputPath,
        "--output-dir", $OutputDir,
        "--pattern", $Pattern,
        "--name-template", $NameTemplate,
        "--encoding", $Encoding,
        "--batch-size", $BatchSize,
        "--max-new-tokens", $MaxNewTokens,
        "--url", $Url
    )

    if ($RunName) {
        $arguments += @("--run-name", $RunName)
    }

    if ($NoRecursive) {
        $arguments += "--no-recursive"
    }
    if ($NoPreserveStructure) {
        $arguments += "--no-preserve-structure"
    }

    & $PythonExe @arguments
}
finally {
    Pop-Location
}
