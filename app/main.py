from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.schemas import (
    APIError,
    KakuyomuExtractResponse,
    KakuyomuTranslateResponse,
    PDFExtractRequest,
    PDFExtractResponse,
    PDFParagraph,
    TranslateWebKakuyomuRequest,
    TranslateJaRequest,
    TranslateJaResponse,
    TranslatedParagraph,
    TranslatedWebParagraph,
    WebExtractRequest,
)
from app.services.pdf_extractor import extract_pdf_paragraphs
from app.services.translation import TranslationRuntime, build_aligned_paragraphs
from app.services.web_extractor import extract_kakuyomu_episode


logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Local Translation Service",
    version="0.1.0",
    description="Phase 1: Japanese translation endpoint and PDF paragraph extraction.",
)
translator = TranslationRuntime()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/translate/ja",
    response_model=TranslateJaResponse,
    responses={400: {"model": APIError}, 500: {"model": APIError}},
)
def translate_japanese(payload: TranslateJaRequest) -> TranslateJaResponse:
    aligned_paragraphs = build_aligned_paragraphs(payload.text)
    if not aligned_paragraphs:
        raise HTTPException(status_code=400, detail="Input text does not contain any non-empty paragraphs.")

    paragraph_texts = [text for _, text in aligned_paragraphs]

    try:
        translated_texts = translator.translate_paragraphs(
            paragraph_texts,
            batch_size=payload.batch_size,
            max_new_tokens=payload.max_new_tokens,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Translation failed: {exc}") from exc

    paragraphs = [
        TranslatedParagraph(
            original_id=paragraph_id,
            original_text=original_text,
            translated_text=translated_text,
        )
        for (paragraph_id, original_text), translated_text in zip(aligned_paragraphs, translated_texts, strict=True)
    ]

    return TranslateJaResponse(
        model_name=translator.model_name,
        device=translator.device,
        paragraphs=paragraphs,
    )


@app.post(
    "/extract/pdf",
    response_model=PDFExtractResponse,
    responses={400: {"model": APIError}, 404: {"model": APIError}},
)
def extract_pdf(payload: PDFExtractRequest) -> PDFExtractResponse:
    try:
        paragraphs = extract_pdf_paragraphs(payload.file_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {exc}") from exc

    return PDFExtractResponse(
        file_path=str(Path(payload.file_path).expanduser().resolve()),
        paragraphs=[
            PDFParagraph(
                paragraph_id=item.paragraph_id,
                page_number=item.page_number,
                kind=item.kind,
                section_title=item.section_title,
                text=item.text,
            )
            for item in paragraphs
        ],
    )


@app.post(
    "/extract/web/kakuyomu",
    response_model=KakuyomuExtractResponse,
    responses={400: {"model": APIError}},
)
def extract_kakuyomu(payload: WebExtractRequest) -> KakuyomuExtractResponse:
    try:
        episode = extract_kakuyomu_episode(payload.url, timeout_seconds=payload.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Kakuyomu extraction failed: {exc}") from exc

    return KakuyomuExtractResponse(
        url=episode.url,
        work_title=episode.work_title,
        episode_title=episode.episode_title,
        paragraphs=[
            {
                "paragraph_id": item.paragraph_id,
                "kind": item.kind,
                "text": item.text,
            }
            for item in episode.paragraphs
        ],
    )


@app.post(
    "/translate/web/kakuyomu",
    response_model=KakuyomuTranslateResponse,
    responses={400: {"model": APIError}, 500: {"model": APIError}},
)
def translate_kakuyomu_episode(payload: TranslateWebKakuyomuRequest) -> KakuyomuTranslateResponse:
    try:
        episode = extract_kakuyomu_episode(payload.url, timeout_seconds=payload.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Kakuyomu extraction failed: {exc}") from exc

    try:
        translated_texts = translator.translate_paragraphs(
            [item.text for item in episode.paragraphs],
            batch_size=payload.batch_size,
            max_new_tokens=payload.max_new_tokens,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Kakuyomu translation failed: {exc}") from exc

    paragraphs = [
        TranslatedWebParagraph(
            paragraph_id=item.paragraph_id,
            kind=item.kind,
            original_text=item.text,
            translated_text=translated_text,
        )
        for item, translated_text in zip(episode.paragraphs, translated_texts, strict=True)
    ]
    translated_title = paragraphs[0].translated_text.strip() if paragraphs and paragraphs[0].translated_text.strip() else episode.episode_title

    return KakuyomuTranslateResponse(
        url=episode.url,
        work_title=episode.work_title,
        episode_title=episode.episode_title,
        source_title=episode.episode_title,
        translated_title=translated_title,
        model_name=translator.model_name,
        device=translator.device,
        paragraphs=paragraphs,
    )
