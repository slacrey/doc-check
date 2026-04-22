from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from uuid import uuid4

from doc_check.config import AppConfig
from doc_check.domain.rule_drafts import RuleDraftSource, RuleDraftSourceType
from doc_check.persistence.repositories import RuleDraftRepository
from doc_check.services.source_normalizer import SourceNormalizer


class RuleDraftPipelineError(ValueError):
    """Raised when a rule draft operation fails."""


class RuleDraftPipelineService:
    def __init__(
        self,
        *,
        config: AppConfig,
        repository: RuleDraftRepository,
        source_normalizer: SourceNormalizer | None = None,
        id_factory=None,
        now_factory=None,
    ) -> None:
        self._config = config
        self._repository = repository
        self._source_normalizer = source_normalizer or SourceNormalizer()
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def add_source(
        self,
        *,
        task_id: str,
        source_type: str,
        original_filename: str,
        content_type: str,
        payload: bytes,
    ) -> RuleDraftSource:
        task = self._repository.get_task(task_id)
        if task is None:
            raise RuleDraftPipelineError(f"Unknown rule draft task: {task_id}")

        normalized_filename = self._normalize_filename(original_filename)
        self._validate_upload(
            original_filename=normalized_filename,
            payload=payload,
        )

        normalized_source_type = self._parse_source_type(source_type)
        source_id = self._id_factory()
        source_dir = task.output_dir / "sources" / source_id
        storage_path = source_dir / "original.docx"
        normalized_path = source_dir / "snapshot.json"
        source_dir.mkdir(parents=True, exist_ok=False)
        storage_path.write_bytes(payload)

        parse_error = None
        normalized_snapshot = None
        try:
            normalized_snapshot = self._source_normalizer.normalize(
                source_type=normalized_source_type,
                source_path=storage_path,
            )
            normalized_path.write_text(
                json.dumps(normalized_snapshot.as_dict(), ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception as exc:
            parse_error = str(exc)
            normalized_path = None

        source = RuleDraftSource(
            source_id=source_id,
            task_id=task_id,
            source_type=normalized_source_type,
            original_filename=normalized_filename,
            stored_filename=storage_path.name,
            storage_path=storage_path,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(payload),
            is_excluded=False,
            uploaded_at=self._now_factory(),
            normalized_path=normalized_path,
            parse_error=parse_error,
        )

        try:
            return self._repository.create_source(source)
        except Exception:
            shutil.rmtree(source_dir, ignore_errors=True)
            raise

    def _validate_upload(self, *, original_filename: str, payload: bytes) -> None:
        if not original_filename:
            raise RuleDraftPipelineError("Uploaded file must include a filename")
        if Path(original_filename).suffix.lower() != ".docx":
            raise RuleDraftPipelineError("Only .docx uploads are supported")
        if not payload:
            raise RuleDraftPipelineError("Uploaded file is empty")
        if len(payload) > self._config.max_upload_bytes:
            raise RuleDraftPipelineError("Uploaded file exceeds the configured size limit")

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        return Path(filename).name.strip()

    @staticmethod
    def _parse_source_type(raw_value: str) -> RuleDraftSourceType:
        try:
            return RuleDraftSourceType(raw_value.strip())
        except ValueError as exc:
            raise RuleDraftPipelineError(f"Unsupported source_type: {raw_value}") from exc
