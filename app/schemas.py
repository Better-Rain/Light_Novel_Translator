from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TranslateJaRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Japanese text to translate.")
    max_new_tokens: int = Field(default=256, ge=32, le=1024)
    batch_size: int = Field(default=16, ge=1, le=64)


class TranslateEnRequest(BaseModel):
    text: str = Field(..., min_length=1, description="English text to translate.")
    max_new_tokens: int = Field(default=256, ge=32, le=1024)
    batch_size: int = Field(default=16, ge=1, le=64)


class TranslatedParagraph(BaseModel):
    original_id: str
    original_text: str
    translated_text: str


class TranslateJaResponse(BaseModel):
    source_language: Literal["ja"] = "ja"
    target_language: Literal["zh"] = "zh"
    model_name: str
    device: str
    paragraphs: list[TranslatedParagraph]


class TranslateEnResponse(BaseModel):
    source_language: Literal["en"] = "en"
    target_language: Literal["zh"] = "zh"
    model_name: str
    device: str
    paragraphs: list[TranslatedParagraph]


class PDFExtractRequest(BaseModel):
    file_path: str = Field(..., min_length=1, description="Absolute or relative PDF file path.")


class PDFTranslateRequest(BaseModel):
    file_path: str = Field(..., min_length=1, description="Absolute or relative PDF file path.")
    source_language: Literal["en", "ja"] = Field(default="en")
    max_new_tokens: int = Field(default=256, ge=32, le=1024)
    batch_size: int = Field(default=8, ge=1, le=64)


class PDFParagraph(BaseModel):
    paragraph_id: str
    page_number: int
    kind: Literal["heading", "paragraph"]
    section_title: str | None = None
    text: str


class PDFTranslatedParagraph(BaseModel):
    paragraph_id: str
    page_number: int
    kind: Literal["heading", "paragraph"]
    section_title: str | None = None
    original_text: str
    translated_text: str


class PDFExtractResponse(BaseModel):
    file_path: str
    paragraphs: list[PDFParagraph]


class PDFTranslateResponse(BaseModel):
    provider: Literal["pdf"] = "pdf"
    source_language: Literal["en", "ja"]
    target_language: Literal["zh"] = "zh"
    document_id: str
    document_title: str
    source_title: str
    translated_title: str
    source_file: str
    source_file_name: str
    model_name: str
    device: str
    paragraphs: list[PDFTranslatedParagraph]


class PDFSavedFiles(BaseModel):
    storage_dir: str
    result_json: str
    bilingual_html: str
    reading_html: str
    document_index_html: str
    result_api_url: str
    page_url: str
    result_json_url: str
    bilingual_html_url: str
    reading_html_url: str
    document_index_html_url: str


class PDFSavedResponse(PDFTranslateResponse):
    saved_at: str
    generated_at: str
    saved_files: PDFSavedFiles


class PDFHistoryItem(BaseModel):
    document_id: str
    document_title: str
    translated_title: str
    source_file_name: str
    saved_at: str
    source_file: str
    source_language: Literal["en", "ja"]
    page_url: str
    result_api_url: str
    bilingual_html_url: str
    reading_html_url: str


class PDFHistoryResponse(BaseModel):
    items: list[PDFHistoryItem]


class WebExtractRequest(BaseModel):
    url: str = Field(..., min_length=1, description="Episode URL to extract.")
    timeout_seconds: int = Field(default=30, ge=5, le=120)


class TranslateWebKakuyomuRequest(BaseModel):
    url: str = Field(..., min_length=1, description="Kakuyomu episode URL to extract and translate.")
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    max_new_tokens: int = Field(default=256, ge=32, le=1024)
    batch_size: int = Field(default=16, ge=1, le=64)


class WebParagraph(BaseModel):
    paragraph_id: str
    kind: Literal["heading", "paragraph"]
    text: str


class TranslatedWebParagraph(BaseModel):
    paragraph_id: str
    kind: Literal["heading", "paragraph"]
    original_text: str
    translated_text: str


class KakuyomuExtractResponse(BaseModel):
    provider: Literal["kakuyomu"] = "kakuyomu"
    url: str
    work_title: str
    episode_title: str
    paragraphs: list[WebParagraph]


class KakuyomuTranslateResponse(BaseModel):
    provider: Literal["kakuyomu"] = "kakuyomu"
    source_language: Literal["ja"] = "ja"
    target_language: Literal["zh"] = "zh"
    url: str
    work_title: str
    episode_title: str
    source_title: str
    translated_title: str
    title_source: Literal["episode_title"] = "episode_title"
    model_name: str
    device: str
    paragraphs: list[TranslatedWebParagraph]


class KakuyomuSavedFiles(BaseModel):
    storage_dir: str
    result_json: str
    bilingual_html: str
    reading_html: str
    episode_index_html: str
    result_api_url: str
    page_url: str
    result_json_url: str
    bilingual_html_url: str
    reading_html_url: str
    episode_index_html_url: str


class KakuyomuSavedResponse(KakuyomuTranslateResponse):
    work_id: str
    episode_id: str
    saved_at: str
    generated_at: str
    source_file: str
    source_file_name: str
    saved_files: KakuyomuSavedFiles


class KakuyomuHistoryItem(BaseModel):
    work_id: str
    episode_id: str
    work_title: str
    episode_title: str
    translated_title: str
    saved_at: str
    url: str
    page_url: str
    result_api_url: str
    bilingual_html_url: str
    reading_html_url: str


class KakuyomuHistoryResponse(BaseModel):
    items: list[KakuyomuHistoryItem]


class KakuyomuUiJobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: float
    message: str
    error: str | None = None
    url: str
    work_id: str | None = None
    episode_id: str | None = None
    result: KakuyomuSavedResponse | None = None


class PdfUiJobResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: float
    message: str
    error: str | None = None
    file_path: str
    document_id: str | None = None
    result: PDFSavedResponse | None = None


class APIError(BaseModel):
    detail: str


class ParagraphChunk(BaseModel):
    paragraph_id: str
    text: str


class RawPDFParagraph(BaseModel):
    paragraph_id: str
    page_number: int
    kind: Literal["heading", "paragraph"]
    section_title: str | None = None
    text: str

    @model_validator(mode="after")
    def ensure_text(self) -> "RawPDFParagraph":
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("Paragraph text must not be empty.")
        return self
