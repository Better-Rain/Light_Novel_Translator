# Local Translation Service

This repository currently implements the first project phase:

- A Japanese-to-Chinese translation API, currently using `shun89/opus-mt-ja-zh` as the default candidate
- A PDF paragraph extraction API that preserves paragraph IDs, page numbers, headings, and section context

## 1. Current status

- `FastAPI + Uvicorn` backend is in place
- The Japanese translation pipeline runs locally on GPU
- Text-based PDF extraction is working
- A batch `.txt -> JSON + HTML` local test workflow is available
- Terminology dictionaries, article extraction from web pages, Redis caching, bilingual export, and user-correction learning are not implemented yet

## 2. Environment setup

Create an isolated Conda environment:

```powershell
conda create -n ln-translator python=3.11 -y
conda activate ln-translator
```

Recommended installation order:

```powershell
pip install fastapi "uvicorn[standard]" pydantic PyMuPDF pdfplumber readability-lxml beautifulsoup4 redis
pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu126
pip install numpy transformers sentencepiece sacremoses accelerate
```

Notes:

- The project now requires at least `torch>=2.6.0`
- Some Marian checkpoints still use `pytorch_model.bin`, and recent `transformers` builds refuse to load those weights with older Torch versions
- `requirements.txt` has been updated to reflect the current working constraints

## 3. Local model

The current default remote candidate is:

- `shun89/opus-mt-ja-zh`

For real offline deployment, the recommended approach is:

- Download the model manually
- Place it under `D:\models\opus-mt-ja-zh`
- Load it from disk via environment variables or the helper scripts

Set the environment variables:

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:HF_LOCAL_FILES_ONLY="1"
```

The local model directory should contain at least:

- `config.json`
- `source.spm`
- `target.spm`
- `vocab.json`
- `pytorch_model.bin` or `model.safetensors`

Check whether the model can be loaded:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-local-model.ps1
```

Expected output:

```text
python: D:\anaconda3\envs\ln-translator\python.exe
torch: 2.7.0+cu126
transformers: 5.5.0
model-load-ok
MarianTokenizer
MarianMTModel
```

## 4. Start the service

Use the helper script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local-service.ps1
```

If the model is stored elsewhere:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local-service.ps1 -ModelPath "X:\your\model\path"
```

After startup:

- `http://127.0.0.1:7860/`
- `http://127.0.0.1:7860/docs`
- `http://127.0.0.1:7860/health`

Health check:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7860/health"
```

Expected:

```json
{"status":"ok"}
```

Web UI:

- Open `http://127.0.0.1:7860/` in the browser
- Paste a Kakuyomu single-episode URL into the input box
- The UI will run the full chain: extraction -> translation -> local save
- After completion, switch between:
  - Reading mode
  - Side-by-side comparison mode
  - Sentence comparison mode

Saved output layout:

- `outputs/library/kakuyomu/<work-id>/<episode-id>/result.json`
- `outputs/library/kakuyomu/<work-id>/<episode-id>/bilingual.html`
- `outputs/library/kakuyomu/<work-id>/<episode-id>/reading.html`
- `outputs/library/kakuyomu/<work-id>/<episode-id>/index.html`
- `outputs/library/kakuyomu/<work-id>/index.html`

This keeps every episode stably grouped under its Kakuyomu work id and episode id instead of relying on filenames alone.

## 5. Japanese translation API

Endpoint:

- `POST /translate/ja`

Response shape:

```json
{
  "source_language": "ja",
  "target_language": "zh",
  "model_name": "D:\\models\\opus-mt-ja-zh",
  "device": "cuda:0",
  "paragraphs": [
    {
      "original_id": "p00001",
      "original_text": "<japanese paragraph 1>",
      "translated_text": "<translated chinese paragraph 1>"
    }
  ]
}
```

Current behavior:

- Input is split on blank lines
- Paragraph alignment is preserved in the response
- The service uses `cuda:0` when a CUDA GPU is available
- If GPU memory runs out, batch size is automatically reduced and retried

## 6. Windows PowerShell encoding note

If you call the API directly from Windows PowerShell, two problems may appear:

- Japanese text may be turned into `?` before it is sent
- UTF-8 response text may be displayed as mojibake in the terminal

That does not necessarily mean the service is broken. The common cause is the request/console encoding behavior of Windows PowerShell 5.x.

Do not judge translation quality only from terminal-rendered JSON. The reliable workflow is to save the response to a UTF-8 file and inspect it in VS Code.

Use the helper script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-translate.ps1
```

It will:

- Send the request as UTF-8
- Save the response to `outputs\translate-smoke.json`
- Print only the saved file path plus model/device information

To test your own input, save the Japanese text as a UTF-8 file such as `data\sample-ja.txt`, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-translate.ps1 -TextFile ".\data\sample-ja.txt"
```

Then open:

- `outputs\translate-smoke.json`

in VS Code to inspect the real Japanese and Chinese text.

## 7. Batch text-file translation

To test multiple Japanese text files in one run, use the batch script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data"
```

Behavior:

- Make sure the local service is already running at `http://127.0.0.1:7860`
- Input text files are read as UTF-8 by default
- A new batch folder is created under `outputs\batch` by default
- Recursively scans `InputPath` for `*.txt` files by default
- Writes three outputs per input file:
  - `JSON` with paragraph IDs, source text, translated text, and lightweight heading metadata
  - a bilingual side-by-side `HTML` page for validation
  - a merged `reading.html` page for continuous reading
- Every output directory also gets its own `index.html` and `index.json`
- Uses `outputs\batch` as the default output root
- Also creates:
  - `outputs\batch\index.json`
  - `outputs\batch\index.html`

To translate a single file:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data\chapter01.txt"
```

To disable recursive directory scanning:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -NoRecursive
```

To tune inference settings:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -BatchSize 4 -MaxNewTokens 192
```

To set an explicit batch/book folder name:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -RunName "book-01"
```

Then the outputs go under:

- `outputs\batch\book-01\...`

To flatten the output tree and customize filenames:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -NoPreserveStructure -NameTemplate "{index:03d}-{parent}-{stem}"
```

Current chapter-title source behavior:

- If a title-like line is detected near the beginning of the text, it is used as the chapter title
- Otherwise the workflow falls back to the text filename, such as `chapter01.txt -> chapter01`
- This is recorded in each JSON file via `title_source`
  - `heading` means the title came from detected body text
  - `filename` means it fell back to the filename

For example:

```json
{
  "source_title": "第1章 出会い",
  "translated_title": "第1章 遇见",
  "title_source": "heading"
}
```

or:

```json
{
  "source_title": "chapter01",
  "translated_title": "chapter01",
  "title_source": "filename"
}
```

About `index.html` versus directory hierarchy:

- The batch root still has an `index.html`
- But now each child directory also gets its own `index.html`
- That means the output structure itself reflects book / part / chapter hierarchy more clearly
- The root index helps you enter a batch
- Nested directory indexes help you browse within that batch at the correct hierarchy level

Outputs:

- Per-file JSON: `outputs\batch\<relative path>.json`
- Per-file bilingual HTML: `outputs\batch\<relative path>.html`
- Per-file reading HTML: `outputs\batch\<relative path>.reading.html`
- Batch index page: `outputs\batch\index.html`

Recommended validation flow:

- Open `outputs\batch\index.html` in VS Code or a browser
- Open `Reading` first to evaluate whole-piece readability
- Open `Bilingual` to verify paragraph alignment and spot obvious issues
- Or inspect the matching `.json` files for paragraph IDs, source text, and translations

What the new capabilities mean:

- `Preserve directory structure`
  - The output tree mirrors the input tree by default
  - Example: `data\vol1\chapter01.txt` becomes `outputs\batch\vol1\chapter01.json/html`
  - This is useful when you test many chapters or books at once and want to avoid filename collisions

- `Custom output naming`
  - You can control output base names via `-NameTemplate`
  - Example:
    ```powershell
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -NoPreserveStructure -NameTemplate "{index:03d}-{parent}-{stem}"
    ```
  - That produces names such as `001-vol1-chapter01.json`, which is useful for export, archiving, or flattening outputs

- `Lightweight heading detection`
  - The script applies simple rules to mark short title-like lines such as `第1章 出会い`, `序章`, or `Chapter 2` as `heading`
  - The reading page renders them as section headings, and the JSON output stores `kind`
  - This is not full document structure parsing. It is a practical layer for local testing

About `index.html`:

- Yes, the current `index.html` is already an output navigation page
- But it is not the same thing as preserving directory structure
- `index.html` solves browsing
- Structure preservation solves on-disk organization, collision avoidance, and source-to-output traceability
- They complement each other rather than replace each other

## 8. Kakuyomu web-body extraction

The project now includes a first Kakuyomu-specific extraction endpoint for single episode pages.

Endpoint:

- `POST /extract/web/kakuyomu`

Request body:

```json
{
  "url": "https://kakuyomu.jp/works/<work-id>/episodes/<episode-id>",
  "timeout_seconds": 30
}
```

Example response:

```json
{
  "provider": "kakuyomu",
  "url": "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154",
  "work_title": "Kakuyomu Random Searcher",
  "episode_title": "第2話　方法",
  "paragraphs": [
    {
      "paragraph_id": "web-p00001",
      "kind": "heading",
      "text": "第2話　方法"
    },
    {
      "paragraph_id": "web-p00002",
      "kind": "paragraph",
      "text": "さて，「すべての作品からランダムに選ぶ」からには，"
    }
  ]
}
```

Local test script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-kakuyomu.ps1 -EpisodeUrl "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154"
```

Default output:

- `outputs\kakuyomu-extract.json`

This becomes the foundation for the later step of feeding extracted web text into the local translation workflow.

If you want the full automatic chain "extract -> translate -> JSON + HTML output", use either the Web UI or the script below:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\translate-kakuyomu.ps1 -EpisodeUrl "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154"
```

Default behavior:

- Calls the new backend endpoint `POST /translate/web/kakuyomu`
- Extracts a single Kakuyomu episode and sends it directly into the local JA->ZH translation flow
- Generates these files under `outputs\kakuyomu\<work-title>-<timestamp>\`:
  - `index.html`
  - `<episode-title>.json`
  - `<episode-title>.html`
  - `<episode-title>.reading.html`

Meaning:

- `*.html` is the bilingual validation page with original text on the left and translation on the right
- `*.reading.html` is the merged translation reading page
- `index.html` is the entry page for the current episode output

Web UI-oriented backend endpoints:

- `POST /ui/api/kakuyomu/translate-save`
- `GET /ui/api/kakuyomu/history`
- `GET /ui/api/kakuyomu/result/{work_id}/{episode_id}`

The Web UI uses the stable storage layout below:

- `outputs/library/kakuyomu/<work-id>/<episode-id>/...`

If you want a fixed output folder name:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\translate-kakuyomu.ps1 -EpisodeUrl "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154" -RunName "kakuyomu-check"
```

This writes results to:

- `outputs\kakuyomu\kakuyomu-check\`

If you want to tune translation parameters:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\translate-kakuyomu.ps1 -EpisodeUrl "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154" -BatchSize 4 -MaxNewTokens 192
```

You can also call the endpoint directly:

- `POST /translate/web/kakuyomu`

Example request body:

```json
{
  "url": "https://kakuyomu.jp/works/<work-id>/episodes/<episode-id>",
  "timeout_seconds": 30,
  "batch_size": 8,
  "max_new_tokens": 256
}
```

Example response:

```json
{
  "provider": "kakuyomu",
  "source_language": "ja",
  "target_language": "zh",
  "url": "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154",
  "work_title": "Kakuyomu Random Searcher",
  "episode_title": "第2話　方法",
  "source_title": "第2話　方法",
  "translated_title": "第2话 方法",
  "title_source": "episode_title",
  "model_name": "D:\\models\\opus-mt-ja-zh",
  "device": "cuda:0",
  "paragraphs": [
    {
      "paragraph_id": "web-p00001",
      "kind": "heading",
      "original_text": "第2話　方法",
      "translated_text": "第2话 方法"
    }
  ]
}
```

## 9. PDF extraction API

Endpoint:

- `POST /extract/pdf`

Example request:

```powershell
$body = @{ file_path = "D:\docs\paper.pdf" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:7860/extract/pdf" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 6
```

Response shape:

```json
{
  "file_path": "D:\\docs\\paper.pdf",
  "paragraphs": [
    {
      "paragraph_id": "pdf-p00001",
      "page_number": 1,
      "kind": "heading",
      "section_title": "1 Introduction",
      "text": "1 Introduction"
    },
    {
      "paragraph_id": "pdf-p00002",
      "page_number": 1,
      "kind": "paragraph",
      "section_title": "1 Introduction",
      "text": "The first paragraph from the paper..."
    }
  ]
}
```

Notes:

- The extractor tries to preserve headings and attach later paragraphs to the current section
- It applies basic filtering for headers, footers, and page numbers
- Scanned PDFs and complex layouts still need later improvements

## 10. Suggested local directories

Recommended local directories:

- `models/`
- `data/`
- `outputs/`
- `downloads/`

Model files, source documents, and generated outputs in these folders should normally stay out of version control.

## 11. Current limitations

- Only Japanese plain-text translation and PDF extraction are implemented
- The English academic translation model is not integrated yet
- Kakuyomu single-episode pages now support the automatic chain: web extraction -> local translation -> JSON/HTML export
- Kakuyomu is still a single-episode feature for now; whole-work table-of-contents crawling, automatic multi-episode traversal, and batch web-job management are not implemented yet
- Syosetu is not adapted yet
- Terminology dictionaries, Redis caching, bilingual export, and user-correction learning remain future work
- Literary quality for light novels currently depends on the Marian checkpoint and may require a stronger model or a multi-step fallback later
- A browser-based Web UI is available now, but the sentence-comparison view is still heuristic punctuation-based splitting rather than true translation alignment
