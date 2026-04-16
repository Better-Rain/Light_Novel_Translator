# 本地翻译服务

英文版说明见 [README.en.md](README.en.md)。

这个仓库当前实现的是第一阶段能力：

- 日语到中文翻译接口，当前默认候选模型为 `shun89/opus-mt-ja-zh`
- PDF 段落提取接口，保留段落 ID、页码、标题与正文关系

## 1. 当前状态

- 后端框架已经是 `FastAPI + Uvicorn`
- 日语翻译链路已能在本地 GPU 上运行
- PDF 文本型文档提取已可用
- 已提供批量 `.txt -> JSON + HTML` 本地测试流程
- 术语库、网页正文提取、Redis 缓存、双语导出、用户修正学习还没有接入

## 2. 环境准备

建议使用 `conda` 创建独立环境：

```powershell
conda create -n ln-translator python=3.11 -y
conda activate ln-translator
```

推荐依赖安装顺序：

```powershell
pip install fastapi "uvicorn[standard]" pydantic PyMuPDF pdfplumber readability-lxml beautifulsoup4 redis
pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu126
pip install numpy transformers sentencepiece sacremoses accelerate
```

说明：

- 当前项目至少需要 `torch>=2.6.0`
- 原因是部分 Marian 模型仍使用 `pytorch_model.bin`，而新版 `transformers` 在 `torch<2.6` 时会拒绝加载这类权重
- `requirements.txt` 已同步更新为当前可用约束

## 3. 本地模型

当前默认远程候选是：

- `shun89/opus-mt-ja-zh`

推荐实际部署方式：

- 手动下载模型后放到 `D:\models\opus-mt-ja-zh`
- 然后通过环境变量或脚本从本地目录加载

设置环境变量：

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:HF_LOCAL_FILES_ONLY="1"
```

模型目录至少应包含：

- `config.json`
- `source.spm`
- `target.spm`
- `vocab.json`
- `pytorch_model.bin` 或 `model.safetensors`

检查模型是否可加载：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-local-model.ps1
```

通过时应看到类似输出：

```text
python: D:\anaconda3\envs\ln-translator\python.exe
torch: 2.7.0+cu126
transformers: 5.5.0
model-load-ok
MarianTokenizer
MarianMTModel
```

## 4. 启动服务

推荐使用项目自带脚本启动：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local-service.ps1
```

如果模型路径不是默认值：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local-service.ps1 -ModelPath "X:\your\model\path"
```

启动后可访问：

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

Web UI 使用方式：

- 在浏览器打开 `http://127.0.0.1:7860/`
- 把 Kakuyomu 单章 URL 粘贴到输入框
- UI 会自动执行整条链路：抓取 -> 翻译 -> 本地保存
- 完成后可以在以下模式之间切换：
  - 阅读模式
  - 对比阅读
  - 逐句对比

保存目录结构：

- `outputs/library/kakuyomu/<work-id>/<episode-id>/result.json`
- `outputs/library/kakuyomu/<work-id>/<episode-id>/bilingual.html`
- `outputs/library/kakuyomu/<work-id>/<episode-id>/reading.html`
- `outputs/library/kakuyomu/<work-id>/<episode-id>/index.html`
- `outputs/library/kakuyomu/<work-id>/index.html`

这样每一章都会稳定归档到对应的作品 ID 和章节 ID 之下，不依赖文件名猜测归属关系。

## 5. 日语翻译接口

接口：

- `POST /translate/ja`

返回结构：

```json
{
  "source_language": "ja",
  "target_language": "zh",
  "model_name": "D:\\models\\opus-mt-ja-zh",
  "device": "cuda:0",
  "paragraphs": [
    {
      "original_id": "p00001",
      "original_text": "<日语段落 1>",
      "translated_text": "<中文译文段落 1>"
    }
  ]
}
```

当前行为：

- 输入会按空行切分段落
- 返回值会保留段落级对齐关系
- GPU 可用时默认使用 `cuda:0`
- 显存不足时会自动减小批大小重试

## 6. Windows PowerShell 编码说明

如果你在 Windows PowerShell 中直接调用接口，可能会出现这两类现象：

- 请求中的日文在发出前被编码成 `?`
- 响应中的 UTF-8 文本在控制台里显示成乱码

这不一定代表服务异常，常见原因是 PowerShell 5.x 的请求编码和控制台显示链路不稳定。

不建议用“直接在控制台里看 JSON 文本”的方式判断翻译质量。更稳的做法是把响应写入 UTF-8 文件，再在 VS Code 中查看。

推荐使用项目自带测试脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-translate.ps1
```

它会：

- 用 UTF-8 正确发送请求
- 把响应写到 `outputs\translate-smoke.json`
- 在终端里只输出文件路径和设备信息

如果要测试你自己的文本，先把文本保存成 UTF-8 文件，例如 `data\sample-ja.txt`，然后运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-translate.ps1 -TextFile ".\data\sample-ja.txt"
```

随后直接在 VS Code 中打开：

- `outputs\translate-smoke.json`

这样看到的内容才是可靠的原文和译文。

## 7. 批量文本文件翻译

如果你想一次测试一个目录中的多份日文文本，推荐使用批量脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data"
```

行为说明：

- 运行前请先确认本地服务已经启动在 `http://127.0.0.1:7860`
- 输入文本文件默认按 UTF-8 读取
- 默认会在 `outputs\batch` 下新建一个“批次目录”，目录名默认是 `输入名-时间戳`
- 默认会递归查找 `InputPath` 下所有 `*.txt` 文件
- 每个输入文件都会生成三类结果：
  - `JSON`：保留段落 ID、原文、译文和简单章节识别结果
  - `HTML`：左右对照验证页，适合开发阶段查对齐和查漏译
  - `reading.html`：合并译文阅读页，适合快速通读整篇
- 每一层输出目录都会生成自己的 `index.html` 和 `index.json`
- 输出根目录默认是 `outputs\batch`
- 会额外生成总索引：
  - `outputs\batch\index.json`
  - `outputs\batch\index.html`

如果你只想翻译单个文件：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data\chapter01.txt"
```

如果你不想递归扫描子目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -NoRecursive
```

如果想调整推理参数：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -BatchSize 4 -MaxNewTokens 192
```

输出内容：

- 单文件结果：`outputs\batch\<相对路径>.json`
- 对照 HTML：`outputs\batch\<相对路径>.html`
- 阅读 HTML：`outputs\batch\<相对路径>.reading.html`
- 总览页：`outputs\batch\index.html`

推荐验证方式：

- 在 VS Code 中直接打开 `outputs\batch\index.html`
- 先点 `Reading` 看整篇阅读体验
- 再点 `Bilingual` 看段落对应是否正确
- 或打开对应的 `.json` 文件检查段落 ID、原文和译文

几个新增能力的含义：

- `支持目录结构保留`
  - 指输出目录默认会镜像输入目录结构
  - 例如输入是 `data\vol1\chapter01.txt`，输出会落到 `outputs\batch\vol1\chapter01.json/html`
  - 这样在多卷、多章节、多来源文本并行测试时，不容易把同名文件混在一起

- `自定义输出命名`
  - 指你可以通过 `-NameTemplate` 控制输出文件基名
  - 例如：
    ```powershell
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -NoPreserveStructure -NameTemplate "{index:03d}-{parent}-{stem}"
    ```
  - 这样会生成像 `001-vol1-chapter01.json` 这样的文件名，适合导出、归档或避免重名

- `简单章节识别`
  - 指脚本会用一组轻量规则，把像 `第1章 出会い`、`序章`、`Chapter 2` 这类短标题行标记成 `heading`
  - 阅读页会把这些行渲染成章节标题，JSON 里也会写入 `kind`
  - 它不是完整文档结构分析，只是为批量本地测试提供一个足够实用的轻量层

关于你提到的 `index.html`：

- 对，当前的 `index.html` 本质上就是一个输出导航页
- 但它和“目录结构保留”不是同一层概念
- `index.html` 解决的是“怎么点进去看结果”
- “目录结构保留”解决的是“磁盘上的输出文件如何组织、如何避免重名、如何保持和输入源一一对应”
- 两者结合起来，既方便浏览，也方便后续做自动处理或归档

接口：

- `POST /extract/pdf`

请求示例：

```powershell
$body = @{ file_path = "D:\docs\paper.pdf" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:7860/extract/pdf" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 6
```

返回结构：

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

说明：

- 会尽量保留章节标题并挂载后续段落
- 页眉、页脚、页码会做基础过滤
- 对扫描版 PDF 或复杂排版 PDF 仍需要后续增强

## 10. 仓库建议

建议本地统一使用这些目录：

- `models/`
- `data/`
- `outputs/`
- `downloads/`

这些目录中的模型、原始文档和输出结果默认不建议提交到仓库。

## 11. 当前限制

- 当前只实现了日语纯文本翻译和 PDF 提取
- 英文论文翻译模型还没有接入
- Kakuyomu 单章正文已经支持自动链路：网页抓取 -> 本地翻译 -> JSON/HTML 导出
- Kakuyomu 当前仍然是“单章节”能力，还没有扩展到整书目录抓取、自动连章遍历和批量网页任务管理
- Syosetu 还没有单独适配
- 术语库、Redis 缓存、双语导出和用户修正学习仍是后续阶段
- 日轻风格保真度目前取决于现有 Marian 模型，后续可能需要更高质量模型或两段式翻译方案
- 现在已经提供浏览器 Web UI，但“逐句对比”仍然是基于标点切分的启发式对齐，不是真正的翻译句对齐
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -BatchSize 4 -MaxNewTokens 192
```

如果你想手动指定这次批量任务的书目/批次目录名：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -RunName "book-01"
```

这样结果会落到：

- `outputs\batch\book-01\...`

如果你想扁平化输出，并自定义文件名：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\batch-translate.ps1 -InputPath ".\data" -NoPreserveStructure -NameTemplate "{index:03d}-{parent}-{stem}"
```

这样适合导出、归档，或者避免不同目录里的同名章节互相覆盖。

章节标题目前的来源：

- 如果正文前几段里识别到像 `第1章 出会い`、`序章`、`Chapter 2` 这样的标题行，就优先把它当作章节标题
- 如果没有识别到标题行，就回退到 `txt` 文件名，例如 `chapter01.txt -> chapter01`
- 这一点会写进每个结果 JSON 的 `title_source`
  - `heading` 表示来自正文标题
  - `filename` 表示来自文件名回退

例如：

```json
{
  "source_title": "第1章 出会い",
  "translated_title": "第1章 遇见",
  "title_source": "heading"
}
```

或者：

```json
{
  "source_title": "chapter01",
  "translated_title": "chapter01",
  "title_source": "filename"
}
```

关于你提到的 `index.html` 和层级关系：

- 现在不只是批次根目录有一个 `index.html`
- 每个子目录也会生成自己的 `index.html`
- 例如如果输入是：
  - `data\book-a\chapter01.txt`
  - `data\book-a\part1\chapter02.txt`
- 那输出会类似：
  - `outputs\batch\book-a-20260405-211000\index.html`
  - `outputs\batch\book-a-20260405-211000\part1\index.html`
- 这样你进入某一层目录时，就能直接看到这一层的章节和下一层子目录，更符合书目/卷/章节的层级感

推荐验证方式：

- 先打开批次根目录下的 `index.html`
- 如果有子目录，再点进对应子目录的 `index.html`
- 阅读时优先看 `Reading`
- 对齐检查时再看 `Bilingual`

## 8. Kakuyomu 网页正文提取

目前已经加入一个 Kakuyomu 单章正文提取接口，适合作为网页正文功能的第一步。

接口：

- `POST /extract/web/kakuyomu`

请求体：

```json
{
  "url": "https://kakuyomu.jp/works/<work-id>/episodes/<episode-id>",
  "timeout_seconds": 30
}
```

返回结构示例：

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

本地测试脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-kakuyomu.ps1 -EpisodeUrl "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154"
```

默认输出：

- `outputs\kakuyomu-extract.json`

这个结果可以作为下一步“网页正文 -> 本地翻译”的输入基础。

如果你想直接完成“抽取 -> 翻译 -> JSON + HTML 导出”的自动链路，可以使用 Web UI，或者使用下面的脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\translate-kakuyomu.ps1 -EpisodeUrl "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154"
```

默认行为：

- 调用新的后端接口 `POST /translate/web/kakuyomu`
- 先抓取 Kakuyomu 单章正文，再直接送入本地日中翻译
- 在 `outputs\kakuyomu\<work-title>-<timestamp>\` 下生成：
  - `index.html`
  - `<episode-title>.json`
  - `<episode-title>.html`
  - `<episode-title>.reading.html`

其中：

- `*.html` 是原文在左、译文在右的双栏核对页，适合查实翻译问题
- `*.reading.html` 是只看译文的阅读页
- `index.html` 是当前章节输出的入口页

面向 Web UI 的后端接口：

- `POST /ui/api/kakuyomu/translate-save`
- `GET /ui/api/kakuyomu/history`
- `GET /ui/api/kakuyomu/result/{work_id}/{episode_id}`

Web UI 默认使用稳定存储目录：

- `outputs/library/kakuyomu/<work-id>/<episode-id>/...`

如果你想固定输出目录名：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\translate-kakuyomu.ps1 -EpisodeUrl "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154" -RunName "kakuyomu-check"
```

这样结果会落到：

- `outputs\kakuyomu\kakuyomu-check\`

如果你想调节翻译参数：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\translate-kakuyomu.ps1 -EpisodeUrl "https://kakuyomu.jp/works/16816700429269320184/episodes/16816700429269681154" -BatchSize 4 -MaxNewTokens 192
```

也可以直接调用接口：

- `POST /translate/web/kakuyomu`

请求体示例：

```json
{
  "url": "https://kakuyomu.jp/works/<work-id>/episodes/<episode-id>",
  "timeout_seconds": 30,
  "batch_size": 8,
  "max_new_tokens": 256
}
```

返回结构示例：

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

## 9. PDF 提取接口
