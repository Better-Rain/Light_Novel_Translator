from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.services.kakuyomu_pipeline import build_kakuyomu_translation_result, save_kakuyomu_translation_result
from app.services.pdf_pipeline import build_pdf_translation_result, save_pdf_translation_result
from app.services.translation import TranslationRuntime


def _read_positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        parsed = int(raw_value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


MAX_CONCURRENT_UI_JOBS = max(1, _read_positive_int_env("UI_MAX_CONCURRENT_JOBS", 1))
MAX_RETAINED_JOBS = max(20, _read_positive_int_env("UI_MAX_RETAINED_JOBS", 100))
UI_JOB_SEMAPHORE = threading.BoundedSemaphore(MAX_CONCURRENT_UI_JOBS)


@dataclass(slots=True)
class KakuyomuUiJob:
    job_id: str
    status: str = "queued"
    progress: float = 0.0
    message: str = "Queued"
    error: str | None = None
    result: dict[str, Any] | None = None
    url: str = ""
    work_id: str | None = None
    episode_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class PdfUiJob:
    job_id: str
    status: str = "queued"
    progress: float = 0.0
    message: str = "Queued"
    error: str | None = None
    result: dict[str, Any] | None = None
    file_path: str = ""
    document_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class KakuyomuUiJobStore:
    translator: TranslationRuntime
    _jobs: dict[str, KakuyomuUiJob] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def create_job(
        self,
        *,
        url: str,
        timeout_seconds: int,
        batch_size: int,
        max_new_tokens: int,
    ) -> KakuyomuUiJob:
        if not UI_JOB_SEMAPHORE.acquire(blocking=False):
            raise RuntimeError("The local translation worker is busy. Try again after the current job finishes.")
        job = KakuyomuUiJob(job_id=uuid.uuid4().hex, url=url)
        with self._lock:
            self._cleanup_locked()
            self._jobs[job.job_id] = job

        thread = threading.Thread(
            target=self._run_job,
            kwargs={
                "job_id": job.job_id,
                "url": url,
                "timeout_seconds": timeout_seconds,
                "batch_size": batch_size,
                "max_new_tokens": max_new_tokens,
            },
            daemon=True,
        )
        thread.start()
        return self.get_job(job.job_id)

    def get_job(self, job_id: str) -> KakuyomuUiJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return KakuyomuUiJob(
                job_id=job.job_id,
                status=job.status,
                progress=job.progress,
                message=job.message,
                error=job.error,
                result=job.result,
                url=job.url,
                work_id=job.work_id,
                episode_id=job.episode_id,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )

    def _update_job(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = time.time()

    def _cleanup_locked(self) -> None:
        if len(self._jobs) < MAX_RETAINED_JOBS:
            return
        removable = sorted(
            (job for job in self._jobs.values() if job.status in {"completed", "failed"}),
            key=lambda job: job.updated_at,
        )
        for job in removable[: max(1, len(self._jobs) - MAX_RETAINED_JOBS + 1)]:
            self._jobs.pop(job.job_id, None)

    def _run_job(
        self,
        *,
        job_id: str,
        url: str,
        timeout_seconds: int,
        batch_size: int,
        max_new_tokens: int,
    ) -> None:
        try:
            self._update_job(job_id, status="running", progress=0.02, message="Fetching Kakuyomu episode")

            def mark_extracted() -> None:
                self._update_job(job_id, progress=0.12, message="Episode fetched, starting translation")

            def mark_translation_progress(completed: int, total: int) -> None:
                translate_ratio = 1.0 if total == 0 else completed / total
                self._update_job(
                    job_id,
                    progress=0.12 + translate_ratio * 0.76,
                    message=f"Translating paragraphs {completed}/{total}",
                )

            result = build_kakuyomu_translation_result(
                url=url,
                timeout_seconds=timeout_seconds,
                batch_size=batch_size,
                max_new_tokens=max_new_tokens,
                translator=self.translator,
                extract_progress_callback=mark_extracted,
                translate_progress_callback=mark_translation_progress,
            )
            self._update_job(
                job_id,
                progress=0.92,
                message="Saving translated result",
                work_id=str(result.get("work_id", "")),
                episode_id=str(result.get("episode_id", "")),
            )
            saved = save_kakuyomu_translation_result(result)
            self._update_job(
                job_id,
                status="completed",
                progress=1.0,
                message="Completed",
                result=saved,
                work_id=str(saved.get("work_id", "")),
                episode_id=str(saved.get("episode_id", "")),
            )
        except Exception as exc:  # noqa: BLE001
            self._update_job(job_id, status="failed", progress=1.0, message="Failed", error=str(exc))
        finally:
            UI_JOB_SEMAPHORE.release()


@dataclass(slots=True)
class PdfUiJobStore:
    translator: TranslationRuntime
    _jobs: dict[str, PdfUiJob] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def create_job(
        self,
        *,
        file_path: str,
        source_language: str,
        batch_size: int,
        max_new_tokens: int,
        debug_max_pages: int | None = None,
        debug_max_paragraphs: int | None = None,
    ) -> PdfUiJob:
        if not UI_JOB_SEMAPHORE.acquire(blocking=False):
            raise RuntimeError("The local translation worker is busy. Try again after the current job finishes.")
        job = PdfUiJob(job_id=uuid.uuid4().hex, file_path=file_path)
        with self._lock:
            self._cleanup_locked()
            self._jobs[job.job_id] = job

        thread = threading.Thread(
            target=self._run_job,
            kwargs={
                "job_id": job.job_id,
                "file_path": file_path,
                "source_language": source_language,
                "batch_size": batch_size,
                "max_new_tokens": max_new_tokens,
                "debug_max_pages": debug_max_pages,
                "debug_max_paragraphs": debug_max_paragraphs,
            },
            daemon=True,
        )
        thread.start()
        return self.get_job(job.job_id)

    def get_job(self, job_id: str) -> PdfUiJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return PdfUiJob(
                job_id=job.job_id,
                status=job.status,
                progress=job.progress,
                message=job.message,
                error=job.error,
                result=job.result,
                file_path=job.file_path,
                document_id=job.document_id,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )

    def _update_job(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = time.time()

    def _cleanup_locked(self) -> None:
        if len(self._jobs) < MAX_RETAINED_JOBS:
            return
        removable = sorted(
            (job for job in self._jobs.values() if job.status in {"completed", "failed"}),
            key=lambda job: job.updated_at,
        )
        for job in removable[: max(1, len(self._jobs) - MAX_RETAINED_JOBS + 1)]:
            self._jobs.pop(job.job_id, None)

    def _run_job(
        self,
        *,
        job_id: str,
        file_path: str,
        source_language: str,
        batch_size: int,
        max_new_tokens: int,
        debug_max_pages: int | None,
        debug_max_paragraphs: int | None,
    ) -> None:
        try:
            self._update_job(job_id, status="running", progress=0.02, message="Extracting PDF paragraphs")

            def mark_extracted() -> None:
                self._update_job(job_id, progress=0.14, message="PDF extracted, starting translation")

            def mark_translation_progress(completed: int, total: int) -> None:
                translate_ratio = 1.0 if total == 0 else completed / total
                self._update_job(
                    job_id,
                    progress=0.14 + translate_ratio * 0.74,
                    message=f"Translating paragraphs {completed}/{total}",
                )

            result = build_pdf_translation_result(
                file_path=file_path,
                source_language=source_language,
                batch_size=batch_size,
                max_new_tokens=max_new_tokens,
                debug_max_pages=debug_max_pages,
                debug_max_paragraphs=debug_max_paragraphs,
                translator=self.translator,
                extract_progress_callback=mark_extracted,
                translate_progress_callback=mark_translation_progress,
            )
            self._update_job(
                job_id,
                progress=0.92,
                message="Saving translated PDF result",
                document_id=str(result.get("document_id", "")),
            )
            saved = save_pdf_translation_result(result)
            self._update_job(
                job_id,
                status="completed",
                progress=1.0,
                message="Completed",
                result=saved,
                document_id=str(saved.get("document_id", "")),
            )
        except Exception as exc:  # noqa: BLE001
            self._update_job(job_id, status="failed", progress=1.0, message="Failed", error=str(exc))
        finally:
            UI_JOB_SEMAPHORE.release()
