from __future__ import annotations

from dataclasses import asdict
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import (
    APIError,
    KakuyomuExtractResponse,
    KakuyomuHistoryResponse,
    KakuyomuSavedResponse,
    KakuyomuTranslateResponse,
    KakuyomuUiJobResponse,
    PDFExtractRequest,
    PDFExtractResponse,
    PDFParagraph,
    PDFHistoryResponse,
    PDFSavedResponse,
    PDFTranslateRequest,
    PDFTranslateResponse,
    PdfUiJobResponse,
    TranslateEnRequest,
    TranslateEnResponse,
    TranslateWebKakuyomuRequest,
    TranslateJaRequest,
    TranslateJaResponse,
    TranslatedParagraph,
    WebExtractRequest,
)
from app.services.kakuyomu_pipeline import (
    OUTPUTS_ROOT,
    build_kakuyomu_translation_result,
    list_saved_kakuyomu_results,
    load_saved_kakuyomu_result,
    save_kakuyomu_translation_result,
)
from app.services.pdf_extractor import extract_pdf_paragraphs
from app.services.pdf_pipeline import (
    build_pdf_translation_result,
    list_saved_pdf_results,
    load_saved_pdf_result,
    save_pdf_translation_result,
)
from app.services.translation import TranslationRuntime, build_aligned_paragraphs
from app.services.ui_jobs import KakuyomuUiJobStore, PdfUiJobStore
from app.services.web_extractor import extract_kakuyomu_episode
from app.web_ui import render_web_ui_html


logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Local Translation Service",
    version="0.1.0",
    description="Local translation service for Kakuyomu episodes and local PDF documents.",
)
translator = TranslationRuntime()
ui_job_store = KakuyomuUiJobStore(translator=translator)
pdf_ui_job_store = PdfUiJobStore(translator=translator)
OUTPUTS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/saved-files", StaticFiles(directory=str(OUTPUTS_ROOT), html=True), name="saved-files")


@app.get("/", response_class=HTMLResponse)
def web_ui(
    provider: str | None = Query(default=None),
    work_id: str | None = Query(default=None),
    episode_id: str | None = Query(default=None),
    document_id: str | None = Query(default=None),
) -> HTMLResponse:
    return HTMLResponse(
        render_web_ui_html(
            initial_provider=provider,
            initial_work_id=work_id,
            initial_episode_id=episode_id,
            initial_document_id=document_id,
        )
    )


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
            source_language="ja",
            target_language="zh",
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
        model_name=translator.get_model_name("ja", "zh"),
        device=translator.device,
        paragraphs=paragraphs,
    )


@app.post(
    "/translate/en",
    response_model=TranslateEnResponse,
    responses={400: {"model": APIError}, 500: {"model": APIError}},
)
def translate_english(payload: TranslateEnRequest) -> TranslateEnResponse:
    aligned_paragraphs = build_aligned_paragraphs(payload.text)
    if not aligned_paragraphs:
        raise HTTPException(status_code=400, detail="Input text does not contain any non-empty paragraphs.")

    paragraph_texts = [text for _, text in aligned_paragraphs]

    try:
        translated_texts = translator.translate_paragraphs(
            paragraph_texts,
            source_language="en",
            target_language="zh",
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

    return TranslateEnResponse(
        model_name=translator.get_model_name("en", "zh"),
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
    "/translate/pdf",
    response_model=PDFTranslateResponse,
    responses={400: {"model": APIError}, 404: {"model": APIError}, 500: {"model": APIError}},
)
def translate_pdf(payload: PDFTranslateRequest) -> PDFTranslateResponse:
    try:
        result = build_pdf_translation_result(
            file_path=payload.file_path,
            source_language=payload.source_language,
            batch_size=payload.batch_size,
            max_new_tokens=payload.max_new_tokens,
            debug_max_pages=payload.debug_max_pages,
            debug_max_paragraphs=payload.debug_max_paragraphs,
            translator=translator,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"PDF translation failed: {exc}") from exc
    return PDFTranslateResponse(**result)


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
        result = build_kakuyomu_translation_result(
            url=payload.url,
            timeout_seconds=payload.timeout_seconds,
            batch_size=payload.batch_size,
            max_new_tokens=payload.max_new_tokens,
            translator=translator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Kakuyomu translation failed: {exc}") from exc

    return KakuyomuTranslateResponse(**result)


@app.post(
    "/ui/api/kakuyomu/translate-save",
    response_model=KakuyomuSavedResponse,
    responses={400: {"model": APIError}, 500: {"model": APIError}},
)
def translate_and_save_kakuyomu(payload: TranslateWebKakuyomuRequest) -> KakuyomuSavedResponse:
    try:
        result = build_kakuyomu_translation_result(
            url=payload.url,
            timeout_seconds=payload.timeout_seconds,
            batch_size=payload.batch_size,
            max_new_tokens=payload.max_new_tokens,
            translator=translator,
        )
        saved = save_kakuyomu_translation_result(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Kakuyomu translate/save failed: {exc}") from exc

    return KakuyomuSavedResponse(**saved)


@app.post(
    "/ui/api/pdf/translate-save",
    response_model=PDFSavedResponse,
    responses={400: {"model": APIError}, 404: {"model": APIError}, 500: {"model": APIError}},
)
def translate_and_save_pdf(payload: PDFTranslateRequest) -> PDFSavedResponse:
    try:
        result = build_pdf_translation_result(
            file_path=payload.file_path,
            source_language=payload.source_language,
            batch_size=payload.batch_size,
            max_new_tokens=payload.max_new_tokens,
            debug_max_pages=payload.debug_max_pages,
            debug_max_paragraphs=payload.debug_max_paragraphs,
            translator=translator,
        )
        saved = save_pdf_translation_result(result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"PDF translate/save failed: {exc}") from exc
    return PDFSavedResponse(**saved)


@app.post(
    "/ui/api/kakuyomu/jobs",
    response_model=KakuyomuUiJobResponse,
    responses={400: {"model": APIError}},
)
def create_kakuyomu_ui_job(payload: TranslateWebKakuyomuRequest) -> KakuyomuUiJobResponse:
    try:
        job = ui_job_store.create_job(
            url=payload.url,
            timeout_seconds=payload.timeout_seconds,
            batch_size=payload.batch_size,
            max_new_tokens=payload.max_new_tokens,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unable to create Kakuyomu UI job: {exc}") from exc
    return KakuyomuUiJobResponse(**asdict(job))


@app.get(
    "/ui/api/kakuyomu/jobs/{job_id}",
    response_model=KakuyomuUiJobResponse,
    responses={404: {"model": APIError}},
)
def get_kakuyomu_ui_job(job_id: str) -> KakuyomuUiJobResponse:
    try:
        job = ui_job_store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Kakuyomu UI job not found: {job_id}") from exc
    return KakuyomuUiJobResponse(**asdict(job))


@app.post(
    "/ui/api/pdf/jobs",
    response_model=PdfUiJobResponse,
    responses={400: {"model": APIError}},
)
def create_pdf_ui_job(payload: PDFTranslateRequest) -> PdfUiJobResponse:
    try:
        job = pdf_ui_job_store.create_job(
            file_path=payload.file_path,
            source_language=payload.source_language,
            batch_size=payload.batch_size,
            max_new_tokens=payload.max_new_tokens,
            debug_max_pages=payload.debug_max_pages,
            debug_max_paragraphs=payload.debug_max_paragraphs,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unable to create PDF UI job: {exc}") from exc
    return PdfUiJobResponse(**asdict(job))


@app.get(
    "/ui/api/pdf/jobs/{job_id}",
    response_model=PdfUiJobResponse,
    responses={404: {"model": APIError}},
)
def get_pdf_ui_job(job_id: str) -> PdfUiJobResponse:
    try:
        job = pdf_ui_job_store.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"PDF UI job not found: {job_id}") from exc
    return PdfUiJobResponse(**asdict(job))


@app.get(
    "/ui/api/kakuyomu/result/{work_id}/{episode_id}",
    response_model=KakuyomuSavedResponse,
    responses={404: {"model": APIError}},
)
def get_saved_kakuyomu_result(work_id: str, episode_id: str) -> KakuyomuSavedResponse:
    try:
        saved = load_saved_kakuyomu_result(work_id, episode_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unable to load saved Kakuyomu result: {exc}") from exc
    return KakuyomuSavedResponse(**saved)


@app.get(
    "/ui/api/pdf/result/{document_id}",
    response_model=PDFSavedResponse,
    responses={404: {"model": APIError}},
)
def get_saved_pdf_result(document_id: str) -> PDFSavedResponse:
    try:
        saved = load_saved_pdf_result(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unable to load saved PDF result: {exc}") from exc
    return PDFSavedResponse(**saved)


@app.get("/ui/api/kakuyomu/history", response_model=KakuyomuHistoryResponse)
def get_kakuyomu_history(limit: int = Query(default=20, ge=1, le=100)) -> KakuyomuHistoryResponse:
    return KakuyomuHistoryResponse(items=list_saved_kakuyomu_results(limit=limit))


@app.get("/ui/api/pdf/history", response_model=PDFHistoryResponse)
def get_pdf_history(limit: int = Query(default=20, ge=1, le=100)) -> PDFHistoryResponse:
    return PDFHistoryResponse(items=list_saved_pdf_results(limit=limit))
