from __future__ import annotations

import json


def render_web_ui_html(
    *,
    initial_provider: str | None = None,
    initial_work_id: str | None = None,
    initial_episode_id: str | None = None,
    initial_document_id: str | None = None,
) -> str:
    initial_payload = json.dumps(
        {
            "provider": initial_provider or "",
            "workId": initial_work_id or "",
            "episodeId": initial_episode_id or "",
            "documentId": initial_document_id or "",
        },
        ensure_ascii=False,
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Light Novel Translator</title>
  <style>
    :root {{
      --bg: #efe6d9;
      --paper: #fffaf3;
      --panel: rgba(255, 250, 243, 0.94);
      --ink: #201917;
      --muted: #6d625a;
      --line: #d8cab8;
      --accent: #0b6468;
      --accent-soft: #d6ebeb;
      --accent-strong: #7e2b1d;
      --shadow: 0 18px 40px rgba(60, 41, 25, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Segoe UI", "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(255, 245, 228, 0.95), transparent 35%),
        linear-gradient(180deg, #f8f2e8 0%, var(--bg) 100%);
    }}
    .page {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 24px 18px 36px;
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      gap: 18px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }}
    .sidebar {{
      position: sticky;
      top: 18px;
      align-self: start;
      padding: 18px;
    }}
    .main {{
      min-width: 0;
      display: grid;
      gap: 18px;
    }}
    h1, h2, h3, p {{
      margin: 0;
    }}
    .eyebrow {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .hero {{
      padding: 22px;
      display: grid;
      gap: 12px;
    }}
    .hero h1 {{
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1.08;
    }}
    .hero p {{
      color: var(--muted);
      line-height: 1.6;
    }}
    .form-grid {{
      display: grid;
      gap: 12px;
      margin-top: 8px;
    }}
    label {{
      display: grid;
      gap: 6px;
      font-size: 14px;
      color: var(--muted);
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      font: inherit;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.88);
    }}
    .inline-fields {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .field-hint {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }}
    .source-panel {{
      display: grid;
      gap: 12px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.58);
    }}
    .source-panel.hidden {{
      display: none;
    }}
    button {{
      border: 0;
      border-radius: 14px;
      padding: 12px 16px;
      font: inherit;
      cursor: pointer;
      background: var(--accent);
      color: white;
      font-weight: 700;
    }}
    button:disabled {{
      opacity: 0.7;
      cursor: wait;
    }}
    .secondary-btn {{
      background: rgba(11, 100, 104, 0.1);
      color: var(--accent);
    }}
    .status {{
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      color: var(--muted);
      line-height: 1.5;
    }}
    .status.error {{
      border-color: #d29c96;
      color: #7d2d23;
      background: rgba(255, 239, 237, 0.9);
    }}
    .progress-block {{
      display: grid;
      gap: 8px;
    }}
    .progress-track {{
      width: 100%;
      height: 12px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(11, 100, 104, 0.12);
      border: 1px solid rgba(11, 100, 104, 0.18);
    }}
    .progress-fill {{
      width: 0%;
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--accent), #2c8f93);
      transition: width 0.25s ease;
    }}
    .progress-text {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}
    .history {{
      margin-top: 18px;
      display: grid;
      gap: 10px;
    }}
    .history-item {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.68);
      display: grid;
      gap: 8px;
    }}
    .history-item strong {{
      font-size: 14px;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }}
    .history-item small {{
      color: var(--muted);
      line-height: 1.5;
      overflow-wrap: anywhere;
    }}
    .history-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .history-actions button, .history-actions a {{
      border-radius: 12px;
      padding: 8px 10px;
      font-size: 13px;
      text-decoration: none;
    }}
    .result-header {{
      padding: 22px;
      display: grid;
      gap: 14px;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
    }}
    .meta-card {{
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.68);
      padding: 12px 14px;
    }}
    .meta-card span {{
      overflow-wrap: anywhere;
    }}
    .meta-card strong {{
      display: block;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .mode-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .mode-btn.active {{
      background: var(--accent-strong);
      color: white;
    }}
    .view {{
      display: none;
      padding: 0 22px 22px;
    }}
    .view.active {{
      display: block;
    }}
    .reading-shell {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.74);
      padding: 24px;
    }}
    .reading-heading {{
      margin: 26px 0 10px;
      padding-top: 6px;
    }}
    .reading-heading h3 {{
      font-size: 24px;
      line-height: 1.2;
    }}
    .source-note {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }}
    .reading-paragraph {{
      margin: 0;
      font-size: 20px;
      line-height: 1.9;
    }}
    .reading-paragraph + .reading-paragraph {{
      margin-top: 1.1em;
    }}
    .pair-list {{
      display: grid;
      gap: 14px;
    }}
    .pair-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.74);
      padding: 16px;
      display: grid;
      gap: 12px;
    }}
    .pair-meta {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .tag {{
      display: inline-block;
      border-radius: 999px;
      padding: 6px 10px;
      background: #eee0d0;
      color: #6d3626;
      font-size: 12px;
      font-family: Consolas, "Cascadia Code", monospace;
    }}
    .pair-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .pair-panel {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.84);
    }}
    .pair-panel h3 {{
      font-size: 13px;
      color: var(--muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }}
    .pair-panel p {{
      line-height: 1.8;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .compare-shell {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .compare-column {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.74);
      padding: 22px;
      max-height: min(74vh, 1080px);
      overflow: auto;
      scroll-behavior: smooth;
    }}
    .compare-column h3 {{
      font-size: 14px;
      color: var(--muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin: 0 0 14px;
      position: sticky;
      top: 0;
      padding: 0 0 10px;
      background: linear-gradient(180deg, rgba(255, 250, 243, 0.98), rgba(255, 250, 243, 0.86));
      backdrop-filter: blur(4px);
    }}
    .compare-article {{
      font-size: 19px;
      line-height: 1.9;
    }}
    .compare-heading {{
      margin: 22px 0 12px;
    }}
    .compare-heading h4 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
    }}
    .compare-paragraph {{
      margin: 0;
    }}
    .compare-paragraph + .compare-paragraph {{
      margin-top: 1.05em;
    }}
    .compare-sentence {{
      display: inline;
      padding: 0.06em 0.08em;
      border-radius: 0.4em;
      cursor: pointer;
      scroll-margin-block: 42vh;
      transition: background-color 0.12s ease, color 0.12s ease;
    }}
    .compare-sentence:focus-visible {{
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }}
    .compare-sentence.active {{
      background: rgba(126, 43, 29, 0.14);
      color: #5a2016;
    }}
    .sentence-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.74);
      padding: 16px;
      margin-bottom: 14px;
      display: grid;
      gap: 12px;
    }}
    .sentence-table {{
      display: grid;
      gap: 8px;
    }}
    .sentence-row {{
      display: grid;
      grid-template-columns: 56px 1fr 1fr;
      gap: 10px;
      align-items: start;
    }}
    .sentence-index {{
      color: var(--muted);
      font-size: 12px;
      padding-top: 2px;
    }}
    .sentence-cell {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.84);
      padding: 12px;
      line-height: 1.7;
      word-break: break-word;
      white-space: pre-wrap;
    }}
    .toolbar-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .toolbar-links a {{
      text-decoration: none;
      color: var(--accent);
      font-weight: 600;
    }}
    .debug-badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 5px 9px;
      background: #f1ded5;
      color: #7e2b1d;
      font-size: 12px;
      font-weight: 700;
    }}
    .empty {{
      padding: 36px 22px 28px;
      color: var(--muted);
      line-height: 1.7;
    }}
    @media (max-width: 1240px) {{
      .page {{
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        position: static;
      }}
    }}
    @media (max-width: 820px) {{
      .pair-grid, .sentence-row, .compare-shell {{
        grid-template-columns: 1fr;
      }}
      .sentence-index {{
        padding-top: 0;
      }}
      .inline-fields {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <aside class="panel sidebar">
      <span class="eyebrow">Web UI</span>
      <div class="hero">
        <h1>\u672c\u5730\u7ffb\u8bd1\u5de5\u4f5c\u53f0</h1>
        <p>\u5f53\u524d\u53ef\u4ee5\u8dd1\u4e24\u6761\u94fe\u8def\uff1aKakuyomu \u5355\u7ae0 URL \u6293\u53d6\uff0c\u6216\u8005\u672c\u5730 PDF \u6587\u732e\u63d0\u53d6\u4e0e\u7ffb\u8bd1\u3002\u7ed3\u679c\u4f1a\u4fdd\u5b58\u5230\u672c\u5730\uff0c\u7136\u540e\u5728\u5f53\u524d\u9875\u5207\u6362\u9605\u8bfb\u3001\u5bf9\u6bd4\u9605\u8bfb\u548c\u9010\u53e5\u5bf9\u6bd4\u3002</p>
      </div>
      <form id="translate-form" class="form-grid">
        <label>
          \u5185\u5bb9\u6765\u6e90
          <select id="source-kind" name="source_kind">
            <option value="kakuyomu">Kakuyomu \u5355\u7ae0</option>
            <option value="pdf">PDF \u6587\u732e</option>
          </select>
        </label>
        <div id="source-panel-kakuyomu" class="source-panel">
          <label>
            Kakuyomu \u5355\u7ae0 URL
            <input id="episode-url" name="url" type="url" placeholder="https://kakuyomu.jp/works/.../episodes/..." />
          </label>
          <div class="field-hint">\u4f1a\u6267\u884c\uff1a\u6293\u53d6 -> \u7ffb\u8bd1 -> \u4fdd\u5b58 -> \u5728\u9875\u5185\u9884\u89c8\u3002</div>
        </div>
        <div id="source-panel-pdf" class="source-panel hidden">
          <label>
            PDF \u6587\u4ef6\u8def\u5f84
            <input id="pdf-file-path" name="file_path" type="text" placeholder="E:\\path\\to\\paper.pdf" />
          </label>
          <div class="inline-fields">
            <label>
              \u6e90\u8bed\u8a00
              <select id="pdf-source-language" name="source_language">
                <option value="en">English</option>
                <option value="ja">Japanese</option>
              </select>
            </label>
            <label>
              \u5b58\u50a8\u7b56\u7565
              <input id="storage-strategy" type="text" value="outputs/library/pdf/<document-id>" disabled />
            </label>
          </div>
          <div class="inline-fields">
            <label>
              PDF \u8c03\u8bd5\u9875\u6570\u4e0a\u9650
              <input id="pdf-debug-max-pages" name="debug_max_pages" type="number" min="1" max="10000" placeholder="\u4e0d\u9650\u5236" />
            </label>
            <label>
              PDF \u8c03\u8bd5\u6bb5\u843d\u4e0a\u9650
              <input id="pdf-debug-max-paragraphs" name="debug_max_paragraphs" type="number" min="1" max="100000" placeholder="\u4e0d\u9650\u5236" />
            </label>
          </div>
          <div class="field-hint">\u9ed8\u8ba4\u9762\u5411\u82f1\u6587 PDF \u6587\u732e\uff0c\u4f1a\u5148\u63d0\u53d6\u6bb5\u843d\uff0c\u518d\u6279\u91cf\u7ffb\u8bd1\u6210\u4e2d\u6587\u3002</div>
        </div>
        <div class="inline-fields">
          <label>
            Batch Size
            <input id="batch-size" name="batch_size" type="number" min="1" max="64" value="8" />
          </label>
          <label>
            Max New Tokens
            <input id="max-new-tokens" name="max_new_tokens" type="number" min="32" max="1024" value="256" />
          </label>
        </div>
        <div class="inline-fields">
          <label>
            Timeout Seconds
            <input id="timeout-seconds" name="timeout_seconds" type="number" min="5" max="120" value="30" />
          </label>
          <label>
            \u5b58\u50a8\u7b56\u7565
            <input id="storage-strategy-summary" type="text" value="outputs/library/kakuyomu/<work-id>/<episode-id>" disabled />
          </label>
        </div>
        <button id="submit-btn" type="submit">\u5f00\u59cb\u5904\u7406</button>
        <div id="status-box" class="status" role="status" aria-live="polite">\u7b49\u5f85\u63d0\u4ea4\u4efb\u52a1\u3002</div>
        <div class="progress-block">
          <div class="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
            <div id="progress-fill" class="progress-fill"></div>
          </div>
          <div id="progress-text" class="progress-text">0%</div>
        </div>
      </form>
      <section class="history">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">
          <h2 id="history-title" style="font-size:18px;">\u6700\u8fd1\u4fdd\u5b58</h2>
          <button id="refresh-history-btn" class="secondary-btn" type="button">\u5237\u65b0</button>
        </div>
        <div id="history-list"></div>
      </section>
    </aside>

    <section class="main">
      <section id="result-panel" class="panel">
        <div id="empty-state" class="empty">
          \u8fd8\u6ca1\u6709\u52a0\u8f7d\u4efb\u4f55\u7ed3\u679c\u3002\u63d0\u4ea4 Kakuyomu \u5355\u7ae0 URL \u6216 PDF \u8def\u5f84\u540e\uff0c\u8fd9\u91cc\u4f1a\u76f4\u63a5\u663e\u793a\u7ffb\u8bd1\u7ed3\u679c\uff0c\u5e76\u652f\u6301\u6a21\u5f0f\u5207\u6362\u3002
        </div>
        <div id="result-shell" style="display:none;">
          <div class="result-header">
            <span class="eyebrow">Result</span>
            <div>
              <h2 id="translated-title" style="font-size:30px;line-height:1.15;"></h2>
              <p id="source-title" style="margin-top:8px;color:var(--muted);"></p>
            </div>
            <div class="meta-grid">
              <div class="meta-card"><strong id="meta-title-label">\u6765\u6e90</strong><span id="work-title"></span></div>
              <div class="meta-card"><strong id="meta-id-label">Identifier</strong><span id="work-episode-id"></span></div>
              <div class="meta-card"><strong>\u6a21\u578b</strong><span id="model-device"></span></div>
              <div class="meta-card"><strong>\u6bb5\u843d\u6570</strong><span id="paragraph-count"></span></div>
              <div id="debug-limits-card" class="meta-card" style="display:none;"><strong>PDF Debug</strong><span id="debug-limits"></span></div>
            </div>
            <div class="toolbar-links" id="saved-links"></div>
            <div class="mode-bar">
              <button class="secondary-btn mode-btn active" type="button" data-mode="reading">\u9605\u8bfb\u6a21\u5f0f</button>
              <button class="secondary-btn mode-btn" type="button" data-mode="compare">\u5bf9\u6bd4\u9605\u8bfb</button>
              <button class="secondary-btn mode-btn" type="button" data-mode="sentence">\u9010\u53e5\u5bf9\u6bd4</button>
            </div>
          </div>
          <div id="view-reading" class="view active"></div>
          <div id="view-compare" class="view"></div>
          <div id="view-sentence" class="view"></div>
        </div>
      </section>
    </section>
  </main>

  <script>
    const initialState = {initial_payload};
    const form = document.getElementById('translate-form');
    const sourceKindInput = document.getElementById('source-kind');
    const urlInput = document.getElementById('episode-url');
    const pdfFilePathInput = document.getElementById('pdf-file-path');
    const pdfSourceLanguageInput = document.getElementById('pdf-source-language');
    const pdfDebugMaxPagesInput = document.getElementById('pdf-debug-max-pages');
    const pdfDebugMaxParagraphsInput = document.getElementById('pdf-debug-max-paragraphs');
    const sourcePanelKakuyomu = document.getElementById('source-panel-kakuyomu');
    const sourcePanelPdf = document.getElementById('source-panel-pdf');
    const batchSizeInput = document.getElementById('batch-size');
    const maxNewTokensInput = document.getElementById('max-new-tokens');
    const timeoutInput = document.getElementById('timeout-seconds');
    const storageStrategyInput = document.getElementById('storage-strategy');
    const storageStrategySummaryInput = document.getElementById('storage-strategy-summary');
    const submitBtn = document.getElementById('submit-btn');
    const statusBox = document.getElementById('status-box');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const historyTitle = document.getElementById('history-title');
    const historyList = document.getElementById('history-list');
    const emptyState = document.getElementById('empty-state');
    const resultShell = document.getElementById('result-shell');
    const translatedTitle = document.getElementById('translated-title');
    const sourceTitle = document.getElementById('source-title');
    const workTitle = document.getElementById('work-title');
    const workEpisodeId = document.getElementById('work-episode-id');
    const metaTitleLabel = document.getElementById('meta-title-label');
    const metaIdLabel = document.getElementById('meta-id-label');
    const modelDevice = document.getElementById('model-device');
    const paragraphCount = document.getElementById('paragraph-count');
    const debugLimitsCard = document.getElementById('debug-limits-card');
    const debugLimits = document.getElementById('debug-limits');
    const savedLinks = document.getElementById('saved-links');
    const readingView = document.getElementById('view-reading');
    const compareView = document.getElementById('view-compare');
    const sentenceView = document.getElementById('view-sentence');
    const modeButtons = Array.from(document.querySelectorAll('.mode-btn'));
    const refreshHistoryBtn = document.getElementById('refresh-history-btn');

    let currentMode = 'reading';
    let currentResult = null;
    let currentJobId = null;
    let compareColumns = [];
    let compareSentenceMap = new Map();
    let compareActiveSentenceKey = '';
    let compareScrollSyncLocked = false;

    function getCurrentSourceKind() {{
      return sourceKindInput.value === 'pdf' ? 'pdf' : 'kakuyomu';
    }}

    function updateSourceMode() {{
      const sourceKind = getCurrentSourceKind();
      const isPdf = sourceKind === 'pdf';
      sourcePanelKakuyomu.classList.toggle('hidden', isPdf);
      sourcePanelPdf.classList.toggle('hidden', !isPdf);
      urlInput.required = !isPdf;
      pdfFilePathInput.required = isPdf;
      timeoutInput.disabled = isPdf;
      storageStrategyInput.value = isPdf
        ? 'outputs/library/pdf/<document-id>'
        : 'outputs/library/kakuyomu/<work-id>/<episode-id>';
      storageStrategySummaryInput.value = storageStrategyInput.value;
      historyTitle.textContent = isPdf ? '\u6700\u8fd1\u4fdd\u5b58 PDF' : '\u6700\u8fd1\u4fdd\u5b58 Kakuyomu';
    }}

    function setStatus(message, isError = false) {{
      statusBox.textContent = message;
      statusBox.classList.toggle('error', isError);
      statusBox.setAttribute('role', isError ? 'alert' : 'status');
    }}

    function setBusy(isBusy) {{
      submitBtn.disabled = isBusy;
      submitBtn.textContent = isBusy ? '\u5904\u7406\u4e2d...' : '\u5f00\u59cb\u5904\u7406';
    }}

    function setProgress(value, label = null) {{
      const clamped = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
      progressFill.style.width = `${{(clamped * 100).toFixed(1)}}%`;
      progressText.textContent = label ? `${{Math.round(clamped * 100)}}% - ${{label}}` : `${{Math.round(clamped * 100)}}%`;
      progressFill.closest('.progress-track')?.setAttribute('aria-valuenow', String(Math.round(clamped * 100)));
    }}

    function escapeHtml(text) {{
      return String(text ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function isHeadingKind(kind) {{
      return kind === 'chapter_heading' || kind === 'heading';
    }}

    function splitIntoSentences(text) {{
      return splitIntoSentencesStable(text);
    }}

    function splitIntoSentencesStable(text) {{
      const normalized = String(text ?? '').replace(/\\r/g, '').trim();
      if (!normalized) return [];
      const blocks = normalized.split(/\\n+/).map(item => item.trim()).filter(Boolean);
      const pieces = [];
      const sentenceEnders = new Set(['\\u3002', '\\uFF01', '\\uFF1F', '!', '?', '.', '\\u2026']);
      const trailingClosers = new Set([
        '\\u300D', '\\u300F', '\\u3011', '\\u3015', '\\u3017', '\\u3019',
        '\\uFF09', '\\uFF3D', '\\uFF5D', ')', ']', '}}', '"', "'", '\\u201D', '\\u2019'
      ]);

      function flush(buffer) {{
        const sentence = buffer.trim();
        if (sentence) {{
          pieces.push(sentence);
        }}
      }}

      for (const block of blocks) {{
        let buffer = '';
        for (let index = 0; index < block.length; index += 1) {{
          buffer += block[index];
          if (!sentenceEnders.has(block[index])) {{
            continue;
          }}

          while (index + 1 < block.length && sentenceEnders.has(block[index + 1])) {{
            index += 1;
            buffer += block[index];
          }}

          while (index + 1 < block.length && trailingClosers.has(block[index + 1])) {{
            index += 1;
            buffer += block[index];
          }}

          flush(buffer);
          buffer = '';
        }}

        if (buffer.trim()) {{
          flush(buffer);
        }}
      }}

      return pieces.length > 0 ? pieces : [normalized];
    }}

    function zipSentences(originalText, translatedText) {{
      const original = splitIntoSentencesStable(originalText);
      const translated = splitIntoSentencesStable(translatedText);
      const total = Math.max(original.length, translated.length);
      const rows = [];
      for (let index = 0; index < total; index += 1) {{
        rows.push({{
          index: index + 1,
          original: original[index] || '',
          translated: translated[index] || '',
        }});
      }}
      return rows;
    }}

    function parseOptionalPositiveInteger(input) {{
      const value = Number(input.value || 0);
      if (!Number.isFinite(value) || value <= 0) return null;
      return Math.floor(value);
    }}

    function formatDebugLimits(limits) {{
      if (!limits) return '';
      const parts = [];
      if (limits.max_pages) parts.push(`pages ${{limits.max_pages}}`);
      if (limits.max_paragraphs) parts.push(`paragraphs ${{limits.max_paragraphs}}`);
      if (limits.limited_paragraph_count !== undefined && limits.original_paragraph_count !== undefined) {{
        parts.push(`${{limits.limited_paragraph_count}}/${{limits.original_paragraph_count}} kept`);
      }}
      return parts.join(', ');
    }}

    function rebuildCompareSentenceMap() {{
      compareSentenceMap = new Map();
      compareView.querySelectorAll('.compare-sentence').forEach(node => {{
        const sentenceKey = node.dataset.sentenceKey || '';
        if (!sentenceKey) return;
        if (!compareSentenceMap.has(sentenceKey)) {{
          compareSentenceMap.set(sentenceKey, []);
        }}
        compareSentenceMap.get(sentenceKey).push(node);
      }});
    }}

    function centerCompareNode(node) {{
      if (!node) return;
      const column = node.closest('.compare-column');
      if (!column) return;
      const columnRect = column.getBoundingClientRect();
      const nodeRect = node.getBoundingClientRect();
      const delta = (nodeRect.top + nodeRect.height / 2) - (columnRect.top + columnRect.height / 2);
      column.scrollTo({{
        top: Math.max(0, column.scrollTop + delta),
        behavior: 'smooth',
      }});
    }}

    function syncCompareColumns(sourceColumn) {{
      if (compareScrollSyncLocked || compareColumns.length < 2 || !sourceColumn) return;
      const sourceMaxScroll = Math.max(1, sourceColumn.scrollHeight - sourceColumn.clientHeight);
      const ratio = sourceColumn.scrollTop / sourceMaxScroll;
      compareScrollSyncLocked = true;
      for (const column of compareColumns) {{
        if (column === sourceColumn) continue;
        const targetMaxScroll = Math.max(0, column.scrollHeight - column.clientHeight);
        column.scrollTop = ratio * targetMaxScroll;
      }}
      window.requestAnimationFrame(() => {{
        compareScrollSyncLocked = false;
      }});
    }}

    function setupCompareInteractions() {{
      compareColumns = Array.from(compareView.querySelectorAll('.compare-column'));
      rebuildCompareSentenceMap();
      for (const column of compareColumns) {{
        column.addEventListener('scroll', () => {{
          syncCompareColumns(column);
        }}, {{ passive: true }});
      }}
      compareActiveSentenceKey = '';
    }}

    function renderReading(paragraphs) {{
      const blocks = paragraphs.map(item => {{
        if (isHeadingKind(item.kind)) {{
          return `
            <section class="reading-heading" id="${{escapeHtml(item.paragraph_id)}}">
              <h3>${{escapeHtml(item.translated_text || item.original_text)}}</h3>
              <p class="source-note">${{escapeHtml(item.original_text)}}</p>
            </section>
          `;
        }}
        return `<p class="reading-paragraph" id="${{escapeHtml(item.paragraph_id)}}">${{escapeHtml(item.translated_text)}}</p>`;
      }}).join('');
      readingView.innerHTML = `<div class="reading-shell">${{blocks}}</div>`;
    }}

    function renderCompare(paragraphs) {{
      const renderArticle = (field) => paragraphs.map(item => {{
        if (isHeadingKind(item.kind)) {{
          const headingText = field === 'original' ? item.original_text : item.translated_text;
          return `
            <section class="compare-heading" id="compare-${{escapeHtml(field)}}-${{escapeHtml(item.paragraph_id)}}">
              <h4>${{escapeHtml(headingText || item.original_text)}}</h4>
            </section>
          `;
        }}
        const rows = zipSentences(item.original_text, item.translated_text);
        const sentenceHtml = rows.map((row, index) => {{
          const sentenceKey = `${{item.paragraph_id}}-${{index + 1}}`;
          const sentenceText = field === 'original' ? row.original : row.translated;
          return `<span class="compare-sentence" tabindex="0" role="button" aria-selected="false" data-sentence-key="${{escapeHtml(sentenceKey)}}">${{escapeHtml(sentenceText || ' ')}}</span>`;
        }}).join('');
        return `<p class="compare-paragraph">${{sentenceHtml}}</p>`;
      }}).join('');

      compareView.innerHTML = `
        <div class="compare-shell">
          <section class="compare-column">
            <h3>Original</h3>
            <article class="compare-article">${{renderArticle('original')}}</article>
          </section>
          <section class="compare-column">
            <h3>Translation</h3>
            <article class="compare-article">${{renderArticle('translated')}}</article>
          </section>
        </div>
      `;
      setupCompareInteractions();
    }}

    function clearCompareHighlight() {{
      compareView.querySelectorAll('.compare-sentence.active').forEach(node => {{
        node.classList.remove('active');
        node.setAttribute('aria-selected', 'false');
      }});
      compareActiveSentenceKey = '';
    }}

    function setCompareHighlight(sentenceKey, options = {{}}) {{
      if (!sentenceKey) return;
      const shouldCenter = Boolean(options.center);
      const sourceColumn = options.sourceNode ? options.sourceNode.closest('.compare-column') : null;
      if (compareActiveSentenceKey !== sentenceKey) {{
        compareView.querySelectorAll('.compare-sentence.active').forEach(node => {{
          node.classList.remove('active');
          node.setAttribute('aria-selected', 'false');
        }});
        const nodes = compareSentenceMap.get(sentenceKey) || [];
        nodes.forEach(node => {{
          node.classList.add('active');
          node.setAttribute('aria-selected', 'true');
        }});
        compareActiveSentenceKey = sentenceKey;
      }}
      if (shouldCenter) {{
        const nodes = compareSentenceMap.get(sentenceKey) || [];
        nodes.forEach(node => {{
          if (sourceColumn && node.closest('.compare-column') === sourceColumn) return;
          centerCompareNode(node);
        }});
      }}
    }}

    function renderSentence(paragraphs) {{
      sentenceView.innerHTML = paragraphs.map(item => {{
        const rows = isHeadingKind(item.kind)
          ? [{{ index: 1, original: item.original_text, translated: item.translated_text }}]
          : zipSentences(item.original_text, item.translated_text);
        return `
          <article class="sentence-card" id="sentence-${{escapeHtml(item.paragraph_id)}}">
            <div class="pair-meta">
              <span class="tag">${{escapeHtml(item.paragraph_id)}}</span>
              <span class="tag">${{escapeHtml(item.kind)}}</span>
            </div>
            <div class="sentence-table">
              ${{
                rows.map(row => `
                  <div class="sentence-row">
                    <div class="sentence-index">#${{row.index}}</div>
                    <div class="sentence-cell">${{escapeHtml(row.original)}}</div>
                    <div class="sentence-cell">${{escapeHtml(row.translated)}}</div>
                  </div>
                `).join('')
              }}
            </div>
          </article>
        `;
      }}).join('');
    }}

    function renderSavedLinks(savedFiles) {{
      const links = [
        ['\u5df2\u4fdd\u5b58 JSON', savedFiles.result_json_url],
        ['\u5df2\u4fdd\u5b58\u5bf9\u7167\u9875', savedFiles.bilingual_html_url],
        ['\u5df2\u4fdd\u5b58\u9605\u8bfb\u9875', savedFiles.reading_html_url],
      ];
      const indexUrl = savedFiles.episode_index_html_url || savedFiles.document_index_html_url;
      if (indexUrl) {{
        links.push(['\u7d22\u5f15\u9875', indexUrl]);
      }}
      savedLinks.innerHTML = links.map(([label, href]) => `<a href="${{escapeHtml(href)}}" target="_blank" rel="noreferrer">${{escapeHtml(label)}}</a>`).join('');
    }}

    function updateMode(mode) {{
      currentMode = mode;
      modeButtons.forEach(button => {{
        button.classList.toggle('active', button.dataset.mode === mode);
      }});
      document.querySelectorAll('.view').forEach(view => {{
        view.classList.toggle('active', view.id === `view-${{mode}}`);
      }});
    }}

    function renderResult(result) {{
      currentResult = result;
      emptyState.style.display = 'none';
      resultShell.style.display = 'block';
      translatedTitle.textContent = result.translated_title;
      if (result.provider === 'pdf') {{
        metaTitleLabel.textContent = '\u6587\u6863';
        metaIdLabel.textContent = 'Document ID';
        sourceTitle.textContent = `${{result.document_title}} / ${{result.source_file_name}}`;
        workTitle.textContent = result.document_title;
        workEpisodeId.textContent = result.document_id;
      }} else {{
        metaTitleLabel.textContent = '\u6765\u6e90';
        metaIdLabel.textContent = 'Work / Episode ID';
        sourceTitle.textContent = `${{result.work_title}} / ${{result.episode_title}}`;
        workTitle.textContent = result.work_title;
        workEpisodeId.textContent = `${{result.work_id}} / ${{result.episode_id}}`;
      }}
      modelDevice.textContent = `${{result.model_name}} / ${{result.device}}`;
      paragraphCount.textContent = String((result.paragraphs || []).length);
      const debugLabel = formatDebugLimits(result.debug_limits);
      debugLimitsCard.style.display = debugLabel ? 'block' : 'none';
      debugLimits.textContent = debugLabel;
      renderSavedLinks(result.saved_files);
      renderReading(result.paragraphs || []);
      renderCompare(result.paragraphs || []);
      renderSentence(result.paragraphs || []);
      updateMode(currentMode);
      const pageUrl = new URL(window.location.href);
      if (result.provider === 'pdf') {{
        pageUrl.searchParams.set('provider', 'pdf');
        pageUrl.searchParams.set('document_id', result.document_id);
        pageUrl.searchParams.delete('work_id');
        pageUrl.searchParams.delete('episode_id');
      }} else {{
        pageUrl.searchParams.set('provider', 'kakuyomu');
        pageUrl.searchParams.set('work_id', result.work_id);
        pageUrl.searchParams.set('episode_id', result.episode_id);
        pageUrl.searchParams.delete('document_id');
      }}
      window.history.replaceState(null, '', pageUrl.toString());
    }}

    async function loadHistory() {{
      const sourceKind = getCurrentSourceKind();
      const response = await fetch(sourceKind === 'pdf' ? '/ui/api/pdf/history' : '/ui/api/kakuyomu/history');
      if (!response.ok) {{
        throw new Error('Unable to load history.');
      }}
      const data = await response.json();
      const items = data.items || [];
      if (sourceKind === 'pdf') {{
        historyList.innerHTML = items.length
          ? items.map(item => `
              <article class="history-item">
                <strong>${{escapeHtml(item.document_title)}} ${{item.is_debug ? '<span class="debug-badge">DEBUG</span>' : ''}}</strong>
                <small>${{escapeHtml(item.saved_at)}}<br>${{escapeHtml(item.document_id)}}<br>${{escapeHtml(item.source_file_name)}}</small>
                <div class="history-actions">
                  <button type="button" class="secondary-btn" data-provider="pdf" data-document-id="${{escapeHtml(item.document_id)}}">\u52a0\u8f7d</button>
                  <a href="${{escapeHtml(item.reading_html_url)}}" target="_blank" rel="noreferrer">\u9605\u8bfb\u9875</a>
                  <a href="${{escapeHtml(item.bilingual_html_url)}}" target="_blank" rel="noreferrer">\u5bf9\u7167\u9875</a>
                </div>
              </article>
            `).join('')
          : '<div class="status">\u8fd8\u6ca1\u6709\u5df2\u4fdd\u5b58 PDF\u3002</div>';
        return;
      }}

      historyList.innerHTML = items.length
        ? items.map(item => `
            <article class="history-item">
              <strong>${{escapeHtml(item.work_title)}} / ${{escapeHtml(item.episode_title)}}</strong>
              <small>${{escapeHtml(item.saved_at)}}<br>${{escapeHtml(item.work_id)}} / ${{escapeHtml(item.episode_id)}}</small>
              <div class="history-actions">
                <button type="button" class="secondary-btn" data-provider="kakuyomu" data-work-id="${{escapeHtml(item.work_id)}}" data-episode-id="${{escapeHtml(item.episode_id)}}">\u52a0\u8f7d</button>
                <a href="${{escapeHtml(item.reading_html_url)}}" target="_blank" rel="noreferrer">\u9605\u8bfb\u9875</a>
                <a href="${{escapeHtml(item.bilingual_html_url)}}" target="_blank" rel="noreferrer">\u5bf9\u7167\u9875</a>
              </div>
            </article>
          `).join('')
        : '<div class="status">\u8fd8\u6ca1\u6709\u5df2\u4fdd\u5b58 Kakuyomu \u7ae0\u8282\u3002</div>';
    }}

    async function loadSavedResult(sourceKind, identifiers) {{
      if (sourceKind === 'pdf') {{
        setStatus(`\u52a0\u8f7d\u5df2\u4fdd\u5b58 PDF: ${{identifiers.documentId}}`);
        setProgress(1, '\u5df2\u52a0\u8f7d');
        const response = await fetch(`/ui/api/pdf/result/${{encodeURIComponent(identifiers.documentId)}}`);
        const data = await response.json();
        if (!response.ok) {{
          throw new Error(data.detail || 'Unable to load saved result.');
        }}
        renderResult(data);
        setStatus(`\u5df2\u52a0\u8f7d PDF: ${{data.document_title}}`);
        return;
      }}

      const workId = identifiers.workId;
      const episodeId = identifiers.episodeId;
      setStatus(`\u52a0\u8f7d\u5df2\u4fdd\u5b58\u7ae0\u8282: ${{workId}} / ${{episodeId}}`);
      setProgress(1, '\u5df2\u52a0\u8f7d');
      const response = await fetch(`/ui/api/kakuyomu/result/${{encodeURIComponent(workId)}}/${{encodeURIComponent(episodeId)}}`);
      const data = await response.json();
      if (!response.ok) {{
        throw new Error(data.detail || 'Unable to load saved result.');
      }}
      renderResult(data);
      setStatus(`\u5df2\u52a0\u8f7d: ${{data.work_title}} / ${{data.episode_title}}`);
    }}

    async function pollJob(sourceKind, jobId) {{
      currentJobId = jobId;
      while (true) {{
        const response = await fetch(
          sourceKind === 'pdf'
            ? `/ui/api/pdf/jobs/${{encodeURIComponent(jobId)}}`
            : `/ui/api/kakuyomu/jobs/${{encodeURIComponent(jobId)}}`
        );
        const data = await response.json();
        if (!response.ok) {{
          throw new Error(data.detail || 'Unable to fetch job status.');
        }}
        setProgress(data.progress || 0, data.message || '');
        if (data.status === 'completed') {{
          currentJobId = null;
          return data.result;
        }}
        if (data.status === 'failed') {{
          currentJobId = null;
          throw new Error(data.error || data.message || 'Job failed.');
        }}
        await new Promise(resolve => window.setTimeout(resolve, 700));
      }}
    }}

    form.addEventListener('submit', async event => {{
      event.preventDefault();
      const sourceKind = getCurrentSourceKind();
      const commonPayload = {{
        batch_size: Number(batchSizeInput.value || 8),
        max_new_tokens: Number(maxNewTokensInput.value || 256),
      }};
      let endpoint = '/ui/api/kakuyomu/jobs';
      let payload = {{}};

      if (sourceKind === 'pdf') {{
        payload = {{
          file_path: pdfFilePathInput.value.trim(),
          source_language: pdfSourceLanguageInput.value,
          ...commonPayload,
        }};
        const debugMaxPages = parseOptionalPositiveInteger(pdfDebugMaxPagesInput);
        const debugMaxParagraphs = parseOptionalPositiveInteger(pdfDebugMaxParagraphsInput);
        if (debugMaxPages !== null) {{
          payload.debug_max_pages = debugMaxPages;
        }}
        if (debugMaxParagraphs !== null) {{
          payload.debug_max_paragraphs = debugMaxParagraphs;
        }}
        endpoint = '/ui/api/pdf/jobs';
        if (!payload.file_path) {{
          setStatus('\u8bf7\u5148\u8f93\u5165 PDF \u6587\u4ef6\u8def\u5f84\u3002', true);
          return;
        }}
      }} else {{
        payload = {{
          url: urlInput.value.trim(),
          timeout_seconds: Number(timeoutInput.value || 30),
          ...commonPayload,
        }};
        if (!payload.url) {{
          setStatus('\u8bf7\u5148\u8f93\u5165 Kakuyomu \u5355\u7ae0 URL\u3002', true);
          return;
        }}
      }}

      setBusy(true);
      setProgress(0.01, '\u521b\u5efa\u4efb\u52a1');
      setStatus(
        sourceKind === 'pdf'
          ? '\u540e\u7aef\u5904\u7406\u4e2d\uff1aPDF \u63d0\u53d6\u3001\u7ffb\u8bd1\u3001\u4fdd\u5b58\u3002'
          : '\u540e\u7aef\u5904\u7406\u4e2d\uff1a\u6293\u53d6\u3001\u7ffb\u8bd1\u3001\u4fdd\u5b58\u3002'
      );
      try {{
        const response = await fetch(endpoint, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
          body: JSON.stringify(payload),
        }});
        const data = await response.json();
        if (!response.ok) {{
          throw new Error(data.detail || 'Translation failed.');
        }}
        const result = await pollJob(sourceKind, data.job_id);
        renderResult(result);
        await loadHistory();
        setProgress(1, '\u5df2\u5b8c\u6210');
        setStatus(
          result.provider === 'pdf'
            ? `\u5df2\u5b8c\u6210: ${{result.document_title}}\uff0c\u7ed3\u679c\u5df2\u4fdd\u5b58\u5230\u672c\u5730\u3002`
            : `\u5df2\u5b8c\u6210: ${{result.work_title}} / ${{result.episode_title}}\uff0c\u7ed3\u679c\u5df2\u4fdd\u5b58\u5230\u672c\u5730\u3002`
        );
      }} catch (error) {{
        setProgress(1, '\u5931\u8d25');
        setStatus(String(error.message || error), true);
      }} finally {{
        setBusy(false);
      }}
    }});

    refreshHistoryBtn.addEventListener('click', async () => {{
      try {{
        await loadHistory();
        setStatus('\u5386\u53f2\u5217\u8868\u5df2\u5237\u65b0\u3002');
      }} catch (error) {{
        setStatus(String(error.message || error), true);
      }}
    }});

    historyList.addEventListener('click', async event => {{
      const button = event.target.closest('button[data-provider]');
      if (!button) return;
      try {{
        if (button.dataset.provider === 'pdf') {{
          await loadSavedResult('pdf', {{ documentId: button.dataset.documentId }});
        }} else {{
          await loadSavedResult('kakuyomu', {{ workId: button.dataset.workId, episodeId: button.dataset.episodeId }});
        }}
      }} catch (error) {{
        setStatus(String(error.message || error), true);
      }}
    }});

    sourceKindInput.addEventListener('change', async () => {{
      updateSourceMode();
      setProgress(0);
      setStatus(
        getCurrentSourceKind() === 'pdf'
          ? '\u5207\u6362\u5230 PDF \u6a21\u5f0f\uff0c\u7b49\u5f85\u8f93\u5165\u6587\u4ef6\u8def\u5f84\u3002'
          : '\u5207\u6362\u5230 Kakuyomu \u6a21\u5f0f\uff0c\u7b49\u5f85\u8f93\u5165 URL\u3002'
      );
      try {{
        await loadHistory();
      }} catch (error) {{
        setStatus(String(error.message || error), true);
      }}
    }});

    modeButtons.forEach(button => {{
      button.addEventListener('click', () => updateMode(button.dataset.mode));
    }});

    compareView.addEventListener('mouseover', event => {{
      const target = event.target.closest('.compare-sentence');
      if (!target) return;
      setCompareHighlight(target.dataset.sentenceKey || '');
    }});

    compareView.addEventListener('mouseleave', () => {{
      clearCompareHighlight();
    }});

    compareView.addEventListener('click', event => {{
      const target = event.target.closest('.compare-sentence');
      if (!target) return;
      setCompareHighlight(target.dataset.sentenceKey || '', {{ center: true, sourceNode: target }});
    }});

    compareView.addEventListener('keydown', event => {{
      const target = event.target.closest('.compare-sentence');
      if (!target || !['Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      setCompareHighlight(target.dataset.sentenceKey || '', {{ center: true, sourceNode: target }});
    }});

    (async () => {{
      sourceKindInput.value = initialState.provider === 'pdf' ? 'pdf' : 'kakuyomu';
      updateSourceMode();
      setProgress(0);
      try {{
        await loadHistory();
      }} catch (error) {{
        setStatus(String(error.message || error), true);
      }}
      if (initialState.provider === 'pdf' && initialState.documentId) {{
        try {{
          await loadSavedResult('pdf', {{ documentId: initialState.documentId }});
        }} catch (error) {{
          setStatus(String(error.message || error), true);
        }}
      }}
      if ((!initialState.provider || initialState.provider === 'kakuyomu') && initialState.workId && initialState.episodeId) {{
        try {{
          await loadSavedResult('kakuyomu', {{ workId: initialState.workId, episodeId: initialState.episodeId }});
        }} catch (error) {{
          setStatus(String(error.message || error), true);
        }}
      }}
    }})();
  </script>
</body>
</html>
"""
