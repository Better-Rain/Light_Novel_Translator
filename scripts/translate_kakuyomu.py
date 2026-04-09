from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.html_export import (
    default_run_directory,
    render_kakuyomu_index_html,
    render_reading_html,
    render_translation_html,
    sanitize_filename_component,
    suggest_output_stem,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a Kakuyomu episode through the local API, translate it, and save JSON/HTML outputs.",
    )
    parser.add_argument("--url", required=True, help="Kakuyomu episode URL.")
    parser.add_argument("--api-url", default="http://127.0.0.1:7860/translate/web/kakuyomu")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/kakuyomu"))
    parser.add_argument(
        "--run-name",
        help="Optional output folder name created under --output-dir. Defaults to <work-title>-<timestamp>.",
    )
    parser.add_argument(
        "--output-stem",
        help="Optional base name for JSON/HTML output files. Defaults to the translated title or episode title.",
    )
    return parser.parse_args()


def post_request(args: argparse.Namespace) -> dict:
    payload = {
        "url": args.url,
        "timeout_seconds": args.timeout_seconds,
        "batch_size": args.batch_size,
        "max_new_tokens": args.max_new_tokens,
    }
    request = urllib.request.Request(
        args.api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {args.api_url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to reach local service at {args.api_url}: {exc.reason}") from exc


def resolve_output_root(args: argparse.Namespace, result: dict) -> Path:
    if args.run_name:
        folder_name = sanitize_filename_component(args.run_name)
        return args.output_dir.expanduser().resolve() / folder_name
    return default_run_directory(args.output_dir, title=str(result.get("work_title", "kakuyomu")))


def build_output_document(result: dict) -> dict:
    document = dict(result)
    document["generated_at"] = datetime.now(timezone.utc).isoformat()
    document["source_file"] = str(result.get("url", ""))
    document["source_file_name"] = str(result.get("episode_title", "episode"))
    document["title_source"] = "episode_title"
    return document


def write_outputs(args: argparse.Namespace, result: dict) -> tuple[Path, Path, Path, Path]:
    document = build_output_document(result)
    output_root = resolve_output_root(args, document)
    output_root.mkdir(parents=True, exist_ok=True)

    output_stem = suggest_output_stem(
        args.output_stem or "",
        str(document.get("translated_title", "")),
        str(document.get("episode_title", "")),
    )
    json_path = output_root / f"{output_stem}.json"
    bilingual_html_path = output_root / f"{output_stem}.html"
    reading_html_path = output_root / f"{output_stem}.reading.html"
    index_json_path = output_root / "index.json"
    index_html_path = output_root / "index.html"

    json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    bilingual_html_path.write_text(
        render_translation_html(document, json_path.name, reading_html_path.name),
        encoding="utf-8",
    )
    reading_html_path.write_text(
        render_reading_html(document, json_path.name, bilingual_html_path.name),
        encoding="utf-8",
    )

    index_payload = {
        "provider": document.get("provider"),
        "url": document.get("url"),
        "work_title": document.get("work_title"),
        "episode_title": document.get("episode_title"),
        "translated_title": document.get("translated_title"),
        "model_name": document.get("model_name"),
        "device": document.get("device"),
        "paragraph_count": len(document.get("paragraphs", [])),
        "json_file": json_path.name,
        "bilingual_html_file": bilingual_html_path.name,
        "reading_html_file": reading_html_path.name,
    }
    index_json_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    index_html_path.write_text(
        render_kakuyomu_index_html(
            document,
            json_file_name=json_path.name,
            bilingual_file_name=bilingual_html_path.name,
            reading_file_name=reading_html_path.name,
        ),
        encoding="utf-8",
    )
    return json_path, bilingual_html_path, reading_html_path, index_html_path


def main() -> None:
    args = parse_args()
    result = post_request(args)
    json_path, bilingual_html_path, reading_html_path, index_html_path = write_outputs(args, result)

    print(f"Saved JSON: {json_path.resolve()}")
    print(f"Saved bilingual HTML: {bilingual_html_path.resolve()}")
    print(f"Saved reading HTML: {reading_html_path.resolve()}")
    print(f"Saved index HTML: {index_html_path.resolve()}")
    print(f"Work: {result.get('work_title')}")
    print(f"Episode: {result.get('episode_title')}")
    print(f"Translated title: {result.get('translated_title')}")
    print(f"Paragraphs: {len(result.get('paragraphs', []))}")
    print(f"Model: {result.get('model_name')}")
    print(f"Device: {result.get('device')}")


if __name__ == "__main__":
    main()
