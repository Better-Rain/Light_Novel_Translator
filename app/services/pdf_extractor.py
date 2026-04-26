from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import fitz

from app.schemas import RawPDFParagraph


SECTION_PATTERN = re.compile(
    r"^(chapter|section|part|appendix|preface|introduction|prologue|epilogue)\b|^\d+(\.\d+)*\b|^[IVXLC]+\.\s",
    re.IGNORECASE,
)
TOC_ENTRY_PATTERN = re.compile(r".{4,}\b\d{1,4}\]?$")
FRONT_MATTER_KEYWORDS = (
    "contents",
    "table of contents",
    "illustrations",
    "acknowledgment",
    "acknowledgements",
    "copyright",
    "published by",
    "all rights reserved",
    "random house",
    "vintage books",
    "dedication",
    "foreword",
    "preface",
)
STOPWORD_TAILS = {"the", "and", "of", "to", "in", "by", "for", "with", "that", "from"}
WEAK_HEADING_STARTS = {"and", "but", "if", "or", "so", "then"}


@dataclass(slots=True)
class _BlockCandidate:
    text: str
    page_number: int
    page_height: float
    bbox: tuple[float, float, float, float]
    kind: str


@dataclass(slots=True)
class _PageSummary:
    page_number: int
    paragraph_count: int
    heading_count: int
    chapter_heading_count: int
    toc_entry_count: int
    average_block_length: float
    body_char_count: int
    long_paragraph_count: int
    short_heading_count: int
    front_matter_keyword_hits: int
    has_cover_like_layout: bool
    has_quote_like_layout: bool
    has_toc_signal: bool


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
            page_height = page.rect.height
            page_dict = page.get_text("dict")
            blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 0]

            for block in blocks:
                text = _extract_block_text(block)
                if not text:
                    continue
                if _normalize_margin_text(text) in repeated_margin_texts:
                    continue
                if _is_noise_block(text, block, page_height):
                    continue
                raw_blocks.append(
                    _BlockCandidate(
                        text=text,
                        page_number=page_index + 1,
                        page_height=page_height,
                        bbox=tuple(block.get("bbox", [0.0, 0.0, 0.0, 0.0])),
                        kind=_classify_block(text, block, body_font_size),
                    )
                )

        merged_blocks = _merge_adjacent_blocks(raw_blocks, body_font_size)
        grouped_blocks = _group_blocks_by_page(merged_blocks)
        title_hints = _build_title_hints(pdf_path)
        main_content_start = _detect_main_content_start(grouped_blocks)
        filtered_blocks = _filter_content_blocks(grouped_blocks, main_content_start, title_hints)
        if not filtered_blocks:
            raise ValueError(
                "No PDF paragraphs remained after filtering "
                f"(raw_blocks={len(raw_blocks)}, merged_blocks={len(merged_blocks)}, "
                f"main_content_start_page={main_content_start})."
            )

        paragraphs: list[RawPDFParagraph] = []
        section_title: str | None = None

        for index, block in enumerate(filtered_blocks, start=1):
            if _is_heading_kind(block.kind):
                section_title = block.text
            paragraphs.append(
                RawPDFParagraph(
                    paragraph_id=f"pdf-p{index:05d}",
                    page_number=block.page_number,
                    kind=block.kind,
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
                    text = _clean_extracted_text(span.get("text", ""))
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
            if top < page_height * 0.1 or bottom > page_height * 0.94:
                margin_occurrences[text] += 1

    repeated_texts: set[str] = set()
    minimum_occurrences = 3 if document.page_count >= 8 else 2
    for text, count in margin_occurrences.items():
        if count >= minimum_occurrences:
            repeated_texts.add(text)
    return repeated_texts


def _normalize_margin_text(text: str) -> str:
    normalized = _clean_extracted_text(text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold()


def _extract_block_text(block: dict) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        fragments = [_clean_extracted_text(span.get("text", "")) for span in line.get("spans", [])]
        line_text = "".join(fragment for fragment in fragments if fragment).strip()
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


def _clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    cleaned = (
        text.replace("\u00ad", "")
        .replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\xa0", " ")
        .replace("\t", " ")
    )
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


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
    if _looks_like_price(stripped):
        return True
    if re.fullmatch(r"[\W_]+", stripped):
        return True

    bbox = block.get("bbox", [0.0, 0.0, 0.0, 0.0])
    top = bbox[1]
    bottom = bbox[3]
    in_margin = top < page_height * 0.05 or bottom > page_height * 0.965
    if in_margin and _looks_like_page_number_or_footer(stripped):
        return True
    if in_margin and len(stripped) <= 2 and not any(char.isalpha() for char in stripped):
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
    sentence_like = _looks_like_sentence(text)

    heading_by_style = (
        short_enough
        and not sentence_like
        and line_count <= 3
        and (max_size >= body_font_size * 1.18 or average_size >= body_font_size * 1.12 or bold_ratio >= 0.6)
    )
    heading_by_pattern = short_enough and bool(SECTION_PATTERN.match(text))
    heading_by_case = short_enough and _looks_like_display_heading(text)

    if heading_by_pattern or (heading_by_style and _looks_like_chapter_title(text)):
        return "chapter_heading"
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
                page_height=previous.page_height,
                bbox=(
                    min(previous.bbox[0], block.bbox[0]),
                    min(previous.bbox[1], block.bbox[1]),
                    max(previous.bbox[2], block.bbox[2]),
                    max(previous.bbox[3], block.bbox[3]),
                ),
                kind="chapter_heading" if "chapter_heading" in {previous.kind, block.kind} else "heading",
            )
            continue
        if _should_merge_blocks(previous, block, body_font_size):
            merged[-1] = _BlockCandidate(
                text=_join_block_text(previous.text, block.text),
                page_number=previous.page_number,
                page_height=previous.page_height,
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
    if not _is_heading_kind(left.kind) or not _is_heading_kind(right.kind):
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
    if stripped.startswith(('"', "'", "-", "*", "•")):
        return True
    if re.match(r"^\(?\d+[\).]", stripped):
        return True
    return False


def _looks_like_heading_fragment(text: str) -> bool:
    stripped = text.strip()
    if not stripped or _looks_like_sentence(stripped):
        return False
    letters = [char for char in stripped if char.isalpha()]
    uppercase_letters = [char for char in letters if char.isupper()]
    uppercase_ratio = len(uppercase_letters) / max(1, len(letters))
    word_count = len(stripped.replace(",", " ").split())
    return word_count <= 8 and (uppercase_ratio >= 0.72 or stripped == stripped.title())


def _looks_like_display_heading(text: str) -> bool:
    stripped = text.strip()
    if not stripped or _looks_like_sentence(stripped):
        return False
    words = stripped.replace(":", " ").replace("-", " ").split()
    if len(words) > 14:
        return False
    letters = [char for char in stripped if char.isalpha()]
    if not letters:
        return False
    uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    title_case_words = sum(1 for word in words if word[:1].isupper())
    return uppercase_ratio >= 0.84 or title_case_words >= max(1, len(words) - 1)


def _looks_like_chapter_title(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _weird_char_ratio(stripped) >= 0.08:
        return False
    if SECTION_PATTERN.match(stripped):
        alpha_words = re.findall(r"[A-Za-z]+", stripped)
        return bool(alpha_words) and len(alpha_words) <= 8
    words = stripped.replace(":", " ").replace("-", " ").split()
    if len(words) > 10:
        return False
    if len(words) <= 4 and all(word[:1].isupper() for word in words if word):
        return True
    return stripped.isupper() and len(words) <= 8


def _looks_like_sentence(text: str) -> bool:
    stripped = text.strip()
    words = stripped.split()
    if len(words) < 7:
        return False
    letters = [char for char in stripped if char.isalpha()]
    lowercase_ratio = sum(1 for char in letters if char.islower()) / max(1, len(letters))
    sentence_punctuation = sum(stripped.count(mark) for mark in [",", ".", ";", ":", "?", "!"])
    if lowercase_ratio >= 0.55:
        return True
    return lowercase_ratio >= 0.35 and sentence_punctuation >= 1


def _looks_like_price(text: str) -> bool:
    return bool(re.fullmatch(r"[$£€¥]\s*\d+(?:[.,]\d{1,2})?", text.strip()))


def _looks_like_page_number_or_footer(text: str) -> bool:
    stripped = text.strip()
    if re.fullmatch(r"[\[\](){}\-–— ]*\d{1,4}[\[\](){}\-–— ]*", stripped):
        return True
    if re.fullmatch(r"[IVXLCivxlc.\-–— ]+", stripped):
        return True
    return False


def _group_blocks_by_page(blocks: list[_BlockCandidate]) -> list[tuple[int, list[_BlockCandidate]]]:
    grouped: list[tuple[int, list[_BlockCandidate]]] = []
    current_page_number: int | None = None
    current_blocks: list[_BlockCandidate] = []

    for block in blocks:
        if current_page_number != block.page_number:
            if current_blocks:
                grouped.append((current_page_number or 1, current_blocks))
            current_page_number = block.page_number
            current_blocks = [block]
        else:
            current_blocks.append(block)

    if current_blocks:
        grouped.append((current_page_number or 1, current_blocks))

    return grouped


def _detect_main_content_start(page_blocks: list[tuple[int, list[_BlockCandidate]]]) -> int:
    first_paragraph_page = 1
    first_general_content_page: int | None = None

    for page_number, blocks in page_blocks:
        summary = _summarize_page(page_number, blocks)
        if summary.paragraph_count and first_paragraph_page == 1:
            first_paragraph_page = page_number
        if _is_strong_section_start_page(summary):
            return page_number
        if first_general_content_page is None and _is_main_content_page(summary):
            first_general_content_page = page_number

    if first_general_content_page is not None:
        return first_general_content_page
    return first_paragraph_page


def _summarize_page(page_number: int, blocks: list[_BlockCandidate]) -> _PageSummary:
    paragraph_blocks = [block for block in blocks if block.kind == "paragraph"]
    heading_blocks = [block for block in blocks if block.kind == "heading"]
    chapter_blocks = [block for block in blocks if block.kind == "chapter_heading"]
    all_text = " ".join(block.text for block in blocks).casefold()
    front_matter_keyword_hits = sum(1 for keyword in FRONT_MATTER_KEYWORDS if keyword in all_text)
    toc_entry_count = sum(1 for block in blocks if TOC_ENTRY_PATTERN.fullmatch(block.text.strip()))
    average_block_length = sum(len(block.text) for block in blocks) / max(1, len(blocks))
    body_char_count = sum(len(block.text) for block in paragraph_blocks)
    long_paragraph_count = sum(1 for block in paragraph_blocks if len(block.text) >= 220)
    short_heading_count = sum(1 for block in blocks if _is_heading_kind(block.kind) and len(block.text) <= 70)
    has_cover_like_layout = len(paragraph_blocks) == 0 and short_heading_count >= 3 and average_block_length <= 30
    has_quote_like_layout = len(paragraph_blocks) == 0 and len(blocks) >= 8 and average_block_length <= 90
    has_toc_signal = "contents" in all_text or toc_entry_count >= 4

    return _PageSummary(
        page_number=page_number,
        paragraph_count=len(paragraph_blocks),
        heading_count=len(heading_blocks),
        chapter_heading_count=len(chapter_blocks),
        toc_entry_count=toc_entry_count,
        average_block_length=average_block_length,
        body_char_count=body_char_count,
        long_paragraph_count=long_paragraph_count,
        short_heading_count=short_heading_count,
        front_matter_keyword_hits=front_matter_keyword_hits,
        has_cover_like_layout=has_cover_like_layout,
        has_quote_like_layout=has_quote_like_layout,
        has_toc_signal=has_toc_signal,
    )


def _is_main_content_page(summary: _PageSummary) -> bool:
    if summary.has_toc_signal:
        return False
    if summary.front_matter_keyword_hits >= 1 and summary.body_char_count < 2400:
        return False
    if summary.has_cover_like_layout or summary.has_quote_like_layout:
        return False
    if summary.paragraph_count >= 2 and (summary.long_paragraph_count >= 1 or summary.body_char_count >= 650):
        return True
    if summary.chapter_heading_count >= 1 and summary.paragraph_count >= 1 and summary.body_char_count >= 250:
        return True
    return False


def _is_strong_section_start_page(summary: _PageSummary) -> bool:
    if summary.has_toc_signal:
        return False
    if summary.front_matter_keyword_hits >= 1:
        return False
    return summary.chapter_heading_count >= 1 and summary.paragraph_count >= 1 and summary.body_char_count >= 250


def _filter_content_blocks(
    page_blocks: list[tuple[int, list[_BlockCandidate]]],
    main_content_start: int,
    title_hints: set[str],
) -> list[_BlockCandidate]:
    kept: list[_BlockCandidate] = []
    known_titles = {title for title in title_hints if title}

    for page_number, blocks in page_blocks:
        if page_number < main_content_start:
            continue
        if page_number > main_content_start + 10 and _is_end_matter_page(page_number, blocks):
            break
        page_kept = _filter_page_blocks(blocks, known_titles)
        if not page_kept:
            continue
        kept.extend(page_kept)
        for block in page_kept:
            if _is_heading_kind(block.kind):
                known_titles.add(_normalize_title_fingerprint(block.text))

    return kept


def _filter_page_blocks(blocks: list[_BlockCandidate], known_titles: set[str]) -> list[_BlockCandidate]:
    page_has_body = any(block.kind == "paragraph" for block in blocks)
    filtered: list[_BlockCandidate] = []

    for block in blocks:
        if _looks_like_footer_candidate(block):
            continue
        if _looks_like_running_header_candidate(block, page_has_body, known_titles):
            continue
        if _looks_like_ocr_heading_noise(block, page_has_body):
            continue
        if _should_demote_heading_to_paragraph(block, page_has_body):
            filtered.append(
                _BlockCandidate(
                    text=block.text,
                    page_number=block.page_number,
                    page_height=block.page_height,
                    bbox=block.bbox,
                    kind="paragraph",
                )
            )
            continue
        filtered.append(block)

    return filtered


def _looks_like_footer_candidate(block: _BlockCandidate) -> bool:
    text = block.text.strip()
    bottom = block.bbox[3]
    in_footer = bottom > block.page_height * 0.955
    if not in_footer:
        return False
    if _looks_like_page_number_or_footer(text):
        return True
    return len(text) <= 10 and not any(char.isalpha() for char in text)


def _looks_like_running_header_candidate(
    block: _BlockCandidate,
    page_has_body: bool,
    known_titles: set[str],
) -> bool:
    text = block.text.strip()
    top = block.bbox[1]
    in_header = top < block.page_height * 0.12
    if not in_header or not page_has_body or not text:
        return False
    if not _is_heading_kind(block.kind):
        return False
    if _looks_like_page_header_marker(text):
        return True
    if _matches_known_title(text, known_titles):
        return True
    if _weird_char_ratio(text) >= 0.08 and len(text.split()) <= 10:
        return True
    return False


def _looks_like_page_header_marker(text: str) -> bool:
    stripped = text.strip()
    if re.search(r"(^|[\s\[(])\d{1,4}([\]\)]|[\s]|$)", stripped) and any(char.isalpha() for char in stripped):
        return True
    if stripped.endswith(("]", ")", "[")):
        return True
    return False


def _matches_known_title(text: str, known_titles: set[str]) -> bool:
    fingerprint = _normalize_title_fingerprint(text)
    if not fingerprint or len(fingerprint) < 5:
        return False
    for known in known_titles:
        if not known:
            continue
        if SequenceMatcher(None, fingerprint, known).ratio() >= 0.6:
            return True
    return False


def _looks_like_ocr_heading_noise(block: _BlockCandidate, page_has_body: bool) -> bool:
    text = block.text.strip()
    if not text or not _is_heading_kind(block.kind):
        return False
    if len(text) <= 2 and not any(char.isalpha() for char in text):
        return True
    if _weird_char_ratio(text) >= 0.14:
        return True
    if page_has_body and len(text.split()) <= 2 and len(text) <= 10 and _weird_char_ratio(text) >= 0.05:
        return True
    return False


def _should_demote_heading_to_paragraph(block: _BlockCandidate, page_has_body: bool) -> bool:
    text = block.text.strip()
    if not _is_heading_kind(block.kind):
        return False
    if page_has_body and _looks_like_short_body_fragment(text):
        return True
    return not _looks_like_valid_heading(text)


def _weird_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    allowed = sum(1 for char in text if char.isalnum() or char.isspace() or char in ",.;:'\"!?-()[]/&")
    return max(0.0, 1 - (allowed / len(text)))


def _looks_like_valid_heading(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _looks_like_chapter_title(stripped) or _looks_like_spaced_caps_heading(stripped):
        return True
    if _looks_like_sentence(stripped):
        return False

    alpha_words = re.findall(r"[A-Za-z]+", stripped)
    alpha_word_count = len(alpha_words)
    if alpha_word_count == 0 or alpha_word_count > 8:
        return False
    if re.search(r"\d", stripped) and not re.match(r"^\d+([.)]|$)", stripped):
        return False
    if re.search(r"[\"“”'`]{2,}|[!?]|,{2,}", stripped):
        return False

    trailing = stripped[-1]
    if trailing in {",", "!", "?", ";", ":", "\"", "'"}:
        return False
    if trailing == "." and alpha_word_count > 1:
        return False
    if _weird_char_ratio(stripped) >= 0.08:
        return False

    words = stripped.split()
    if len(words) <= 2 and words[0].casefold().strip(".,;:!?") in WEAK_HEADING_STARTS:
        return False
    if words and words[-1].casefold() in STOPWORD_TAILS:
        return False
    if stripped[:1].islower():
        return False
    if _looks_like_display_heading(stripped) and alpha_word_count <= 6:
        return True
    return alpha_word_count <= 4 and stripped == stripped.title()


def _looks_like_spaced_caps_heading(text: str) -> bool:
    tokens = text.split()
    if len(tokens) < 3:
        return False
    compact_tokens = [token for token in tokens if token.isalpha()]
    if not compact_tokens:
        return False
    return all(len(token) <= 2 and token == token.upper() for token in compact_tokens)


def _looks_like_short_body_fragment(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    words = stripped.split()
    if len(words) > 4:
        return False
    if stripped.endswith((",", ";", ":", "!", "?")):
        return True
    first_word = words[0].casefold().strip(".,;:!?") if words else ""
    if first_word in WEAK_HEADING_STARTS:
        return True
    if len(stripped) <= 3 and re.fullmatch(r"[IVXLC\d.]+", stripped, re.IGNORECASE):
        return True
    return False


def _is_end_matter_page(page_number: int, blocks: list[_BlockCandidate]) -> bool:
    heading_texts = [block.text.strip().casefold() for block in blocks if _is_heading_kind(block.kind)]
    if any(text in {"index", "bibliography", "references"} for text in heading_texts):
        return True

    all_text = " ".join(block.text for block in blocks).casefold()
    if "vintage political science" in all_text or "social criticism" in all_text:
        return True
    short_entry_count = sum(1 for block in blocks if len(block.text) <= 80 and re.search(r"\b\d{1,4}\b", block.text))
    return page_number > 300 and short_entry_count >= max(8, len(blocks) // 2)


def _build_title_hints(pdf_path: Path) -> set[str]:
    stem = pdf_path.stem
    stem = stem.replace("_", " ")
    stem = stem.replace("(z-library.sk, 1lib.sk, z-lib.sk)", "")
    fingerprint = _normalize_title_fingerprint(stem)
    return {fingerprint} if fingerprint else set()


def _normalize_title_fingerprint(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).casefold()
    normalized = normalized.translate(str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "6": "g", "7": "t"}))
    normalized = re.sub(r"[^a-z]+", "", normalized)
    return normalized


def _is_heading_kind(kind: str) -> bool:
    return kind in {"heading", "chapter_heading"}
