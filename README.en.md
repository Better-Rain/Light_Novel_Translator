# Local Translation and Reading Workbench

Chinese documentation is available in [README.md](README.md).

This is a local translation and reading workbench for two primary input types:

- Kakuyomu single-episode light novel URLs
- Local PDF documents in English or Japanese

The main workflow is:

```text
extract -> segment -> translate to Chinese -> save JSON/HTML -> read in the Web UI
```

Generated results are saved under `outputs/`. The project does not use a database.

## 1. Current Features

- `FastAPI + Uvicorn` backend.
- `/translate/ja` Japanese-to-Chinese plain-text API.
- `/translate/en` English-to-Chinese plain-text API, including local NLLB/M2M100-style source token and forced BOS token handling.
- Kakuyomu single-episode extraction, translation, saving, history, and saved-result loading.
- PDF extraction, translation, saving, history, and saved-result loading.
- Web UI with Kakuyomu and PDF sources.
- Reading mode, side-by-side comparison, and sentence comparison in the Web UI.
- PDF debug caps for maximum pages and maximum paragraphs, useful for quick long-document validation.
- A PDF extraction debug-report CLI for inspecting filtering, demotion, and end-matter decisions.
- Stable local output directories:
  - `outputs/library/kakuyomu/<work-id>/<episode-id>/`
  - `outputs/library/pdf/<document-id>/`

## 2. Environment Setup

Use the existing project Conda environment when available:

```powershell
conda activate D:\anaconda3\envs\ln-translator
cd "E:\Programs\Vscode Projects\Light_Novel_Translator"
```

To create a fresh environment:

```powershell
conda create -n ln-translator python=3.11 -y
conda activate ln-translator
pip install fastapi "uvicorn[standard]" pydantic PyMuPDF pdfplumber readability-lxml beautifulsoup4 redis
pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu126
pip install numpy transformers sentencepiece sacremoses accelerate
```

Notes:

- The project requires `torch>=2.6.0`.
- Some Marian checkpoints still use `pytorch_model.bin`; recent `transformers` builds reject those weights with older Torch versions.
- `requirements.txt` reflects the currently working constraints.

## 3. Local Models

Common local model variables:

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:EN_ZH_MODEL_PATH="D:\models\nllb-200-distilled-600M"
$env:HF_LOCAL_FILES_ONLY="1"
```

The Japanese-to-Chinese model directory should contain at least:

- `config.json`
- `source.spm`
- `target.spm`
- `vocab.json`
- `pytorch_model.bin` or `model.safetensors`

English-to-Chinese currently uses NLLB/M2M100-style local models through `EN_ZH_MODEL_PATH`.

Check the Japanese-to-Chinese model:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-local-model.ps1
```

## 4. Start the Service

Starting with the project Python is recommended because both translation model paths can be configured explicitly:

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:EN_ZH_MODEL_PATH="D:\models\nllb-200-distilled-600M"
$env:HF_LOCAL_FILES_ONLY="1"
& "D:\anaconda3\envs\ln-translator\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 7860
```

After startup:

- `http://127.0.0.1:7860/`
- `http://127.0.0.1:7860/docs`
- `http://127.0.0.1:7860/health`

Health check:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7860/health"
```

Expected response:

```json
{"status":"ok"}
```

## 5. Web UI

Open:

```text
http://127.0.0.1:7860/
```

Kakuyomu single episode:

1. Select `Kakuyomu single episode`.
2. Enter a Kakuyomu episode URL.
3. Start the job.
4. Switch between reading, side-by-side comparison, and sentence comparison after completion.

PDF document:

1. Select `PDF document`.
2. Enter the absolute path to a local PDF.
3. Select `English` or `Japanese` as the source language.
4. For long-document checks, optionally set maximum debug pages and paragraphs.
5. Start the job.

PDF debug runs do not overwrite full results. When debug caps are active, `document_id` receives a suffix such as `-debug-p2-n8`, and history entries are marked as `DEBUG`.

## 6. Main APIs

Plain-text translation:

- `POST /translate/ja`
- `POST /translate/en`

Kakuyomu:

- `POST /extract/web/kakuyomu`
- `POST /translate/web/kakuyomu`
- `POST /ui/api/kakuyomu/translate-save`
- `GET /ui/api/kakuyomu/history`
- `GET /ui/api/kakuyomu/result/{work_id}/{episode_id}`

PDF:

- `POST /extract/pdf`
- `POST /translate/pdf`
- `POST /ui/api/pdf/translate-save`
- `GET /ui/api/pdf/history`
- `GET /ui/api/pdf/result/{document_id}`

PDF translation requests can include debug caps:

```json
{
  "file_path": "D:\\docs\\paper.pdf",
  "source_language": "en",
  "debug_max_pages": 2,
  "debug_max_paragraphs": 24
}
```

## 7. Output Layout

Kakuyomu output directory:

```text
outputs/library/kakuyomu/<work-id>/<episode-id>/
```

Common files:

- `result.json`
- `bilingual.html`
- `reading.html`
- `index.html`

PDF output directory:

```text
outputs/library/pdf/<document-id>/
```

Common files:

- `result.json`
- `bilingual.html`
- `reading.html`
- `index.html`

## 8. Quick Verification

Run the local regression checks without loading the real translation models:

```powershell
& "D:\anaconda3\envs\ln-translator\python.exe" .\scripts\verify_local_fixes.py
```

If the sample PDF is unavailable:

```powershell
& "D:\anaconda3\envs\ln-translator\python.exe" .\scripts\verify_local_fixes.py --skip-pdf
```

Write a PDF extraction debug report:

```powershell
& "D:\anaconda3\envs\ln-translator\python.exe" .\scripts\debug_pdf_extraction.py ".\The Death and Life of Great American Cities (Jane Jacobs) (z-library.sk, 1lib.sk, z-lib.sk).pdf" --output outputs\pdf_extraction_debug_report.json
```

The report includes page-level filtering reasons, kept/dropped/demoted counts, sample text, detected body start, and detected end-matter start. The output file is under `outputs/` and should not be committed.

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for the fuller manual test flow.

## 9. PDF Extraction Status

The current extractor:

- Reads text blocks with PyMuPDF.
- Cleans soft hyphens, zero-width characters, and excess whitespace.
- Estimates body font size.
- Filters repeated running headers, footers, page numbers, and obvious OCR noise.
- Detects front matter; the current sample PDF starts useful body content around page 12.
- Preserves `chapter_heading`, `heading`, and `paragraph` as distinct paragraph kinds.
- Demotes suspicious false headings back to paragraphs.
- Detects sample-PDF end matter such as index/advertising/publisher catalog pages.

OCR-heavy and complex-layout PDFs still need more work, especially around chapter structure and table-of-contents quality.

## 10. Current Limitations

- Kakuyomu is still single-episode only; whole-work crawling and automatic multi-episode traversal are not implemented yet.
- PDF sentence comparison is still punctuation-based and is not true semantic alignment.
- Japanese PDF front-matter and heading heuristics are less mature than the English rules.
- Terminology dictionaries, Redis caching, and user-correction learning remain future work.
- Translation quality depends on the local model, and full long-document translation can take substantial CPU/GPU time.

## 11. Suggested Local Directories

Keep models, source documents, and generated outputs local and out of version control:

- `models/`
- `data/`
- `outputs/`
- `downloads/`
