from __future__ import annotations

import html
from pathlib import Path
from typing import Any


INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def sanitize_filename_component(value: str) -> str:
    sanitized = "".join("_" if char in INVALID_FILENAME_CHARS or ord(char) < 32 else char for char in value)
    sanitized = sanitized.strip().rstrip(".")
    return sanitized or "untitled"


def suggest_output_stem(*candidates: str, fallback: str = "episode") -> str:
    for candidate in candidates:
        sanitized = sanitize_filename_component(candidate)
        if sanitized and sanitized != "untitled":
            return sanitized
    return fallback


def render_translation_html(result: dict[str, Any], json_file_name: str, reading_file_name: str) -> str:
    paragraphs = result.get("paragraphs", [])
    source_file = html.escape(str(result.get("source_file", "")))
    file_name = html.escape(str(result.get("source_file_name", "")))
    model_name = html.escape(str(result.get("model_name", "")))
    device = html.escape(str(result.get("device", "")))
    paragraph_count = len(paragraphs)

    paragraph_cards = "\n".join(
        f"""
        <article class="pair" id="{html.escape(item['paragraph_id'])}">
          <div class="pair-meta">
            <span class="pair-id">{html.escape(item['paragraph_id'])}</span>
            <span class="pair-kind">{html.escape(item.get('kind', 'paragraph'))}</span>
          </div>
          <div class="pair-grid">
            <section class="panel original">
              <h2>Original</h2>
              <p>{html.escape(item['original_text'])}</p>
            </section>
            <section class="panel translated">
              <h2>Translation</h2>
              <p>{html.escape(item['translated_text'])}</p>
            </section>
          </div>
        </article>
        """
        for item in paragraphs
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{file_name} - Bilingual Output</title>
  <style>
    :root {{
      --bg: #f5efe3;
      --paper: #fffaf1;
      --ink: #1f1a17;
      --muted: #6f655e;
      --line: #d9ccba;
      --accent: #7a2419;
      --accent-soft: #efe0d2;
      --shadow: 0 18px 45px rgba(79, 55, 28, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top, #fdf7ed 0%, var(--bg) 58%, #e9dcc9 100%);
      line-height: 1.65;
    }}
    .shell {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}
    .hero {{
      background: linear-gradient(140deg, rgba(255, 250, 241, 0.96), rgba(246, 234, 216, 0.96));
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 28px;
      margin-bottom: 24px;
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
    h1 {{
      margin: 14px 0 10px;
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1.1;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-top: 20px;
    }}
    .meta-card {{
      background: rgba(255, 255, 255, 0.62);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
    }}
    .meta-card strong {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 4px;
    }}
    .meta-card span {{
      word-break: break-word;
    }}
    .link-row {{
      margin-top: 18px;
    }}
    .link-row a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }}
    .pair {{
      background: rgba(255, 250, 241, 0.94);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      padding: 18px;
      margin-top: 18px;
    }}
    .pair-meta {{
      margin-bottom: 14px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .pair-id, .pair-kind {{
      display: inline-block;
      font-family: Consolas, "Cascadia Code", monospace;
      font-size: 13px;
      padding: 6px 10px;
      border-radius: 999px;
      background: #f0e3d2;
      color: #6d3626;
    }}
    .pair-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .panel {{
      min-height: 100%;
      border-radius: 18px;
      padding: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.78);
    }}
    .panel h2 {{
      margin: 0 0 10px;
      font-size: 14px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .panel p {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 17px;
    }}
    .translated {{
      background: rgba(250, 242, 232, 0.92);
    }}
    @media (max-width: 860px) {{
      .pair-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <span class="eyebrow">Bilingual Output</span>
      <h1>{file_name}</h1>
      <div class="meta">
        <div class="meta-card"><strong>Source</strong><span>{source_file}</span></div>
        <div class="meta-card"><strong>Paragraphs</strong><span>{paragraph_count}</span></div>
        <div class="meta-card"><strong>Model</strong><span>{model_name}</span></div>
        <div class="meta-card"><strong>Device</strong><span>{device}</span></div>
      </div>
      <div class="link-row">
        <a href="{html.escape(json_file_name)}">Open JSON output</a>
        <span> | </span>
        <a href="{html.escape(reading_file_name)}">Open merged reading view</a>
      </div>
    </section>
    {paragraph_cards}
  </main>
</body>
</html>
"""


def render_reading_html(result: dict[str, Any], json_file_name: str, bilingual_file_name: str) -> str:
    paragraphs = result.get("paragraphs", [])
    source_title = html.escape(str(result.get("source_title", "")))
    translated_title = html.escape(str(result.get("translated_title", "")))
    source_file = html.escape(str(result.get("source_file", "")))
    model_name = html.escape(str(result.get("model_name", "")))
    device = html.escape(str(result.get("device", "")))

    toc_items = "\n".join(
        f'<li><a href="#{html.escape(item["paragraph_id"])}">{html.escape(item["translated_text"] or item["original_text"])}</a></li>'
        for item in paragraphs
        if item.get("kind") == "heading"
    )

    content_blocks: list[str] = []
    for item in paragraphs:
        anchor = html.escape(item["paragraph_id"])
        translated_text = html.escape(str(item["translated_text"]))
        original_text = html.escape(str(item["original_text"]))
        if item.get("kind") == "heading":
            content_blocks.append(
                f"""
                <section class="chapter-heading" id="{anchor}">
                  <h2>{translated_text or original_text}</h2>
                  <p class="source-note">{original_text}</p>
                </section>
                """
            )
        else:
            content_blocks.append(
                f"""
                <p class="reading-paragraph" id="{anchor}">{translated_text}</p>
                """
            )

    toc_section = ""
    if toc_items:
        toc_section = f"""
        <aside class="toc">
          <h2>Contents</h2>
          <ol>
            {toc_items}
          </ol>
        </aside>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{translated_title or source_title} - Reading View</title>
  <style>
    :root {{
      --bg: #f4efe8;
      --paper: #fffcf7;
      --ink: #231c17;
      --muted: #72685f;
      --line: #ddd1c2;
      --accent: #8d2d1b;
      --accent-soft: #f2dfd9;
      --shadow: 0 18px 48px rgba(64, 40, 20, 0.07);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        linear-gradient(180deg, rgba(255, 250, 243, 0.92), rgba(244, 239, 232, 0.98)),
        radial-gradient(circle at top left, rgba(241, 224, 205, 0.55), transparent 40%);
      color: var(--ink);
      font-family: "Georgia", "Times New Roman", "Noto Serif SC", "Songti SC", serif;
    }}
    .shell {{
      max-width: 900px;
      margin: 0 auto;
      padding: 32px 18px 60px;
    }}
    .hero, .toc, .article {{
      background: rgba(255, 252, 247, 0.95);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
    }}
    .hero {{
      padding: 26px;
      margin-bottom: 18px;
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
    h1 {{
      margin: 14px 0 10px;
      font-size: clamp(30px, 5vw, 46px);
      line-height: 1.12;
    }}
    .subtitle {{
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 16px;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      color: var(--muted);
      font-size: 14px;
    }}
    .links {{
      margin-top: 18px;
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
    }}
    .links a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }}
    .toc {{
      padding: 22px 24px;
      margin-bottom: 18px;
    }}
    .toc h2 {{
      margin: 0 0 12px;
      font-size: 14px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-family: "Segoe UI", "Noto Sans SC", sans-serif;
    }}
    .toc ol {{
      margin: 0;
      padding-left: 20px;
    }}
    .toc li + li {{
      margin-top: 8px;
    }}
    .toc a {{
      color: var(--accent);
      text-decoration: none;
    }}
    .article {{
      padding: 34px 32px;
    }}
    .chapter-heading {{
      margin: 26px 0 16px;
      padding-top: 8px;
    }}
    .chapter-heading h2 {{
      margin: 0 0 6px;
      font-size: clamp(24px, 3vw, 32px);
      line-height: 1.2;
    }}
    .source-note {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      font-family: "Segoe UI", "Noto Sans SC", sans-serif;
    }}
    .reading-paragraph {{
      margin: 0;
      font-size: 20px;
      line-height: 1.9;
      text-wrap: pretty;
    }}
    .reading-paragraph + .reading-paragraph {{
      margin-top: 1.15em;
    }}
    @media (max-width: 720px) {{
      .article {{
        padding: 26px 20px;
      }}
      .reading-paragraph {{
        font-size: 18px;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <span class="eyebrow">Reading View</span>
      <h1>{translated_title or source_title}</h1>
      <p class="subtitle">{source_title}</p>
      <div class="meta">
        <span>Source: {source_file}</span>
        <span>Model: {model_name}</span>
        <span>Device: {device}</span>
        <span>Paragraphs: {len(paragraphs)}</span>
      </div>
      <div class="links">
        <a href="{html.escape(bilingual_file_name)}">Open bilingual validation view</a>
        <a href="{html.escape(json_file_name)}">Open JSON output</a>
      </div>
    </section>
    {toc_section}
    <article class="article">
      {''.join(content_blocks)}
    </article>
  </main>
</body>
</html>
"""


def render_kakuyomu_index_html(
    result: dict[str, Any],
    *,
    json_file_name: str,
    bilingual_file_name: str,
    reading_file_name: str,
) -> str:
    work_title = html.escape(str(result.get("work_title", "")))
    episode_title = html.escape(str(result.get("episode_title", "")))
    translated_title = html.escape(str(result.get("translated_title", "")))
    model_name = html.escape(str(result.get("model_name", "")))
    device = html.escape(str(result.get("device", "")))
    url = html.escape(str(result.get("url", "")))
    paragraph_count = len(result.get("paragraphs", []))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{episode_title or work_title} - Kakuyomu Output</title>
  <style>
    :root {{
      --bg: #f3efe8;
      --paper: #fffdf8;
      --ink: #201b18;
      --line: #d8cec2;
      --accent: #0f5f61;
      --accent-soft: #d9eeee;
      --muted: #6b6258;
    }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #faf7f1, var(--bg));
      color: var(--ink);
      font-family: "Segoe UI", "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
    }}
    .shell {{
      max-width: 960px;
      margin: 0 auto;
      padding: 32px 20px 52px;
    }}
    .hero, .panel {{
      background: rgba(255, 253, 248, 0.95);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 24px;
      margin-bottom: 18px;
      box-shadow: 0 18px 40px rgba(48, 35, 23, 0.06);
    }}
    .badge {{
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
    h1 {{
      margin: 14px 0 10px;
      font-size: clamp(28px, 4vw, 42px);
      line-height: 1.1;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 16px;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-top: 20px;
    }}
    .meta-card {{
      background: rgba(255, 255, 255, 0.62);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
    }}
    .meta-card strong {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 4px;
    }}
    .meta-card span {{
      word-break: break-word;
    }}
    .panel a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
    }}
    li + li {{
      margin-top: 10px;
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <span class="badge">Kakuyomu Translation</span>
      <h1>{translated_title or episode_title or work_title}</h1>
      <p class="subtitle">{work_title} / {episode_title}</p>
      <div class="meta">
        <div class="meta-card"><strong>Source URL</strong><span>{url}</span></div>
        <div class="meta-card"><strong>Paragraphs</strong><span>{paragraph_count}</span></div>
        <div class="meta-card"><strong>Model</strong><span>{model_name}</span></div>
        <div class="meta-card"><strong>Device</strong><span>{device}</span></div>
      </div>
    </section>
    <section class="panel">
      <h2>Outputs</h2>
      <ul>
        <li><a href="{html.escape(reading_file_name)}">Reading view</a></li>
        <li><a href="{html.escape(bilingual_file_name)}">Bilingual validation view</a></li>
        <li><a href="{html.escape(json_file_name)}">JSON output</a></li>
      </ul>
    </section>
  </main>
</body>
</html>
"""


def default_run_directory(base_output_dir: Path, *, title: str) -> Path:
    from datetime import datetime

    folder_name = sanitize_filename_component(f"{title}-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    return base_output_dir.expanduser().resolve() / folder_name
