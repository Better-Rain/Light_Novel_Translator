from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app
from app.schemas import PDFTranslateResponse
from app.services.pdf_extractor import _looks_like_chapter_title, _looks_like_sentence, extract_pdf_paragraphs
from app.services.pdf_pipeline import build_pdf_translation_result
from app.services.storage_paths import safe_child, validate_storage_id


DEFAULT_SAMPLE_PDF = Path(
    "The Death and Life of Great American Cities (Jane Jacobs) (z-library.sk, 1lib.sk, z-lib.sk).pdf"
)
BAD_STORAGE_IDS = ["..", ".", "a/b", r"a\b", "C:bad", "", " ok"]
KNOWN_BAD_HEADINGS = {"And", "Third,", "I", "100.", "Index"}


class FakeTranslator:
    device = "test"

    def get_model_name(self, source_language: str, target_language: str) -> str:
        return f"fake-{source_language}-{target_language}"

    def translate_paragraphs(self, paragraphs: list[str], **_: Any) -> list[str]:
        return [f"译文:{paragraph[:24]}" for paragraph in paragraphs]


def verify_storage_paths() -> None:
    for storage_id in BAD_STORAGE_IDS:
        try:
            validate_storage_id(storage_id, "test id")
        except ValueError:
            continue
        raise AssertionError(f"Unsafe storage id was accepted: {storage_id!r}")

    safe_path = safe_child(Path("outputs/library/pdf"), "valid id-123")
    if safe_path.name != "valid id-123":
        raise AssertionError(f"Unexpected safe child path: {safe_path}")
    print("[ok] storage id validation rejects traversal and invalid path characters")


def verify_api_rejects_bad_ids() -> None:
    client = TestClient(app)
    health = client.get("/health")
    if health.status_code != 200 or health.json().get("status") != "ok":
        raise AssertionError(f"Health check failed: {health.status_code} {health.text}")

    pdf_response = client.get("/ui/api/pdf/result/C%3Abad")
    if pdf_response.status_code != 400:
        raise AssertionError(f"Expected PDF bad id 400, got {pdf_response.status_code}: {pdf_response.text}")

    kakuyomu_response = client.get("/ui/api/kakuyomu/result/C%3Abad/x")
    if kakuyomu_response.status_code != 400:
        raise AssertionError(
            f"Expected Kakuyomu bad id 400, got {kakuyomu_response.status_code}: {kakuyomu_response.text}"
        )
    print("[ok] saved-result APIs reject invalid identifiers")


def verify_debug_schema(sample_pdf: Path) -> None:
    result = build_pdf_translation_result(
        file_path=str(sample_pdf),
        source_language="en",
        batch_size=8,
        max_new_tokens=64,
        debug_max_pages=2,
        debug_max_paragraphs=4,
        translator=FakeTranslator(),
    )
    response = PDFTranslateResponse(**result)
    if response.debug_limits is None:
        raise AssertionError("debug_limits was dropped by PDFTranslateResponse")
    if response.debug_limits.max_pages != 2 or response.debug_limits.max_paragraphs != 4:
        raise AssertionError(f"Unexpected debug limits: {response.debug_limits}")
    if len(response.paragraphs) != 4:
        raise AssertionError(f"Expected 4 debug paragraphs, got {len(response.paragraphs)}")
    if not response.document_id.endswith("-debug-p2-n4"):
        raise AssertionError(f"Unexpected debug document_id: {response.document_id}")
    print("[ok] PDF debug limits survive response schema and document id suffixing")


def verify_japanese_pdf_heuristics() -> None:
    if not _looks_like_chapter_title("第1章 はじめに"):
        raise AssertionError("Japanese chapter heading was not recognized")
    if not _looks_like_chapter_title("プロローグ"):
        raise AssertionError("Japanese prologue heading was not recognized")
    if not _looks_like_sentence("これはかなり長い日本語の本文であり、見出しではなく通常の段落として扱われるべき文章です。"):
        raise AssertionError("Long Japanese body sentence was not recognized")
    print("[ok] Japanese PDF heading/body heuristics recognize basic chapter and sentence patterns")


def verify_sample_pdf(sample_pdf: Path) -> None:
    paragraphs = extract_pdf_paragraphs(sample_pdf)
    if not paragraphs:
        raise AssertionError("Sample PDF produced no paragraphs")
    if paragraphs[0].page_number != 12 or paragraphs[0].text.strip() != "Introduction":
        raise AssertionError(
            f"Unexpected sample start: page={paragraphs[0].page_number} text={paragraphs[0].text[:80]!r}"
        )
    if paragraphs[-1].page_number >= 452:
        raise AssertionError(f"End matter was not trimmed; last page is {paragraphs[-1].page_number}")

    headings = [item for item in paragraphs if item.kind != "paragraph"]
    bad_hits = sorted({item.text for item in headings if item.text in KNOWN_BAD_HEADINGS})
    if bad_hits:
        raise AssertionError(f"Known bad heading fragments still present: {bad_hits}")

    counts = Counter(item.kind for item in paragraphs)
    print(
        "[ok] sample PDF extraction "
        f"count={len(paragraphs)} first_page={paragraphs[0].page_number} "
        f"last_page={paragraphs[-1].page_number} kinds={dict(counts)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify recent local fixes without loading real translation models.")
    parser.add_argument("--sample-pdf", type=Path, default=DEFAULT_SAMPLE_PDF)
    parser.add_argument("--skip-pdf", action="store_true", help="Skip checks that need the sample PDF file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify_storage_paths()
    verify_api_rejects_bad_ids()
    verify_japanese_pdf_heuristics()

    sample_pdf = args.sample_pdf.expanduser().resolve()
    if args.skip_pdf:
        print("[skip] sample PDF checks")
        return 0
    if not sample_pdf.exists():
        raise FileNotFoundError(f"Sample PDF not found: {sample_pdf}")

    verify_sample_pdf(sample_pdf)
    verify_debug_schema(sample_pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
