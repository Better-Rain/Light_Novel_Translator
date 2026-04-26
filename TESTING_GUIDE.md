# 启动与测试指南

本文用于验证当前本地翻译工作台的主要链路，重点覆盖 Web UI、PDF 调试模式、保存历史和最近修复的安全/抽取行为。

## 1. 环境准备

推荐使用项目既有 conda 环境：

```powershell
conda activate D:\anaconda3\envs\ln-translator
cd "E:\Programs\Vscode Projects\Light_Novel_Translator"
```

常用模型环境变量：

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:EN_ZH_MODEL_PATH="D:\models\nllb-200-distilled-600M"
$env:HF_LOCAL_FILES_ONLY="1"
```

说明：

- 日译中走 `JA_ZH_MODEL_PATH`。
- 英译中走 `EN_ZH_MODEL_PATH`。
- `HF_LOCAL_FILES_ONLY=1` 会避免在线下载模型。

## 2. 不加载模型的快速验证

这个检查不会跑真实翻译模型，适合改代码后快速确认最近修复没有坏：

```powershell
& "D:\anaconda3\envs\ln-translator\python.exe" .\scripts\verify_local_fixes.py
```

如果本地没有样例 PDF，可跳过 PDF 检查：

```powershell
& "D:\anaconda3\envs\ln-translator\python.exe" .\scripts\verify_local_fixes.py --skip-pdf
```

预期现象：

- 输出 `[ok] storage id validation...`
- 输出 `[ok] saved-result APIs reject invalid identifiers`
- 有样例 PDF 时，输出 `first_page=12`、`last_page=451` 左右。
- 有样例 PDF 时，输出 debug document id suffix/schema 通过。

## 3. 启动 Web 服务

推荐直接用 Python 启动，便于同时配置英译中模型：

```powershell
$env:JA_ZH_MODEL_PATH="D:\models\opus-mt-ja-zh"
$env:EN_ZH_MODEL_PATH="D:\models\nllb-200-distilled-600M"
$env:HF_LOCAL_FILES_ONLY="1"
& "D:\anaconda3\envs\ln-translator\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 7860
```

启动成功后访问：

- `http://127.0.0.1:7860/`
- `http://127.0.0.1:7860/docs`
- `http://127.0.0.1:7860/health`

健康检查：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7860/health"
```

预期：

```json
{"status":"ok"}
```

## 4. Web UI PDF 调试模式验证

打开：

```text
http://127.0.0.1:7860/
```

操作：

1. 内容来源选择 `PDF 文献`。
2. PDF 文件路径填入本地样例 PDF 的绝对路径，例如：
   ```text
   E:\Programs\Vscode Projects\Light_Novel_Translator\The Death and Life of Great American Cities (Jane Jacobs) (z-library.sk, 1lib.sk, z-lib.sk).pdf
   ```
3. 源语言选择 `English`。
4. 为了快速验证，填写：
   - `PDF 调试页数上限`: `2`
   - `PDF 调试段落上限`: `8`
5. 点击 `开始处理`。

预期现象：

- 进度条会经历 PDF 提取、翻译、保存。
- 结果区域会出现 `PDF Debug` 元信息，例如 `pages 2, paragraphs 8, 8/2914 kept`。
- 历史记录里的该 PDF 项会带 `DEBUG` 标记。
- 保存目录名会包含类似 `-debug-p2-n8` 后缀，避免覆盖正式结果。
- 点击 `阅读模式 / 对比阅读 / 逐句对比` 都应能切换。

## 5. Web UI 阅读体验检查

建议用浏览器开发者工具切换这些窗口尺寸：

- `1366 x 768`
- `1280 x 720`
- `1112 x 834`
- `1024 x 768`
- `820 x 1180`
- `390 x 844`

重点观察：

- 约 1240px 以下时，左侧表单应变成上方单列布局，阅读区不再被 320px 侧栏挤窄。
- PDF 长文件名、document id、历史记录不应横向撑破页面。
- 进度状态变化应清楚可见。
- 对比阅读里的句子可以鼠标悬停、点击，也可以用 Tab 聚焦后按 Enter/Space 触发对应句高亮。

## 6. PDF 抽取质量观察点

当前样例 PDF 的关键预期：

- 正文起点应是第 12 页。
- 第一个块应为 `Introduction`。
- `Index` 之后的尾部索引/广告/出版社目录不应进入结果。
- `And`、`Third,`、`I`、`100.`、`Index` 不应作为 heading/chapter_heading 出现在结果里。

快速从命令行看抽取统计：

```powershell
$env:PYTHONIOENCODING="utf-8"
@'
from collections import Counter
from app.services.pdf_extractor import extract_pdf_paragraphs
pdf = r"E:\Programs\Vscode Projects\Light_Novel_Translator\The Death and Life of Great American Cities (Jane Jacobs) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
items = extract_pdf_paragraphs(pdf)
print("count", len(items))
print("first_page", items[0].page_number)
print("last_page", items[-1].page_number)
print("kind_counts", dict(Counter(item.kind for item in items)))
'@ | & "D:\anaconda3\envs\ln-translator\python.exe" -
```

当前预期近似：

```text
count 2914
first_page 12
last_page 451
kind_counts {'chapter_heading': 22, 'paragraph': 2865, 'heading': 27}
```

## 7. Kakuyomu 单章链路检查

在 Web UI 选择 `Kakuyomu 单章`，输入 Kakuyomu episode URL 后点击开始。

预期现象：

- 页面状态显示抓取、翻译、保存。
- 完成后可在三种阅读模式切换。
- 历史记录能加载已保存章节。
- 输出路径为：
  ```text
  outputs/library/kakuyomu/<work-id>/<episode-id>/
  ```

如果需要只测抽取：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-kakuyomu.ps1 -EpisodeUrl "https://kakuyomu.jp/works/<work-id>/episodes/<episode-id>"
```

## 8. 常见异常判断

- 模型加载失败：确认模型路径和 `HF_LOCAL_FILES_ONLY=1` 是否匹配本地模型目录。
- 英译中输出语言不对：确认 `EN_ZH_MODEL_PATH` 指向 NLLB/M2M100 类模型，并使用 `source_language=en`。
- PDF 任务太慢：先用 Web UI 的调试页数/段落上限缩小范围。
- Web UI 提示本地翻译 worker busy：说明已有任务正在运行，等待当前任务结束后再提交。
- 终端中文/日文显示乱码：优先打开保存的 UTF-8 JSON/HTML 文件，不要只看 PowerShell 输出。
