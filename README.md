# 本地翻译服务

英文版说明见 [README.en.md](README.en.md)。

这个仓库目前实现的是第一阶段能力：

- 日语到中文翻译，使用 `Helsinki-NLP/opus-mt-ja-zh`
- PDF 段落提取，保留段落 ID 与章节标题

## 1. 环境准备

```powershell
conda create -n ln-translator python=3.11 -y
conda activate ln-translator
pip install -r requirements.txt
```

如果你的部署环境是 RTX 4090，建议先安装对应 CUDA 版本的 PyTorch，再执行 `pip install -r requirements.txt`。

如果要实现完全离线运行，先把模型下载到本地目录，再设置环境变量：

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:HF_LOCAL_FILES_ONLY="1"
```

## 2. 启动服务

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 7860
```

接口文档地址：

- http://127.0.0.1:7860/docs

## 3. 日语翻译接口

接口：`POST /translate/ja`

请求示例：

```powershell
curl -X POST "http://127.0.0.1:7860/translate/ja" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"<日语段落 1>\n\n<日语段落 2>\",\"batch_size\":16,\"max_new_tokens\":256}"
```

返回格式：

```json
{
  "source_language": "ja",
  "target_language": "zh",
  "model_name": "Helsinki-NLP/opus-mt-ja-zh",
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

说明：

- 输入文本按空行分段，接口会保留原文与译文的段落对应关系。
- GPU 可用时默认使用 `cuda:0`。
- 默认使用批量推理，显存不足时会自动降低批大小重试。

## 4. PDF 提取接口

接口：`POST /extract/pdf`

请求示例：

```powershell
curl -X POST "http://127.0.0.1:7860/extract/pdf" `
  -H "Content-Type: application/json" `
  -d "{\"file_path\":\"D:\\docs\\paper.pdf\"}"
```

返回格式：

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

- 会尽量保留章节标题，并将后续段落挂到当前章节标题下。
- 页眉、页脚和页码会做基础过滤，但识别仍然是启发式规则。
- 对扫描版 PDF 或排版异常的论文，可能还需要后续专项优化。

## 5. 仓库建议

仓库已新增以下 Git 基础文件：

- `.gitignore`：忽略虚拟环境、模型权重、缓存、输出文件、Redis 数据和 IDE 配置
- `.gitattributes`：统一文本文件属性，并将 PDF、模型权重等标记为二进制文件

建议把本地模型、原始 PDF、导出结果统一放在以下目录中，这些目录默认不会被提交：

- `models/`
- `data/`
- `outputs/`
- `downloads/`

## 6. 当前限制

- 模型第一次加载会比较慢。
- 当前只实现了日语纯文本翻译和 PDF 提取，还没有接入网页正文提取、术语库、缓存和用户修正学习。
- PDF 标题识别与段落合并规则目前偏通用，后续可以针对学术论文格式继续细化。
