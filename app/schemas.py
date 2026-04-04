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

