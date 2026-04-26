from __future__ import annotations

import html
import json
import urllib.parse
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.html_export import (
    render_kakuyomu_index_html,
    render_reading_html,
    render_translation_html,
)
from app.services.storage_paths import safe_child, validate_storage_id
from app.services.translation import TranslationRuntime
from app.services.web_extractor import extract_kakuyomu_episode


OUTPUTS_ROOT = Path("outputs").resolve()
KAKUYOMU_LIBRARY_ROOT = OUTPUTS_ROOT / "library" / "kakuyomu"


def parse_kakuyomu_ids(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 4 or parts[0] != "works" or parts[2] != "episodes":
        raise ValueError("Expected a Kakuyomu episode URL like /works/<work-id>/episodes/<episode-id>.")
    return (
        validate_storage_id(parts[1], "Kakuyomu work_id"),
        validate_storage_id(parts[3], "Kakuyomu episode_id"),
    )


def build_kakuyomu_translation_result(
    *,
    url: str,
    timeout_seconds: int,
    batch_size: int,
    max_new_tokens: int,
    translator: TranslationRuntime,
    extract_progress_callback: Callable[[], None] | None = None,
    translate_progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    episode = extract_kakuyomu_episode(url, timeout_seconds=timeout_seconds)
    if extract_progress_callback is not None:
        extract_progress_callback()
    translated_texts = translator.translate_paragraphs(
        [item.text for item in episode.paragraphs],
        source_language="ja",
        target_language="zh",
        batch_size=batch_size,
        max_new_tokens=max_new_tokens,
        progress_callback=translate_progress_callback,
    )
    work_id, episode_id = parse_kakuyomu_ids(episode.url)
    paragraphs = [
        {
            "paragraph_id": item.paragraph_id,
            "kind": item.kind,
            "original_text": item.text,
            "translated_text": translated_text,
        }
        for item, translated_text in zip(episode.paragraphs, translated_texts, strict=True)
    ]
    translated_title = paragraphs[0]["translated_text"].strip() if paragraphs and paragraphs[0]["translated_text"].strip() else episode.episode_title
    return {
        "provider": "kakuyomu",
        "source_language": "ja",
        "target_language": "zh",
        "url": episode.url,
        "work_id": work_id,
        "episode_id": episode_id,
        "work_title": episode.work_title,
        "episode_title": episode.episode_title,
        "source_title": episode.episode_title,
        "translated_title": translated_title,
        "title_source": "episode_title",
        "model_name": translator.get_model_name("ja", "zh"),
        "device": translator.device,
        "paragraphs": paragraphs,
    }


def save_kakuyomu_translation_result(result: dict[str, Any]) -> dict[str, Any]:
    saved_at = datetime.now(timezone.utc).isoformat()
    document = dict(result)
    document["saved_at"] = saved_at
    document["generated_at"] = saved_at
    document["source_file"] = str(result.get("url", ""))
    document["source_file_name"] = str(result.get("episode_title", "episode"))

    work_id = validate_storage_id(str(result["work_id"]), "Kakuyomu work_id")
    episode_id = validate_storage_id(str(result["episode_id"]), "Kakuyomu episode_id")
    document["work_id"] = work_id
    document["episode_id"] = episode_id
    episode_root = safe_child(KAKUYOMU_LIBRARY_ROOT, work_id, episode_id)
    episode_root.mkdir(parents=True, exist_ok=True)

    result_json_path = episode_root / "result.json"
    bilingual_html_path = episode_root / "bilingual.html"
    reading_html_path = episode_root / "reading.html"
    episode_index_html_path = episode_root / "index.html"

    result_json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    bilingual_html_path.write_text(
        render_translation_html(document, result_json_path.name, reading_html_path.name),
        encoding="utf-8",
    )
    reading_html_path.write_text(
        render_reading_html(document, result_json_path.name, bilingual_html_path.name),
        encoding="utf-8",
    )
    episode_index_html_path.write_text(
        render_kakuyomu_index_html(
            document,
            json_file_name=result_json_path.name,
            bilingual_file_name=bilingual_html_path.name,
            reading_file_name=reading_html_path.name,
        ),
        encoding="utf-8",
    )

    write_work_index(work_id)
    write_library_index()

    saved_files = build_saved_file_metadata(work_id, episode_id)
    return {**document, "saved_files": saved_files}


def build_saved_file_metadata(work_id: str, episode_id: str) -> dict[str, str]:
    work_id = validate_storage_id(work_id, "Kakuyomu work_id")
    episode_id = validate_storage_id(episode_id, "Kakuyomu episode_id")
    episode_root = safe_child(KAKUYOMU_LIBRARY_ROOT, work_id, episode_id)
    relative_root = episode_root.relative_to(OUTPUTS_ROOT).as_posix()
    quoted_relative_root = urllib.parse.quote(relative_root, safe="/")
    quoted_work_id = urllib.parse.quote(work_id)
    quoted_episode_id = urllib.parse.quote(episode_id)
    return {
        "storage_dir": str(episode_root),
        "result_json": str(episode_root / "result.json"),
        "bilingual_html": str(episode_root / "bilingual.html"),
        "reading_html": str(episode_root / "reading.html"),
        "episode_index_html": str(episode_root / "index.html"),
        "result_api_url": f"/ui/api/kakuyomu/result/{quoted_work_id}/{quoted_episode_id}",
        "page_url": f"/?work_id={urllib.parse.quote(work_id)}&episode_id={urllib.parse.quote(episode_id)}",
        "result_json_url": f"/saved-files/{quoted_relative_root}/result.json",
        "bilingual_html_url": f"/saved-files/{quoted_relative_root}/bilingual.html",
        "reading_html_url": f"/saved-files/{quoted_relative_root}/reading.html",
        "episode_index_html_url": f"/saved-files/{quoted_relative_root}/index.html",
    }


def load_saved_kakuyomu_result(work_id: str, episode_id: str) -> dict[str, Any]:
    work_id = validate_storage_id(work_id, "Kakuyomu work_id")
    episode_id = validate_storage_id(episode_id, "Kakuyomu episode_id")
    result_path = safe_child(KAKUYOMU_LIBRARY_ROOT, work_id, episode_id) / "result.json"
    if not result_path.exists():
        raise FileNotFoundError(f"Saved Kakuyomu result not found for work '{work_id}' episode '{episode_id}'.")
    document = json.loads(result_path.read_text(encoding="utf-8"))
    document["saved_files"] = build_saved_file_metadata(work_id, episode_id)
    return document


def list_saved_kakuyomu_results(limit: int = 20) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not KAKUYOMU_LIBRARY_ROOT.exists():
        return items

    for result_path in KAKUYOMU_LIBRARY_ROOT.glob("*/*/result.json"):
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        try:
            work_id = validate_storage_id(str(data.get("work_id") or result_path.parent.parent.name), "Kakuyomu work_id")
            episode_id = validate_storage_id(str(data.get("episode_id") or result_path.parent.name), "Kakuyomu episode_id")
            saved_files = build_saved_file_metadata(work_id, episode_id)
        except ValueError:
            continue
        items.append(
            {
                "work_id": work_id,
                "episode_id": episode_id,
                "work_title": str(data.get("work_title", "")),
                "episode_title": str(data.get("episode_title", "")),
                "translated_title": str(data.get("translated_title", "")),
                "saved_at": str(data.get("saved_at", "")),
                "url": str(data.get("url", "")),
                "page_url": f"/?work_id={urllib.parse.quote(work_id)}&episode_id={urllib.parse.quote(episode_id)}",
                "result_api_url": saved_files["result_api_url"],
                "bilingual_html_url": saved_files["bilingual_html_url"],
                "reading_html_url": saved_files["reading_html_url"],
            }
        )

    items.sort(key=lambda item: item.get("saved_at", ""), reverse=True)
    return items[:limit]


def write_work_index(work_id: str) -> None:
    work_id = validate_storage_id(work_id, "Kakuyomu work_id")
    work_root = safe_child(KAKUYOMU_LIBRARY_ROOT, work_id)
    work_root.mkdir(parents=True, exist_ok=True)
    episodes: list[dict[str, Any]] = []
    work_title = work_id

    for result_path in sorted(work_root.glob("*/result.json")):
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        try:
            episode_id = validate_storage_id(result_path.parent.name, "Kakuyomu episode_id")
            saved_files = build_saved_file_metadata(work_id, episode_id)
        except ValueError:
            continue
        work_title = str(data.get("work_title", work_title))
        episodes.append(
            {
                "episode_id": episode_id,
                "episode_title": str(data.get("episode_title", "")),
                "translated_title": str(data.get("translated_title", "")),
                "saved_at": str(data.get("saved_at", "")),
                "page_url": f"/?work_id={urllib.parse.quote(work_id)}&episode_id={urllib.parse.quote(episode_id)}",
                "bilingual_html_url": saved_files["bilingual_html_url"],
                "reading_html_url": saved_files["reading_html_url"],
            }
        )

    episodes.sort(key=lambda item: item.get("saved_at", ""), reverse=True)
    (work_root / "index.json").write_text(
        json.dumps(
            {
                "provider": "kakuyomu",
                "work_id": work_id,
                "work_title": work_title,
                "episode_count": len(episodes),
                "episodes": episodes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (work_root / "index.html").write_text(render_work_index_html(work_id, work_title, episodes), encoding="utf-8")


def write_library_index() -> None:
    KAKUYOMU_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    works: list[dict[str, Any]] = []
    for work_root in sorted(path for path in KAKUYOMU_LIBRARY_ROOT.iterdir() if path.is_dir()):
        try:
            folder_work_id = validate_storage_id(work_root.name, "Kakuyomu work_id")
        except ValueError:
            continue
        index_path = work_root / "index.json"
        if not index_path.exists():
            continue
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        try:
            work_id = validate_storage_id(str(data.get("work_id", folder_work_id)), "Kakuyomu work_id")
        except ValueError:
            continue
        works.append(
            {
                "work_id": work_id,
                "work_title": str(data.get("work_title", work_root.name)),
                "episode_count": int(data.get("episode_count", 0)),
                "latest_saved_at": str(data.get("episodes", [{}])[0].get("saved_at", "")) if data.get("episodes") else "",
            }
        )

    works.sort(key=lambda item: item.get("latest_saved_at", ""), reverse=True)
    (KAKUYOMU_LIBRARY_ROOT / "index.json").write_text(
        json.dumps({"provider": "kakuyomu", "works": works}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (KAKUYOMU_LIBRARY_ROOT / "index.html").write_text(render_library_index_html(works), encoding="utf-8")


def render_work_index_html(work_id: str, work_title: str, episodes: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(item['episode_id'])}</td>
          <td>{html.escape(item['episode_title'])}</td>
          <td>{html.escape(item['translated_title'])}</td>
          <td>{html.escape(item['saved_at'])}</td>
          <td><a href="{html.escape(item['page_url'])}">Open UI</a></td>
          <td><a href="{html.escape(item['reading_html_url'])}">Reading</a> | <a href="{html.escape(item['bilingual_html_url'])}">Compare</a></td>
        </tr>
        """
        for item in episodes
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(work_title)} - Work Index</title>
  <style>
    body {{ font-family: "Segoe UI", sans-serif; margin: 0; padding: 24px; background: #f6f1ea; color: #1f1a17; }}
    .panel {{ max-width: 1080px; margin: 0 auto; background: #fffdf8; border: 1px solid #ddd2c6; border-radius: 18px; padding: 24px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 12px 10px; border-bottom: 1px solid #ddd2c6; vertical-align: top; }}
    a {{ color: #0f5f61; text-decoration: none; font-weight: 600; }}
  </style>
</head>
<body>
  <section class="panel">
    <h1>{html.escape(work_title)}</h1>
    <p>Work ID: {html.escape(work_id)}</p>
    <table>
      <thead>
        <tr>
          <th>Episode ID</th>
          <th>Episode Title</th>
          <th>Translated Title</th>
          <th>Saved At</th>
          <th>UI</th>
          <th>Saved Files</th>
        </tr>
      </thead>
      <tbody>
        {rows or '<tr><td colspan="6">No episodes saved.</td></tr>'}
      </tbody>
    </table>
  </section>
</body>
</html>
"""


def render_library_index_html(works: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(item['work_id'])}</td>
          <td>{html.escape(item['work_title'])}</td>
          <td>{item['episode_count']}</td>
          <td>{html.escape(item['latest_saved_at'])}</td>
          <td><a href="{html.escape('/saved-files/library/kakuyomu/' + urllib.parse.quote(item['work_id']) + '/index.html')}">Open Work Index</a></td>
        </tr>
        """
        for item in works
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kakuyomu Library</title>
  <style>
    body {{ font-family: "Segoe UI", sans-serif; margin: 0; padding: 24px; background: #f6f1ea; color: #1f1a17; }}
    .panel {{ max-width: 1080px; margin: 0 auto; background: #fffdf8; border: 1px solid #ddd2c6; border-radius: 18px; padding: 24px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 12px 10px; border-bottom: 1px solid #ddd2c6; vertical-align: top; }}
    a {{ color: #0f5f61; text-decoration: none; font-weight: 600; }}
  </style>
</head>
<body>
  <section class="panel">
    <h1>Kakuyomu Library</h1>
    <table>
      <thead>
        <tr>
          <th>Work ID</th>
          <th>Work Title</th>
          <th>Episodes</th>
          <th>Latest Saved At</th>
          <th>Work Index</th>
        </tr>
      </thead>
      <tbody>
        {rows or '<tr><td colspan="5">No saved works yet.</td></tr>'}
      </tbody>
    </table>
  </section>
</body>
</html>
"""
