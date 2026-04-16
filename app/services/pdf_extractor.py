from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.schemas import RawPDFParagraph


SECTION_PATTERN = re.compile(
    r"^(chapter|section|part|appendix|preface|introduction|prologue|epilogue)\b|^\d+(\.\d+)*\b|^[IVXLC]+\.\s",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _BlockCandidate:
    text: str
    page_number: int
    bbox: tuple[float, float, float, float]
    kind: str


def extract_pdf_paragraphs(file_path: str | Path) -> list[RawPDFParagraph]:
    pdf_path = Path(file_path).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {pdf_path}")

    try:
        document = fitz.open(pdf_path)
    except fitz.FileDataError as exc:
        raise ValueError(f"Unable to open PDF: {pdf_path}") from exc

    with document:
        body_font_size = _estimate_body_font_size(document)
        repeated_margin_texts = _find_repeated_margin_texts(document)
        raw_blocks: list[_BlockCandidate] = []

        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            page_dict = page.get_text("dict")
            blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 0]

            for block in blocks:
                text = _extract_block_text(block)
                if not text:
                    continue
                if text in repeated_margin_texts:
                    continue
                if _is_noise_block(text, block, page.rect.height):
                    continue
                raw_blocks.append(
                    _BlockCandidate(
                        text=text,
                        page_number=page_index + 1,
                        bbox=tuple(block.get("bbox", [0.0, 0.0, 0.0, 0.0])),
                        kind=_classify_block(text, block, body_font_size),
                    )
                )

        merged_blocks = _merge_adjacent_blocks(raw_blocks, body_font_size)
        paragraphs: list[RawPDFParagraph] = []
        section_title: str | None = None

        for index, block in enumerate(merged_blocks, start=1):
            if block.kind == "heading":
                section_title = block.text
            paragraphs.append(
                RawPDFParagraph(
                    paragraph_id=f"pdf-p{index:05d}",
                    page_number=block.page_number,
                    kind="heading" if block.kind == "heading" else "paragraph",
                    section_title=section_title,
                    text=block.text,
                )
            )

        return paragraphs


def _estimate_body_font_size(document: fitz.Document) -> float:
    sizes: list[float] = []

    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    size = span.get("size", 0.0)
                    if text and size > 0:
                        sizes.append(size)

    if not sizes:
        raise ValueError("No extractable text found in the PDF.")

    return statistics.median(sizes)


def _find_repeated_margin_texts(document: fitz.Document) -> set[str]:
    margin_occurrences: Counter[str] = Counter()

    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        page_dict = page.get_text("dict")
        page_height = page.rect.height
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            text = _normalize_margin_text(_extract_block_text(block))
            if not text or len(text) > 120:
                continue
            bbox = block.get("bbox", [0.0, 0.0, 0.0, 0.0])
            top = bbox[1]
            bottom = bbox[3]
            if top < page_height * 0.09 or bottom > page_height * 0.94:
                margin_occurrences[text] += 1

    repeated_texts: set[str] = set()
    minimum_occurrences = 3 if document.page_count >= 8 else 2
    for text, count in margin_occurrences.items():
        if count >= minimum_occurrences:
            repeated_texts.add(text)
    return repeated_texts


def _normalize_margin_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized.casefold()


def _extract_block_text(block: dict) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        fragments = [span.get("text", "") for span in line.get("spans", [])]
        line_text = "".join(fragments).strip()
        if line_text:
            lines.append(line_text)

    if not lines:
        return ""

    if len(lines) == 1:
        return lines[0]

    merged_lines: list[str] = [lines[0]]
    for line_text in lines[1:]:
        if _should_join_without_space(merged_lines[-1], line_text):
            merged_lines[-1] = f"{merged_lines[-1]}{line_text}"
        else:
            merged_lines.append(line_text)

    return " ".join(segment.strip() for segment in merged_lines if segment.strip()).strip()


def _should_join_without_space(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left.endswith("-"):
        return True
    return _contains_cjk(left[-1]) or _contains_cjk(right[0])


def _contains_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff"


def _is_noise_block(text: str, block: dict, page_height: float) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) <= 4 and stripped.replace("-", "").isdigit():
        return True
    if re.fullmatch(r"[$£€]\s*\d+([.,]\d{1,2})?", stripped):
        return True

    bbox = block.get("bbox", [0, 0, 0, 0])
    top = bbox[1]
    bottom = bbox[3]
    if len(stripped) <= 32 and (top < page_height * 0.05 or bottom > page_height * 0.96):
        if re.fullmatch(r"[\dIVXLCivxlc.\- ]+", stripped):
            return True

    return False


def _classify_block(text: str, block: dict, body_font_size: float) -> str:
    span_sizes: list[float] = []
    bold_like_count = 0
    span_count = 0
    line_count = 0

    for line in block.get("lines", []):
        if line.get("spans"):
            line_count += 1
        for span in line.get("spans", []):
            span_count += 1
            size = span.get("size", 0.0)
            if size > 0:
                span_sizes.append(size)
            flags = span.get("flags", 0)
            font_name = str(span.get("font", "")).lower()
            if "bold" in font_name or flags & 2**4:
                bold_like_count += 1

    if not span_sizes:
        return "paragraph"

    max_size = max(span_sizes)
    average_size = sum(span_sizes) / len(span_sizes)
    bold_ratio = bold_like_count / max(1, span_count)
    short_enough = len(text) <= 180
    heading_by_style = (
        short_enough
        and line_count <= 3
        and (max_size >= body_font_size * 1.18 or average_size >= body_font_size * 1.12 or bold_ratio >= 0.6)
    )
    heading_by_pattern = short_enough and bool(SECTION_PATTERN.match(text))
    heading_by_case = short_enough and text == text.upper() and len(text.split()) <= 12

    if heading_by_style or heading_by_pattern or heading_by_case:
        return "heading"
    return "paragraph"


def _merge_adjacent_blocks(blocks: list[_BlockCandidate], body_font_size: float) -> list[_BlockCandidate]:
    if not blocks:
        return []

    merged: list[_BlockCandidate] = [blocks[0]]
    for block in blocks[1:]:
        previous = merged[-1]
        if _should_merge_heading_blocks(previous, block, body_font_size):
            merged[-1] = _BlockCandidate(
                text=_join_heading_text(previous.text, block.text),
                page_number=previous.page_number,
                bbox=(
                    min(previous.bbox[0], block.bbox[0]),
                    min(previous.bbox[1], block.bbox[1]),
                    max(previous.bbox[2], block.bbox[2]),
                    max(previous.bbox[3], block.bbox[3]),
                ),
                kind="heading",
            )
            continue
        if _should_merge_blocks(previous, block, body_font_size):
            merged[-1] = _BlockCandidate(
                text=_join_block_text(previous.text, block.text),
                page_number=previous.page_number,
                bbox=(
                    min(previous.bbox[0], block.bbox[0]),
                    min(previous.bbox[1], block.bbox[1]),
                    max(previous.bbox[2], block.bbox[2]),
                    max(previous.bbox[3], block.bbox[3]),
                ),
                kind="paragraph",
            )
        else:
            merged.append(block)
    return merged


def _should_merge_blocks(left: _BlockCandidate, right: _BlockCandidate, body_font_size: float) -> bool:
    if left.kind != "paragraph" or right.kind != "paragraph":
        return False
    if left.page_number != right.page_number:
        return False

    vertical_gap = right.bbox[1] - left.bbox[3]
    horizontal_offset = abs(left.bbox[0] - right.bbox[0])
    if vertical_gap < -1:
        return False
    if vertical_gap > body_font_size * 1.9:
        return False
    if horizontal_offset > body_font_size * 4:
        return False
    if _looks_like_new_paragraph(right.text):
        return False
    return True


def _should_merge_heading_blocks(left: _BlockCandidate, right: _BlockCandidate, body_font_size: float) -> bool:
    if left.kind != "heading" or right.kind != "heading":
        return False
    if left.page_number != right.page_number:
        return False
    if len(left.text) > 80 or len(right.text) > 80:
        return False

    vertical_gap = right.bbox[1] - left.bbox[3]
    horizontal_offset = abs(left.bbox[0] - right.bbox[0])
    if vertical_gap < -1 or vertical_gap > body_font_size * 1.5:
        return False
    if horizontal_offset > body_font_size * 4:
        return False
    if _looks_like_price(left.text) or _looks_like_price(right.text):
        return False

    return _looks_like_heading_fragment(left.text) and _looks_like_heading_fragment(right.text)


def _join_block_text(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    if left.endswith("-"):
        return f"{left[:-1]}{right.lstrip()}"
    if _contains_cjk(left[-1]) or _contains_cjk(right[0]):
        return f"{left}{right}"
    return f"{left} {right}"


def _join_heading_text(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    return f"{left.rstrip()} {right.lstrip()}".strip()


def _looks_like_new_paragraph(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    if stripped.startswith(("•", "-", "*")):
        return True
    if re.match(r"^\(?\d+[\).]", stripped):
        return True
    return False


def _looks_like_heading_fragment(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    letters = [char for char in stripped if char.isalpha()]
    uppercase_letters = [char for char in letters if char.isupper()]
    uppercase_ratio = len(uppercase_letters) / max(1, len(letters))
    word_count = len(stripped.replace(",", " ").split())
    return uppercase_ratio >= 0.72 and word_count <= 8


def _looks_like_price(text: str) -> bool:
    return bool(re.fullmatch(r"[$£€]\s*\d+([.,]\d{1,2})?", text.strip()))
