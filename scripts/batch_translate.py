from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-translate UTF-8 text files through the local Japanese translation API.",
    )
    parser.add_argument("--url", default="http://127.0.0.1:7860/translate/ja")
    parser.add_argument("--input", type=Path, required=True, help="A UTF-8 text file or a directory containing .txt files.")
    parser.add_argument("--pattern", default="*.txt", help="Glob pattern used when --input is a directory.")
    parser.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--run-name",
        help="Optional batch folder name created under --output-dir. Defaults to <input-name>-<timestamp>.",
    )
    parser.add_argument(
        "--preserve-structure",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep the input directory structure under the output directory.",
    )
    parser.add_argument(
        "--name-template",
        default="{stem}",
        help="Base output name template. Available fields: stem, parent, relative_dir, relative_stem, index.",
    )
    parser.add_argument("--encoding", default="utf-8", help="Text encoding for input files.")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/batch"))
    return parser.parse_args()


def discover_source_files(input_path: Path, pattern: str, recursive: bool) -> tuple[list[Path], Path]:
    resolved_input = input_path.expanduser().resolve()
    if not resolved_input.exists():
        raise FileNotFoundError(f"Input path does not exist: {resolved_input}")

    if resolved_input.is_file():
        if resolved_input.suffix.lower() != ".txt":
            raise ValueError(f"Expected a .txt file, got: {resolved_input}")
        return [resolved_input], resolved_input.parent

    iterator = resolved_input.rglob(pattern) if recursive else resolved_input.glob(pattern)
    files = sorted(path.resolve() for path in iterator if path.is_file())
    if not files:
        raise ValueError(f"No files matched pattern '{pattern}' under: {resolved_input}")
    return files, resolved_input


def post_translation_request(
    *,
    url: str,
    text: str,
    batch_size: int,
    max_new_tokens: int,
) -> dict[str, Any]:
    payload = {
        "text": text,
        "batch_size": batch_size,
        "max_new_tokens": max_new_tokens,
    }
    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=request_body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to reach translation service at {url}: {exc.reason}") from exc

    return json.loads(response_body.decode("utf-8"))


def build_result_document(source_file: Path, response_data: dict[str, Any]) -> dict[str, Any]:
    result = dict(response_data)
    result["source_file"] = str(source_file)
    result["source_file_name"] = source_file.name
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    return result


HEADING_PATTERNS = (
    re.compile(r"^\s*(?:第[0-9０-９一二三四五六七八九十百千零〇]+(?:章|話|節|部|巻)|[0-9０-９]+(?:[.\-][0-9０-９]+)*[.)、]?)\s*\S*"),
    re.compile(r"^\s*(?:序章|終章|幕間|間章|番外編|プロローグ|エピローグ|あとがき|後書き|序|終)\s*$"),
    re.compile(r"^\s*(?:chapter|part|section|prologue|epilogue|interlude)\b", re.IGNORECASE),
)


def detect_heading_kind(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "paragraph"
    if len(stripped) > 80:
        return "paragraph"
    if stripped.endswith(("。", "！", "？", ".", "!", "?")):
        return "paragraph"
    if any(pattern.match(stripped) for pattern in HEADING_PATTERNS):
        return "heading"
    if re.search(r"[A-Za-z]", stripped) and stripped == stripped.upper() and len(stripped.split()) <= 8:
        return "heading"
    return "paragraph"


def enrich_paragraphs(paragraphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in paragraphs:
        enriched_item = dict(item)
        enriched_item["kind"] = detect_heading_kind(str(item.get("original_text", "")))
        enriched.append(enriched_item)
    return enriched


def detect_titles(source_file: Path, paragraphs: list[dict[str, Any]]) -> tuple[str, str]:
    for item in paragraphs[:3]:
        if item.get("kind") == "heading":
            return str(item.get("original_text", "")).strip(), str(item.get("translated_text", "")).strip()
    fallback = source_file.stem
    return fallback, fallback


INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def sanitize_filename_component(value: str) -> str:
    sanitized = "".join("_" if char in INVALID_FILENAME_CHARS or ord(char) < 32 else char for char in value)
    sanitized = sanitized.strip().rstrip(".")
    return sanitized or "untitled"


def resolve_batch_output_root(base_output_dir: Path, input_path: Path, run_name: str | None) -> Path:
    base_root = base_output_dir.expanduser().resolve()
    resolved_input = input_path.expanduser().resolve()
    if run_name:
        folder_name = sanitize_filename_component(run_name)
    else:
        input_label = resolved_input.stem if resolved_input.is_file() else resolved_input.name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        folder_name = sanitize_filename_component(f"{input_label}-{timestamp}")
    return base_root / folder_name


def build_output_base(
    *,
    output_root: Path,
    relative_source: Path,
    preserve_structure: bool,
    name_template: str,
    index: int,
) -> Path:
    relative_dir = relative_source.parent.as_posix()
    relative_stem = relative_source.with_suffix("").as_posix()
    template_values = {
        "stem": relative_source.stem,
        "parent": relative_source.parent.name if relative_source.parent != Path(".") else "root",
        "relative_dir": relative_dir or "root",
        "relative_stem": relative_stem,
        "index": index,
    }
    try:
        rendered_name = name_template.format_map(template_values)
    except KeyError as exc:
        raise ValueError(f"Unknown placeholder in --name-template: {exc}") from exc

    parts = [sanitize_filename_component(part) for part in rendered_name.replace("\\", "/").split("/") if part]
    if not parts:
        parts = [f"file-{index:04d}"]
    target_dir = output_root / relative_source.parent if preserve_structure else output_root
    return target_dir.joinpath(*parts)


def render_translation_html(result: dict[str, Any], json_file_name: str, reading_file_name: str) -> str:
    paragraphs = result.get("paragraphs", [])
    source_file = html.escape(str(result.get("source_file", "")))
    file_name = html.escape(str(result.get("source_file_name", "")))
    model_name = html.escape(str(result.get("model_name", "")))
    device = html.escape(str(result.get("device", "")))
    paragraph_count = len(paragraphs)

    paragraph_cards = "\n".join(
        f"""
        <article class="pair" id="{html.escape(item['original_id'])}">
          <div class="pair-meta">
            <span class="pair-id">{html.escape(item['original_id'])}</span>
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
    }}
    .pair-id {{
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
        <div class="meta-card"><strong>Source File</strong><span>{source_file}</span></div>
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
        f'<li><a href="#{html.escape(item["original_id"])}">{html.escape(item["translated_text"] or item["original_text"])}</a></li>'
        for item in paragraphs
        if item.get("kind") == "heading"
    )

    content_blocks: list[str] = []
    for item in paragraphs:
        anchor = html.escape(item["original_id"])
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


def render_index_html(summary: dict[str, Any]) -> str:
    success_rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(item['source_file_name'])}</td>
          <td>{item['paragraph_count']}</td>
          <td>{html.escape(item['device'])}</td>
          <td>{html.escape(item['model_name'])}</td>
          <td><a href="{html.escape(item['reading_html_relpath'])}">Reading</a></td>
          <td><a href="{html.escape(item['bilingual_html_relpath'])}">Bilingual</a></td>
          <td><a href="{html.escape(item['json_relpath'])}">JSON</a></td>
        </tr>
        """
        for item in summary["files"]
    )
    failure_rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(item['source_file'])}</td>
          <td colspan="2">{html.escape(item['error'])}</td>
        </tr>
        """
        for item in summary["failures"]
    )

    failure_section = ""
    if summary["failures"]:
        failure_section = f"""
        <section class="panel">
          <h2>Failures</h2>
          <table>
            <thead>
              <tr>
                <th>Source File</th>
                <th colspan="2">Error</th>
              </tr>
            </thead>
            <tbody>
              {failure_rows}
            </tbody>
          </table>
        </section>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Batch Translation Index</title>
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
      max-width: 1180px;
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
    h1 {{ margin: 14px 0 10px; font-size: clamp(28px, 4vw, 42px); }}
    p {{ color: var(--muted); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
      overflow: hidden;
    }}
    th, td {{
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      font-size: 12px;
      color: var(--muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <span class="badge">Batch Translation</span>
      <h1>Output Index</h1>
      <p>Generated at {html.escape(summary['generated_at'])}</p>
      <p>Input root: {html.escape(summary['input_root'])}</p>
      <p>Output root: {html.escape(summary['output_root'])}</p>
      <p>Success: {len(summary['files'])} | Failures: {len(summary['failures'])}</p>
    </section>
    <section class="panel">
      <h2>Translated Files</h2>
      <table>
        <thead>
              <tr>
                <th>Source File</th>
                <th>Paragraphs</th>
                <th>Device</th>
                <th>Model</th>
                <th>Reading</th>
                <th>Bilingual</th>
                <th>JSON</th>
              </tr>
            </thead>
        <tbody>
          {success_rows}
        </tbody>
      </table>
    </section>
    {failure_section}
  </main>
</body>
</html>
"""


def render_directory_index_html(
    *,
    title: str,
    batch_root_rel: str,
    parent_index_rel: str | None,
    child_dirs: list[dict[str, str]],
    files: list[dict[str, Any]],
) -> str:
    child_rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(item['name'])}</td>
          <td>Directory</td>
          <td><a href="{html.escape(item['index_relpath'])}">Open index</a></td>
        </tr>
        """
        for item in child_dirs
    )
    file_rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(item['display_name'])}</td>
          <td>{item['paragraph_count']}</td>
          <td><a href="{html.escape(item['reading_relpath'])}">Reading</a> | <a href="{html.escape(item['bilingual_relpath'])}">Bilingual</a> | <a href="{html.escape(item['json_relpath'])}">JSON</a></td>
        </tr>
        """
        for item in files
    )
    parent_link = f'<a href="{html.escape(parent_index_rel)}">Up one level</a>' if parent_index_rel else ""
    batch_root_link = f'<a href="{html.escape(batch_root_rel)}">Batch root index</a>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - Directory Index</title>
  <style>
    :root {{
      --bg: #f6f1ea;
      --paper: #fffdf8;
      --ink: #221c18;
      --muted: #6f655c;
      --line: #ddd2c6;
      --accent: #005f66;
      --accent-soft: #dceff1;
    }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #fbf8f3, var(--bg));
      color: var(--ink);
      font-family: "Segoe UI", "Noto Sans SC", "Microsoft YaHei UI", sans-serif;
    }}
    .shell {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 28px 18px 48px;
    }}
    .hero, .panel {{
      background: rgba(255, 253, 248, 0.96);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 22px;
      margin-bottom: 18px;
      box-shadow: 0 16px 36px rgba(48, 35, 23, 0.05);
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
      font-size: clamp(28px, 4vw, 40px);
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-top: 12px;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <span class="badge">Directory Index</span>
      <h1>{html.escape(title)}</h1>
      <div class="links">
        {batch_root_link}
        {parent_link}
      </div>
    </section>
    <section class="panel">
      <h2>Subdirectories</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Open</th>
          </tr>
        </thead>
        <tbody>
          {child_rows or '<tr><td colspan="3">No child directories.</td></tr>'}
        </tbody>
      </table>
    </section>
    <section class="panel">
      <h2>Files</h2>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Paragraphs</th>
            <th>Outputs</th>
          </tr>
        </thead>
        <tbody>
          {file_rows or '<tr><td colspan="3">No files in this directory.</td></tr>'}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def write_directory_indexes(output_root: Path, files_summary: list[dict[str, Any]]) -> None:
    directories: dict[Path, dict[str, Any]] = {Path("."): {"child_dirs": set(), "files": []}}

    for item in files_summary:
        relative_json = Path(item["json_relpath"])
        directory = relative_json.parent
        directories.setdefault(directory, {"child_dirs": set(), "files": []})
        directories[directory]["files"].append(item)

        current = directory
        while current != Path("."):
            parent = current.parent
            directories.setdefault(parent, {"child_dirs": set(), "files": []})
            directories[parent]["child_dirs"].add(current.name)
            current = parent

    for directory in sorted(directories.keys(), key=lambda value: (len(value.parts), value.as_posix())):
        current_dir = output_root if directory == Path(".") else output_root / directory
        current_dir.mkdir(parents=True, exist_ok=True)

        child_dirs = []
        for child_name in sorted(directories[directory]["child_dirs"]):
            child_dir = directory / child_name if directory != Path(".") else Path(child_name)
            child_dirs.append(
                {
                    "name": child_name,
                    "index_relpath": os.path.relpath(output_root / child_dir / "index.html", current_dir).replace("\\", "/"),
                }
            )

        files = []
        for item in sorted(directories[directory]["files"], key=lambda entry: entry["source_file_name"]):
            files.append(
                {
                    "display_name": item.get("translated_title") or item.get("source_title") or item["source_file_name"],
                    "paragraph_count": item["paragraph_count"],
                    "reading_relpath": os.path.relpath(output_root / Path(item["reading_html_relpath"]), current_dir).replace("\\", "/"),
                    "bilingual_relpath": os.path.relpath(output_root / Path(item["bilingual_html_relpath"]), current_dir).replace("\\", "/"),
                    "json_relpath": os.path.relpath(output_root / Path(item["json_relpath"]), current_dir).replace("\\", "/"),
                }
            )

        parent_index_rel = None
        if directory != Path("."):
            parent_index_rel = os.path.relpath(output_root / directory.parent / "index.html", current_dir).replace("\\", "/")

        batch_root_rel = os.path.relpath(output_root / "index.html", current_dir).replace("\\", "/")
        title = "Batch Root" if directory == Path(".") else directory.as_posix()

        index_html_path = current_dir / "index.html"
        index_json_path = current_dir / "index.json"
        index_json_path.write_text(
            json.dumps(
                {
                    "directory": "." if directory == Path(".") else directory.as_posix(),
                    "child_dirs": child_dirs,
                    "files": files,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        index_html_path.write_text(
            render_directory_index_html(
                title=title,
                batch_root_rel=batch_root_rel,
                parent_index_rel=parent_index_rel,
                child_dirs=child_dirs,
                files=files,
            ),
            encoding="utf-8",
        )


def main() -> int:
    args = parse_args()
    source_files, root = discover_source_files(args.input, args.pattern, args.recursive)
    output_root = resolve_batch_output_root(args.output_dir, args.input, args.run_name)
    output_root.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_root": str(root),
        "output_root": str(output_root),
        "files": [],
        "failures": [],
    }

    for index, source_file in enumerate(source_files, start=1):
        relative_source = source_file.relative_to(root) if source_file.parent != source_file else Path(source_file.name)
        output_base = build_output_base(
            output_root=output_root,
            relative_source=relative_source.with_suffix(".txt"),
            preserve_structure=args.preserve_structure,
            name_template=args.name_template,
            index=index,
        )
        json_path = output_base.with_suffix(".json")
        bilingual_html_path = output_base.with_suffix(".html")
        reading_html_path = output_base.with_suffix(".reading.html")
        json_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            text = source_file.read_text(encoding=args.encoding)
            response_data = post_translation_request(
                url=args.url,
                text=text,
                batch_size=args.batch_size,
                max_new_tokens=args.max_new_tokens,
            )
            result = build_result_document(source_file, response_data)
            result["paragraphs"] = enrich_paragraphs(list(result.get("paragraphs", [])))
            source_title, translated_title = detect_titles(source_file, result["paragraphs"])
            result["source_title"] = source_title
            result["translated_title"] = translated_title
            result["title_source"] = "heading" if source_title != source_file.stem else "filename"
            json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            bilingual_html_path.write_text(
                render_translation_html(result, json_path.name, reading_html_path.name),
                encoding="utf-8",
            )
            reading_html_path.write_text(
                render_reading_html(result, json_path.name, bilingual_html_path.name),
                encoding="utf-8",
            )

            summary["files"].append(
                {
                    "source_file": str(source_file),
                    "source_file_name": relative_source.as_posix(),
                    "paragraph_count": len(result.get("paragraphs", [])),
                    "device": str(result.get("device", "")),
                    "model_name": str(result.get("model_name", "")),
                    "source_title": source_title,
                    "translated_title": translated_title,
                    "title_source": result["title_source"],
                    "json_relpath": json_path.relative_to(output_root).as_posix(),
                    "bilingual_html_relpath": bilingual_html_path.relative_to(output_root).as_posix(),
                    "reading_html_relpath": reading_html_path.relative_to(output_root).as_posix(),
                }
            )
            print(
                f"[ok] {source_file.name} -> "
                f"{json_path.relative_to(output_root)} , "
                f"{bilingual_html_path.relative_to(output_root)} , "
                f"{reading_html_path.relative_to(output_root)}"
            )
        except Exception as exc:  # noqa: BLE001
            summary["failures"].append({"source_file": str(source_file), "error": str(exc)})
            print(f"[failed] {source_file}: {exc}", file=sys.stderr)

    index_json_path = output_root / "index.json"
    index_html_path = output_root / "index.html"
    index_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    index_html_path.write_text(render_index_html(summary), encoding="utf-8")
    write_directory_indexes(output_root, summary["files"])

    print(f"Saved batch index JSON: {index_json_path}")
    print(f"Saved batch index HTML: {index_html_path}")

    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
