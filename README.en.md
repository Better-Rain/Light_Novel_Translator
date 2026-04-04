# Local Translation Service

This repository contains the first-phase local service for:

- Japanese to Chinese translation via `Helsinki-NLP/opus-mt-ja-zh`
- PDF paragraph extraction with paragraph IDs and heading preservation

## 1. Environment setup

```powershell
conda create -n ln-translator python=3.11 -y
conda activate ln-translator
pip install -r requirements.txt
```

If you want a CUDA-enabled PyTorch build for RTX 4090, install the matching wheel from the PyTorch index before `pip install -r requirements.txt`.

For a fully offline deployment, download the model to a local directory once, then point the service to that directory:

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:HF_LOCAL_FILES_ONLY="1"
```

## 2. Start the API

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 7860
```

Interactive docs:

- http://127.0.0.1:7860/docs

## 3. Translate Japanese text

```powershell
curl -X POST "http://127.0.0.1:7860/translate/ja" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"<japanese paragraph 1>\n\n<japanese paragraph 2>\",\"batch_size\":16,\"max_new_tokens\":256}"
```

Response shape:

```json
{
  "source_language": "ja",
  "target_language": "zh",
  "model_name": "Helsinki-NLP/opus-mt-ja-zh",
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

## 4. Extract PDF paragraphs

```powershell
curl -X POST "http://127.0.0.1:7860/extract/pdf" `
  -H "Content-Type: application/json" `
  -d "{\"file_path\":\"D:\\docs\\paper.pdf\"}"
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

## Notes

- The translation endpoint splits input on blank lines to preserve paragraph alignment.
- The model is loaded lazily on first use. If `HF_LOCAL_FILES_ONLY=1`, the service will only read the model from local disk.
- On CUDA, the service uses `float16`, TF32, and batched generation. If GPU memory is insufficient, it automatically reduces batch size.
- PDF heading detection is heuristic and works best on born-digital academic PDFs.

