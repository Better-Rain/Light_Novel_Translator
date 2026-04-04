from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


LOGGER = logging.getLogger(__name__)

MODEL_NAME = os.getenv("JA_ZH_MODEL_PATH", "Helsinki-NLP/opus-mt-ja-zh")
PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n+", re.MULTILINE)


def _normalize_paragraphs(text: str) -> list[str]:
    paragraphs = [segment.strip() for segment in PARAGRAPH_SPLIT_PATTERN.split(text) if segment.strip()]
    return paragraphs


@dataclass(slots=True)
class TranslationRuntime:
    model_name: str = MODEL_NAME
    device: str = "cpu"
    dtype: torch.dtype = torch.float32

    def __post_init__(self) -> None:
        self._load_lock = threading.Lock()
        self._tokenizer: AutoTokenizer | None = None
        self._model: AutoModelForSeq2SeqLM | None = None
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device.startswith("cuda") else torch.float32
        if self.device.startswith("cuda"):
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return

        with self._load_lock:
            if self._model is not None and self._tokenizer is not None:
                return

            LOGGER.info("Loading translation model '%s' on %s", self.model_name, self.device)
            local_files_only = os.getenv("HF_LOCAL_FILES_ONLY", "0") == "1"
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                local_files_only=local_files_only,
            )
            model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_name,
                torch_dtype=self.dtype,
                low_cpu_mem_usage=True,
                local_files_only=local_files_only,
            )
            model.to(self.device)
            model.eval()

            self._tokenizer = tokenizer
            self._model = model

    def translate_paragraphs(
        self,
        paragraphs: list[str],
        *,
        batch_size: int = 16,
        max_new_tokens: int = 256,
    ) -> list[str]:
        if not paragraphs:
            return []

        self._ensure_loaded()
        assert self._tokenizer is not None
        assert self._model is not None

        results: list[str] = []
        current_batch_size = max(1, batch_size)
        index = 0

        while index < len(paragraphs):
            batch = paragraphs[index : index + current_batch_size]
            try:
                translated_batch = self._generate_batch(batch, max_new_tokens=max_new_tokens)
                results.extend(translated_batch)
                index += len(batch)
            except torch.cuda.OutOfMemoryError:
                if not self.device.startswith("cuda"):
                    raise
                torch.cuda.empty_cache()
                if current_batch_size == 1:
                    raise RuntimeError(
                        "CUDA out of memory while translating a single paragraph. "
                        "Reduce max_new_tokens or split the paragraph further."
                    ) from None
                current_batch_size = max(1, current_batch_size // 2)
                LOGGER.warning("CUDA OOM detected, reducing translation batch size to %s", current_batch_size)
            except RuntimeError as exc:
                if "CUDA out of memory" not in str(exc):
                    raise
                if not self.device.startswith("cuda"):
                    raise
                torch.cuda.empty_cache()
                if current_batch_size == 1:
                    raise RuntimeError(
                        "CUDA out of memory while translating a single paragraph. "
                        "Reduce max_new_tokens or split the paragraph further."
                    ) from exc
                current_batch_size = max(1, current_batch_size // 2)
                LOGGER.warning("CUDA OOM detected, reducing translation batch size to %s", current_batch_size)

        return results

    def _generate_batch(self, paragraphs: list[str], *, max_new_tokens: int) -> list[str]:
        assert self._tokenizer is not None
        assert self._model is not None

        encoded = self._tokenizer(
            paragraphs,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}

        with torch.inference_mode():
            generated = self._model.generate(
                **encoded,
                max_new_tokens=max_new_tokens,
                num_beams=4,
                length_penalty=1.0,
                no_repeat_ngram_size=3,
                early_stopping=True,
            )

        decoded = self._tokenizer.batch_decode(generated, skip_special_tokens=True)
        return [item.strip() for item in decoded]


def build_aligned_paragraphs(text: str) -> list[tuple[str, str]]:
    paragraphs = _normalize_paragraphs(text)
    return [(f"p{index:05d}", paragraph) for index, paragraph in enumerate(paragraphs, start=1)]
