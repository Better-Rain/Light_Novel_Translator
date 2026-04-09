from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TranslateJaRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Japanese text to translate.")
    max_new_tokens: int = Field(
        default=256,
        ge=32,
        le=1024,
        description="Maximum number of generated tokens per paragraph.",
    )
    batch_size: int = Field(
        default=16,
        ge=1,
        le=64,
        description="Paragraph batch size for GPU/CPU inference.",
    )


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


class PDFExtractRequest(BaseModel):
    file_path: str = Field(..., min_length=1, description="Absolute or relative PDF file path.")


class PDFParagraph(BaseModel):
    paragraph_id: str
    page_number: int
    kind: Literal["heading", "paragraph"]
    section_title: str | None = None
    text: str


class PDFExtractResponse(BaseModel):
    file_path: str
    paragraphs: list[PDFParagraph]


class WebExtractRequest(BaseModel):
    url: str = Field(..., min_length=1, description="Episode URL to extract.")
    timeout_seconds: int = Field(default=30, ge=5, le=120)


class TranslateWebKakuyomuRequest(BaseModel):
    url: str = Field(..., min_length=1, description="Kakuyomu episode URL to extract and translate.")
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    max_new_tokens: int = Field(
        default=256,
        ge=32,
        le=1024,
        description="Maximum number of generated tokens per paragraph.",
    )
    batch_size: int = Field(
        default=16,
        ge=1,
        le=64,
        description="Paragraph batch size for GPU/CPU inference.",
    )


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
