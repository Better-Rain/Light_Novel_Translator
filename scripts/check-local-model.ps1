param(
    [string]$ModelPath = "D:\models\opus-mt-ja-zh",
    [string]$PythonExe = "D:\anaconda3\envs\ln-translator\python.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ModelPath)) {
    throw "Model directory does not exist: $ModelPath"
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python executable does not exist: $PythonExe"
}

$resolvedModelPath = (Resolve-Path -LiteralPath $ModelPath).Path
$requiredFiles = @(
    "config.json",
    "source.spm",
    "target.spm",
    "vocab.json"
)

$missing = @()
foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedModelPath $file))) {
        $missing += $file
    }
}

$hasWeights = @(
    "pytorch_model.bin",
    "model.safetensors"
) | ForEach-Object {
    Test-Path -LiteralPath (Join-Path $resolvedModelPath $_)
} | Where-Object { $_ } | Measure-Object | Select-Object -ExpandProperty Count

if ($missing.Count -gt 0) {
    throw "Model directory is missing required files: $($missing -join ', ')"
}

if ($hasWeights -eq 0) {
    throw "Model directory is missing weights. Expected one of: pytorch_model.bin, model.safetensors"
}

$env:JA_ZH_MODEL_PATH = $resolvedModelPath
$env:HF_LOCAL_FILES_ONLY = "1"

@'
import os
import sys
import torch
import transformers
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

path = os.environ["JA_ZH_MODEL_PATH"]
print(f"python: {sys.executable}")
print(f"torch: {torch.__version__}")
print(f"transformers: {transformers.__version__}")

if os.path.exists(os.path.join(path, "pytorch_model.bin")) and tuple(int(part) for part in torch.__version__.split("+", 1)[0].split(".")[:2]) < (2, 6):
    raise RuntimeError(
        "This model uses pytorch_model.bin, but the current torch version is below 2.6. "
        "Upgrade torch or replace the weights with model.safetensors."
    )

tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
model = AutoModelForSeq2SeqLM.from_pretrained(path, local_files_only=True)
print("model-load-ok")
print(type(tokenizer).__name__)
print(type(model).__name__)
'@ | & $PythonExe -
