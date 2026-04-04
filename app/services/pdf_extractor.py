from __future__ import annotations

import re
import statistics
from pathlib import Path

import fitz

from app.schemas import RawPDFParagraph


SECTION_PATTERN = re.compile(
    r"^(chapter|section|part|appendix)\b|^\d+(\.\d+)*\b|^[IVXLC]+\.\s",
    re.IGNORECASE,
)


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
        paragraphs: list[RawPDFParagraph] = []
        section_title: str | None = None
        paragraph_counter = 1

        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            page_dict = page.get_text("dict")
            blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 0]

            for block in blocks:
                text = _extract_block_text(block)
                if not text:
                    continue
                if _is_noise_block(text, block, page.rect.height):
                    continue

                kind = _classify_block(text, block, body_font_size)
                paragraph_id = f"pdf-p{paragraph_counter:05d}"

                if kind == "heading":
                    section_title = text

                paragraphs.append(
                    RawPDFParagraph(
                        paragraph_id=paragraph_id,
                        page_number=page_index + 1,
                        kind=kind,
                        section_title=section_title,
                        text=text,
                    )
                )
                paragraph_counter += 1

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
    return left.endswith("-") or _contains_cjk(left[-1]) or _contains_cjk(right[0])


def _contains_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff"


def _is_noise_block(text: str, block: dict, page_height: float) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) <= 4 and stripped.replace("-", "").isdigit():
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

