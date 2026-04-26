from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.pdf_extractor import build_pdf_extraction_debug_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a PDF extraction debug report as UTF-8 JSON.")
    parser.add_argument("pdf", type=Path, help="PDF file to inspect.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/pdf_extraction_debug_report.json"),
        help="Output JSON path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_pdf_extraction_debug_report(args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = report["counts"]
    filter_report = report["filter_report"]
    print(f"Saved PDF extraction debug report: {args.output.resolve()}")
    print(f"Pages: {report['page_count']}")
    print(f"Main content start page: {report['main_content_start_page']}")
    print(f"End matter start page: {filter_report.get('end_matter_start_page')}")
    print(f"Raw candidates: {counts['raw_candidates']}")
    print(f"Merged blocks: {counts['merged_blocks']}")
    print(f"Filtered blocks: {counts['filtered_blocks']}")
    print(f"Filtered kinds: {report['filtered_kind_counts']}")
    print(f"Filter reasons: {filter_report.get('reason_counts', {})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
