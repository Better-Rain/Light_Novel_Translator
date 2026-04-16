from __future__ import annotations

import logging
import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


LOGGER = logging.getLogger(__name__)

DEFAULT_MODELS: dict[tuple[str, str], str] = {
    ("ja", "zh"): "shun89/opus-mt-ja-zh",
    ("en", "zh"): "Helsinki-NLP/opus-mt-en-zh",
}
MODEL_ENV_KEYS: dict[tuple[str, str], tuple[str, str]] = {
    ("ja", "zh"): ("JA_ZH_MODEL_PATH", "JA_ZH_MODEL_NAME"),
    ("en", "zh"): ("EN_ZH_MODEL_PATH", "EN_ZH_MODEL_NAME"),
}
PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n+", re.MULTILINE)


@dataclass(slots=True)
class LoadedTranslationModel:
    source_language: str
    target_language: str
    model_name: str
    tokenizer: AutoTokenizer
    model: AutoModelForSeq2SeqLM


def _normalize_paragraphs(text: str) -> list[str]:
    return [segment.strip() for segment in PARAGRAPH_SPLIT_PATTERN.split(text) if segment.strip()]


@dataclass(slots=True)
class TranslationRuntime:
    default_source_language: str = "ja"
    default_target_language: str = "zh"
    device: str = "cpu"
    dtype: torch.dtype = torch.float32
    _load_lock: threading.Lock = field(init=False, repr=False)
    _models: dict[tuple[str, str], LoadedTranslationModel] = field(init=False, default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._load_lock = threading.Lock()
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device.startswith("cuda") else torch.float32
        if self.device.startswith("cuda"):
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

    @property
    def model_name(self) -> str:
        return self.get_model_name(self.default_source_language, self.default_target_language)

    def get_model_name(self, source_language: str, target_language: str) -> str:
        key = (source_language, target_language)
        env_path_key, env_name_key = MODEL_ENV_KEYS.get(key, ("", ""))
        if env_path_key and os.getenv(env_path_key):
            return str(os.getenv(env_path_key))
        if env_name_key and os.getenv(env_name_key):
            return str(os.getenv(env_name_key))
        if key in DEFAULT_MODELS:
            return DEFAULT_MODELS[key]
        raise RuntimeError(f"Unsupported translation pair: {source_language}->{target_language}")

    def _ensure_loaded(self, source_language: str, target_language: str) -> LoadedTranslationModel:
        key = (source_language, target_language)
        loaded = self._models.get(key)
        if loaded is not None:
            return loaded

        with self._load_lock:
            loaded = self._models.get(key)
            if loaded is not None:
                return loaded

            model_name = self.get_model_name(source_language, target_language)
            LOGGER.info("Loading translation model '%s' for %s->%s on %s", model_name, source_language, target_language, self.device)
            local_files_only = os.getenv("HF_LOCAL_FILES_ONLY", "0") == "1"
            try:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_name,
                    local_files_only=local_files_only,
                )
                model = AutoModelForSeq2SeqLM.from_pretrained(
                    model_name,
                    dtype=self.dtype,
                    low_cpu_mem_usage=True,
                    local_files_only=local_files_only,
                )
            except Exception as exc:  # noqa: BLE001
                guidance = (
                    f"Unable to load translation model '{model_name}' for {source_language}->{target_language}. "
                    "For offline usage, manually download a compatible Marian/Seq2Seq model and set the matching "
                    "environment variable, for example JA_ZH_MODEL_PATH or EN_ZH_MODEL_PATH."
                )
                raise RuntimeError(guidance) from exc

            model.to(self.device)
            model.eval()
            loaded = LoadedTranslationModel(
                source_language=source_language,
                target_language=target_language,
                model_name=model_name,
                tokenizer=tokenizer,
                model=model,
            )
            self._models[key] = loaded
            return loaded

    def translate_paragraphs(
        self,
        paragraphs: list[str],
        *,
        source_language: str = "ja",
        target_language: str = "zh",
        batch_size: int = 16,
        max_new_tokens: int = 256,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        if not paragraphs:
            return []

        loaded = self._ensure_loaded(source_language, target_language)
        results: list[str] = []
        current_batch_size = max(1, batch_size)
        index = 0
        total = len(paragraphs)
        if progress_callback is not None:
            progress_callback(0, total)

        while index < len(paragraphs):
            batch = paragraphs[index : index + current_batch_size]
            try:
                translated_batch = self._generate_batch(
                    loaded,
                    batch,
                    max_new_tokens=max_new_tokens,
                )
                results.extend(translated_batch)
                index += len(batch)
                if progress_callback is not None:
                    progress_callback(index, total)
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

    def _generate_batch(
        self,
        loaded: LoadedTranslationModel,
        paragraphs: list[str],
        *,
        max_new_tokens: int,
    ) -> list[str]:
        encoded = loaded.tokenizer(
            paragraphs,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}

        with torch.inference_mode():
            generated = loaded.model.generate(
                **encoded,
                max_new_tokens=max_new_tokens,
                num_beams=4,
                length_penalty=1.0,
                no_repeat_ngram_size=3,
                early_stopping=True,
            )

        decoded = loaded.tokenizer.batch_decode(generated, skip_special_tokens=True)
        return [item.strip() for item in decoded]


def build_aligned_paragraphs(text: str) -> list[tuple[str, str]]:
    paragraphs = _normalize_paragraphs(text)
    return [(f"p{index:05d}", paragraph) for index, paragraph in enumerate(paragraphs, start=1)]
