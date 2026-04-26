from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import urllib.parse
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.html_export import (
    render_reading_html,
    render_translation_html,
    sanitize_filename_component,
)
from app.services.pdf_extractor import extract_pdf_paragraphs
from app.services.storage_paths import safe_child, validate_storage_id
from app.services.translation import TranslationRuntime


LOGGER = logging.getLogger(__name__)
OUTPUTS_ROOT = Path("outputs").resolve()
PDF_LIBRARY_ROOT = OUTPUTS_ROOT / "library" / "pdf"


def build_pdf_translation_result(
    *,
    file_path: str,
    source_language: str,
    batch_size: int,
    max_new_tokens: int,
    translator: TranslationRuntime,
    debug_max_pages: int | None = None,
    debug_max_paragraphs: int | None = None,
    extract_progress_callback: Callable[[], None] | None = None,
    translate_progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    source_path = Path(file_path).expanduser().resolve()
    paragraphs = extract_pdf_paragraphs(source_path)
    paragraphs, debug_limits = _apply_debug_limits(
        paragraphs,
        max_pages=debug_max_pages,
        max_paragraphs=debug_max_paragraphs,
    )
    if not paragraphs:
        detail = "No PDF paragraphs remained after extraction"
        if debug_limits is not None:
            detail = f"{detail} and debug limits"
        raise ValueError(f"{detail}: {source_path}")
    if extract_progress_callback is not None:
        extract_progress_callback()

    translated_texts = translator.translate_paragraphs(
        [item.text for item in paragraphs],
        source_language=source_language,
        target_language="zh",
        batch_size=batch_size,
        max_new_tokens=max_new_tokens,
        progress_callback=translate_progress_callback,
    )
    document_id = build_pdf_document_id(source_path)
    if debug_limits is not None:
        document_id = _build_debug_document_id(document_id, debug_limits)
    document_title = detect_pdf_title(source_path, paragraphs)
    translated_title = document_title
    for item, translated_text in zip(paragraphs, translated_texts, strict=True):
        if _is_heading_kind(item.kind) and translated_text.strip():
            translated_title = translated_text.strip()
            break

    result = {
        "provider": "pdf",
        "source_language": source_language,
        "target_language": "zh",
        "document_id": document_id,
        "document_title": document_title,
        "source_title": document_title,
        "translated_title": translated_title,
        "source_file": str(source_path),
        "source_file_name": source_path.name,
        "model_name": translator.get_model_name(source_language, "zh"),
        "device": translator.device,
        "paragraphs": [
            {
                "paragraph_id": item.paragraph_id,
                "page_number": item.page_number,
                "kind": item.kind,
                "section_title": item.section_title,
                "original_text": item.text,
                "translated_text": translated_text,
            }
            for item, translated_text in zip(paragraphs, translated_texts, strict=True)
        ],
    }
    if debug_limits is not None:
        result["debug_limits"] = debug_limits
    return result


def _apply_debug_limits(
    paragraphs: list[Any],
    *,
    max_pages: int | None = None,
    max_paragraphs: int | None = None,
) -> tuple[list[Any], dict[str, int] | None]:
    if max_pages is None:
        max_pages = _read_positive_int_env("PDF_DEBUG_MAX_PAGES")
    if max_paragraphs is None:
        max_paragraphs = _read_positive_int_env("PDF_DEBUG_MAX_PARAGRAPHS")
    if max_pages is None and max_paragraphs is None:
        return paragraphs, None

    limited = list(paragraphs)
    debug_info: dict[str, int] = {"original_paragraph_count": len(paragraphs)}

    if max_pages is not None and limited:
        first_page = min(getattr(item, "page_number", 1) for item in limited)
        last_page = first_page + max_pages - 1
        limited = [item for item in limited if getattr(item, "page_number", first_page) <= last_page]
        debug_info["max_pages"] = max_pages
        debug_info["kept_through_page"] = last_page

    if max_paragraphs is not None:
        limited = limited[:max_paragraphs]
        debug_info["max_paragraphs"] = max_paragraphs

    debug_info["limited_paragraph_count"] = len(limited)
    return limited, debug_info


def _read_positive_int_env(name: str) -> int | None:
    raw_value = os.getenv(name)
    if not raw_value:
        return None
    try:
        parsed = int(raw_value)
    except ValueError:
        LOGGER.warning("Ignoring invalid %s=%r; expected a positive integer.", name, raw_value)
        return None
    if parsed <= 0:
        LOGGER.warning("Ignoring invalid %s=%r; expected a positive integer.", name, raw_value)
        return None
    return parsed


def _is_heading_kind(kind: str) -> bool:
    return kind in {"chapter_heading", "heading"}


def _build_debug_document_id(document_id: str, debug_limits: dict[str, int]) -> str:
    suffix_parts: list[str] = ["debug"]
    if "max_pages" in debug_limits:
        suffix_parts.append(f"p{debug_limits['max_pages']}")
    if "max_paragraphs" in debug_limits:
        suffix_parts.append(f"n{debug_limits['max_paragraphs']}")
    suffix = "-".join(suffix_parts)
    return f"{document_id}-{suffix}"


def save_pdf_translation_result(result: dict[str, Any]) -> dict[str, Any]:
    saved_at = datetime.now(timezone.utc).isoformat()
    document = dict(result)
    document["saved_at"] = saved_at
    document["generated_at"] = saved_at

    document_id = validate_storage_id(str(document["document_id"]), "PDF document_id")
    document["document_id"] = document_id
    document_root = safe_child(PDF_LIBRARY_ROOT, document_id)
    document_root.mkdir(parents=True, exist_ok=True)

    result_json_path = document_root / "result.json"
    bilingual_html_path = document_root / "bilingual.html"
    reading_html_path = document_root / "reading.html"
    document_index_html_path = document_root / "index.html"

    result_json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    bilingual_html_path.write_text(
        render_translation_html(document, result_json_path.name, reading_html_path.name),
        encoding="utf-8",
    )
    reading_html_path.write_text(
        render_reading_html(document, result_json_path.name, bilingual_html_path.name),
        encoding="utf-8",
    )
    document_index_html_path.write_text(
        render_pdf_index_html(document, result_json_path.name, bilingual_html_path.name, reading_html_path.name),
        encoding="utf-8",
    )

    write_pdf_library_index()
    saved_files = build_pdf_saved_file_metadata(document_id)
    return {**document, "saved_files": saved_files}


def load_saved_pdf_result(document_id: str) -> dict[str, Any]:
    document_id = validate_storage_id(document_id, "PDF document_id")
    result_path = safe_child(PDF_LIBRARY_ROOT, document_id) / "result.json"
    if not result_path.exists():
        raise FileNotFoundError(f"Saved PDF result not found for document '{document_id}'.")
    document = json.loads(result_path.read_text(encoding="utf-8"))
    document["saved_files"] = build_pdf_saved_file_metadata(document_id)
    return document


def list_saved_pdf_results(limit: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not PDF_LIBRARY_ROOT.exists():
        return items

    for result_path in PDF_LIBRARY_ROOT.glob("*/result.json"):
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        try:
            document_id = validate_storage_id(str(data.get("document_id") or result_path.parent.name), "PDF document_id")
            saved_files = build_pdf_saved_file_metadata(document_id)
        except ValueError:
            continue
        debug_limits = data.get("debug_limits")
        items.append(
            {
                "document_id": document_id,
                "document_title": str(data.get("document_title", document_id)),
                "translated_title": str(data.get("translated_title", "")),
                "source_file_name": str(data.get("source_file_name", "")),
                "saved_at": str(data.get("saved_at", "")),
                "source_file": str(data.get("source_file", "")),
                "source_language": str(data.get("source_language", "en")),
                "debug_limits": debug_limits if isinstance(debug_limits, dict) else None,
                "is_debug": isinstance(debug_limits, dict) or "-debug-" in document_id,
                "page_url": f"/?provider=pdf&document_id={urllib.parse.quote(document_id)}",
                "result_api_url": f"/ui/api/pdf/result/{urllib.parse.quote(document_id)}",
                "bilingual_html_url": saved_files["bilingual_html_url"],
                "reading_html_url": saved_files["reading_html_url"],
            }
        )

    items.sort(key=lambda item: item.get("saved_at", ""), reverse=True)
    return items[:limit]


def build_pdf_saved_file_metadata(document_id: str) -> dict[str, str]:
    document_id = validate_storage_id(document_id, "PDF document_id")
    document_root = safe_child(PDF_LIBRARY_ROOT, document_id)
    relative_root = document_root.relative_to(OUTPUTS_ROOT).as_posix()
    quoted_relative_root = urllib.parse.quote(relative_root, safe="/")
    quoted_document_id = urllib.parse.quote(document_id)
    return {
        "storage_dir": str(document_root),
        "result_json": str(document_root / "result.json"),
        "bilingual_html": str(document_root / "bilingual.html"),
        "reading_html": str(document_root / "reading.html"),
        "document_index_html": str(document_root / "index.html"),
        "result_api_url": f"/ui/api/pdf/result/{quoted_document_id}",
        "page_url": f"/?provider=pdf&document_id={urllib.parse.quote(document_id)}",
        "result_json_url": f"/saved-files/{quoted_relative_root}/result.json",
        "bilingual_html_url": f"/saved-files/{quoted_relative_root}/bilingual.html",
        "reading_html_url": f"/saved-files/{quoted_relative_root}/reading.html",
        "document_index_html_url": f"/saved-files/{quoted_relative_root}/index.html",
    }


def build_pdf_document_id(file_path: str | Path) -> str:
    source_path = Path(file_path).expanduser().resolve()
    digest = hashlib.sha1()
    with source_path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    stem = sanitize_filename_component(source_path.stem)
    return f"{stem[:48]}-{digest.hexdigest()[:12]}"


def detect_pdf_title(file_path: str | Path, paragraphs: list[dict[str, Any]] | list[Any]) -> str:
    source_path = Path(file_path)
    return clean_pdf_title_from_filename(source_path.stem)


def clean_pdf_title_from_filename(stem: str) -> str:
    title = stem
    title = title.replace("_", " ").strip()
    title = title.replace("  ", " ")
    title = title.replace("(z-library.sk, 1lib.sk, z-lib.sk)", "").strip()
    title = title.strip(" -_")
    return title or "PDF Document"


def write_pdf_library_index() -> None:
    PDF_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    items = list_saved_pdf_results(limit=500)
    (PDF_LIBRARY_ROOT / "index.json").write_text(
        json.dumps({"provider": "pdf", "documents": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (PDF_LIBRARY_ROOT / "index.html").write_text(render_pdf_library_index_html(items), encoding="utf-8")


def render_pdf_index_html(
    result: dict[str, Any],
    json_file_name: str,
    bilingual_file_name: str,
    reading_file_name: str,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(result.get("document_title", "PDF Document")))}</title>
  <style>
    body {{ font-family: "Segoe UI", sans-serif; margin: 0; padding: 24px; background: #f6f1ea; color: #1f1a17; }}
    .panel {{ max-width: 980px; margin: 0 auto; background: #fffdf8; border: 1px solid #ddd2c6; border-radius: 18px; padding: 24px; }}
    .links {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 18px; }}
    a {{ color: #0f5f61; text-decoration: none; font-weight: 600; }}
    .meta {{ color: #6a625a; line-height: 1.6; }}
  </style>
</head>
<body>
  <section class="panel">
    <h1>{html.escape(str(result.get("translated_title", result.get("document_title", "PDF Document"))))}</h1>
    <p class="meta">
      Source: {html.escape(str(result.get("source_file", "")))}<br>
      Document ID: {html.escape(str(result.get("document_id", "")))}<br>
      Source Language: {html.escape(str(result.get("source_language", "")))}<br>
      Model: {html.escape(str(result.get("model_name", "")))} / {html.escape(str(result.get("device", "")))}
    </p>
    <div class="links">
      <a href="{html.escape(json_file_name)}">Open JSON</a>
      <a href="{html.escape(reading_file_name)}">Open Reading View</a>
      <a href="{html.escape(bilingual_file_name)}">Open Compare View</a>
      <a href="/">Open Web UI</a>
    </div>
  </section>
</body>
</html>
"""


def render_pdf_library_index_html(items: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(item['document_id'])}</td>
          <td>{html.escape(item['document_title'])}</td>
          <td>{html.escape(item['source_file_name'])}</td>
          <td>{html.escape(item['saved_at'])}</td>
          <td><a href="{html.escape(item['page_url'])}">Open UI</a></td>
          <td><a href="{html.escape(item['reading_html_url'])}">Reading</a> | <a href="{html.escape(item['bilingual_html_url'])}">Compare</a></td>
        </tr>
        """
        for item in items
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PDF Library</title>
  <style>
    body {{ font-family: "Segoe UI", sans-serif; margin: 0; padding: 24px; background: #f6f1ea; color: #1f1a17; }}
    .panel {{ max-width: 1180px; margin: 0 auto; background: #fffdf8; border: 1px solid #ddd2c6; border-radius: 18px; padding: 24px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 12px 10px; border-bottom: 1px solid #ddd2c6; vertical-align: top; }}
    a {{ color: #0f5f61; text-decoration: none; font-weight: 600; }}
  </style>
</head>
<body>
  <section class="panel">
    <h1>PDF Library</h1>
    <table>
      <thead>
        <tr>
          <th>Document ID</th>
          <th>Title</th>
          <th>Source File</th>
          <th>Saved At</th>
          <th>UI</th>
          <th>Saved Files</th>
        </tr>
      </thead>
      <tbody>
        {rows or '<tr><td colspan="6">No saved documents yet.</td></tr>'}
      </tbody>
    </table>
  </section>
</body>
</html>
"""
