# 本地翻译与阅读工作台

英文版说明见 [README.en.md](README.en.md)。

这是一个本地运行的翻译与阅读工作台，当前主要处理两类输入：

- Kakuyomu 单章轻小说网页 URL
- 本地 PDF 文献，支持英文或日文来源

核心链路是：

```text
抽取 -> 分段 -> 翻译成中文 -> 保存 JSON/HTML -> 在 Web UI 中阅读
```

保存结果默认写入 `outputs/`，不使用数据库。

## 1. 当前能力

- `FastAPI + Uvicorn` 后端。
- `/translate/ja` 日译中纯文本接口。
- `/translate/en` 英译中纯文本接口，支持本地 NLLB/M2M100 类模型的 source token 和 forced BOS token。
- Kakuyomu 单章正文抽取、翻译、保存和历史读取。
- PDF 段落抽取、翻译、保存、历史读取和已保存结果加载。
- Web UI 支持 Kakuyomu / PDF 双来源。
- Web UI 支持阅读模式、对比阅读、逐句对比。
- PDF 支持调试页数和调试段落上限，便于快速验证长文档。
- PDF 抽取器提供命令行调试报告，便于查看过滤、降级、尾部截断等决策。
- 输出为本地 JSON/HTML 文件，主要目录为：
  - `outputs/library/kakuyomu/<work-id>/<episode-id>/`
  - `outputs/library/pdf/<document-id>/`

## 2. 环境准备

推荐使用项目既有 conda 环境：

```powershell
conda activate D:\anaconda3\envs\ln-translator
cd "E:\Programs\Vscode Projects\Light_Novel_Translator"
```

如果需要重新创建环境：

```powershell
conda create -n ln-translator python=3.11 -y
conda activate ln-translator
pip install fastapi "uvicorn[standard]" pydantic PyMuPDF pdfplumber readability-lxml beautifulsoup4 redis
pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu126
pip install numpy transformers sentencepiece sacremoses accelerate
```

说明：

- 当前项目至少需要 `torch>=2.6.0`。
- 部分 Marian 模型仍使用 `pytorch_model.bin`，新版 `transformers` 在 `torch<2.6` 时会拒绝加载这类权重。
- `requirements.txt` 已同步当前可用约束。

## 3. 本地模型

常用本地模型路径：

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:EN_ZH_MODEL_PATH="D:\models\nllb-200-distilled-600M"
$env:HF_LOCAL_FILES_ONLY="1"
```

日译中推荐模型目录至少包含：

- `config.json`
- `source.spm`
- `target.spm`
- `vocab.json`
- `pytorch_model.bin` 或 `model.safetensors`

英译中当前按 NLLB/M2M100 类模型处理，推荐通过 `EN_ZH_MODEL_PATH` 指向本地目录。

检查日译中模型是否可加载：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-local-model.ps1
```

## 4. 启动服务

推荐直接用项目 Python 启动，便于同时设置英译中模型：

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:EN_ZH_MODEL_PATH="D:\models\nllb-200-distilled-600M"
$env:HF_LOCAL_FILES_ONLY="1"
& "D:\anaconda3\envs\ln-translator\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 7860
```

启动后访问：

- `http://127.0.0.1:7860/`
- `http://127.0.0.1:7860/docs`
- `http://127.0.0.1:7860/health`

健康检查：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7860/health"
```

预期结果：

```json
{"status":"ok"}
```

## 5. Web UI 使用

打开：

```text
http://127.0.0.1:7860/
```

Kakuyomu 单章：

1. 内容来源选择 `Kakuyomu 单章`。
2. 填入 Kakuyomu episode URL。
3. 点击 `开始处理`。
4. 完成后可在阅读模式、对比阅读、逐句对比之间切换。

PDF 文献：

1. 内容来源选择 `PDF 文献`。
2. 填入本地 PDF 绝对路径。
3. 选择源语言 `English` 或 `Japanese`。
4. 长文档验证时可填写 `PDF 调试页数上限` 和 `PDF 调试段落上限`。
5. 点击 `开始处理`。

PDF 调试模式不会覆盖正式结果。启用调试上限后，`document_id` 会附加类似 `-debug-p2-n8` 的后缀，历史记录也会显示 `DEBUG` 标记。

## 6. 主要 API

纯文本翻译：

- `POST /translate/ja`
- `POST /translate/en`

Kakuyomu：

- `POST /extract/web/kakuyomu`
- `POST /translate/web/kakuyomu`
- `POST /ui/api/kakuyomu/translate-save`
- `GET /ui/api/kakuyomu/history`
- `GET /ui/api/kakuyomu/result/{work_id}/{episode_id}`

PDF：

- `POST /extract/pdf`
- `POST /translate/pdf`
- `POST /ui/api/pdf/translate-save`
- `GET /ui/api/pdf/history`
- `GET /ui/api/pdf/result/{document_id}`

PDF 翻译请求可包含调试上限：

```json
{
  "file_path": "D:\\docs\\paper.pdf",
  "source_language": "en",
  "debug_max_pages": 2,
  "debug_max_paragraphs": 24
}
```

## 7. 输出结构

Kakuyomu 保存目录：

```text
outputs/library/kakuyomu/<work-id>/<episode-id>/
```

常见文件：

- `result.json`
- `bilingual.html`
- `reading.html`
- `index.html`

PDF 保存目录：

```text
outputs/library/pdf/<document-id>/
```

常见文件：

- `result.json`
- `bilingual.html`
- `reading.html`
- `index.html`

## 8. 快速验证

不加载真实翻译模型的本地回归检查：

```powershell
& "D:\anaconda3\envs\ln-translator\python.exe" .\scripts\verify_local_fixes.py
```

如果本地没有样例 PDF：

```powershell
& "D:\anaconda3\envs\ln-translator\python.exe" .\scripts\verify_local_fixes.py --skip-pdf
```

PDF 抽取决策调试报告：

```powershell
& "D:\anaconda3\envs\ln-translator\python.exe" .\scripts\debug_pdf_extraction.py ".\The Death and Life of Great American Cities (Jane Jacobs) (z-library.sk, 1lib.sk, z-lib.sk).pdf" --output outputs\pdf_extraction_debug_report.json
```

报告会写出页级过滤原因、保留/丢弃/降级计数、样本文本、正文起点和尾部截断页。生成文件位于 `outputs/`，默认不提交到仓库。

更完整的手动验证步骤见 [TESTING_GUIDE.md](TESTING_GUIDE.md)。

## 9. PDF 抽取现状

当前抽取器会做这些处理：

- 使用 PyMuPDF 读取文本块。
- 清理软连字符、零宽字符和多余空白。
- 估算正文字号。
- 过滤重复页眉、页脚、页码和明显 OCR 噪声。
- 自动识别前置内容，样例 PDF 正文起点约为第 12 页。
- 区分 `chapter_heading`、`heading` 和 `paragraph`。
- 对疑似正文误判标题做降级。
- 识别样例 PDF 尾部索引/广告等 end matter，避免进入正文结果。

OCR 或复杂排版 PDF 仍需要继续优化，尤其是章节结构和目录质量。

## 10. 当前限制

- Kakuyomu 仍是单章链路，还没有整本目录抓取和自动连章。
- PDF 逐句对比仍基于标点切分，不是真正语义对齐。
- 日文 PDF 的前置内容和标题判断还偏英文规则，可靠性低于英文文献。
- 术语库、Redis 缓存、用户修正学习仍是后续阶段。
- 翻译质量取决于本地模型本身，长文档正式翻译会明显消耗 GPU/CPU 时间。

## 11. 本地目录建议

建议把模型、原始文档和生成结果放在这些目录，并保持不提交：

- `models/`
- `data/`
- `outputs/`
- `downloads/`
