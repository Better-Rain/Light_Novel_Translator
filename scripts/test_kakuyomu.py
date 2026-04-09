from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract a Kakuyomu episode through the local API and save the response.")
    parser.add_argument("--url", required=True, help="Kakuyomu episode URL.")
    parser.add_argument("--api-url", default="http://127.0.0.1:7860/extract/web/kakuyomu")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path("outputs/kakuyomu-extract.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = {
        "url": args.url,
        "timeout_seconds": args.timeout_seconds,
    }
    request = urllib.request.Request(
        args.api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        data = json.loads(response.read().decode("utf-8"))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved response to: {args.output.resolve()}")
    print(f"Work: {data.get('work_title')}")
    print(f"Episode: {data.get('episode_title')}")
    print(f"Paragraphs: {len(data.get('paragraphs', []))}")


if __name__ == "__main__":
    main()
