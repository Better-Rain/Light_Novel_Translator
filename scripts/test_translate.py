from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a UTF-8 translation request and save the response to a file.")
    parser.add_argument("--url", default="http://127.0.0.1:7860/translate/ja")
    parser.add_argument("--text-file", type=Path, help="Optional UTF-8 text file to translate.")
    parser.add_argument(
        "--text",
        default="今日はいい天気です。\n\n本を読みたいです。",
        help="Fallback text used when --text-file is not provided.",
    )
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--output", type=Path, default=Path("outputs/translate-smoke.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    text = args.text_file.read_text(encoding="utf-8") if args.text_file else args.text

    payload = {
        "text": text,
        "batch_size": args.batch_size,
        "max_new_tokens": args.max_new_tokens,
    }
    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        args.url,
        data=request_body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        response_body = response.read()

    data = json.loads(response_body.decode("utf-8"))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved response to: {args.output.resolve()}")
    print(f"Device: {data.get('device')}")
    print(f"Model: {data.get('model_name')}")
    print("Open the saved JSON file in VS Code to inspect the real Japanese and Chinese text.")


if __name__ == "__main__":
    main()
