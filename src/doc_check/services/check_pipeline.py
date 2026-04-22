from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import uuid

from doc_check.config import AppConfig
from doc_check.domain.documents import ArtifactRecord, ArtifactStatus, CreateArtifactCommand
from doc_check.persistence.repositories import ArtifactRepository


class ArtifactValidationError(ValueError):
    """Raised when an uploaded artifact fails basic validation."""


class CheckPipelineService:
    def __init__(
        self,
        *,
        config: AppConfig,
        repository: ArtifactRepository,
        id_factory=None,
        now_factory=None,
    ) -> None:
        self._config = config
        self._repository = repository
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def create_artifact(self, command: CreateArtifactCommand) -> ArtifactRecord:
        original_filename = self._normalize_filename(command.original_filename)
        self._validate(command=command, original_filename=original_filename)

        created_at = self._now_factory()
        expires_at = created_at + timedelta(days=self._config.retention_days)
        artifact_id = self._id_factory()
        artifact_dir = self._config.artifacts_dir / artifact_id
        storage_path = artifact_dir / "original.docx"

        artifact_dir.mkdir(parents=True, exist_ok=False)
        storage_path.write_bytes(command.payload)

        record = ArtifactRecord(
            artifact_id=artifact_id,
            original_filename=original_filename,
            stored_filename=storage_path.name,
            storage_path=storage_path,
            content_type=command.content_type,
            size_bytes=len(command.payload),
            ruleset_id=command.ruleset_id.strip(),
            ruleset_version=command.ruleset_version.strip(),
            status=ArtifactStatus.UPLOADED,
            created_at=created_at,
            expires_at=expires_at,
            created_by=command.user.user_id,
            auth_source=command.user.auth_source,
        )

        try:
            return self._repository.create(record)
        except Exception:
            shutil.rmtree(artifact_dir, ignore_errors=True)
            raise

    def _validate(self, *, command: CreateArtifactCommand, original_filename: str) -> None:
        if not original_filename:
            raise ArtifactValidationError("Uploaded file must include a filename")
        if Path(original_filename).suffix.lower() != ".docx":
            raise ArtifactValidationError("Only .docx uploads are supported")
        if not command.payload:
            raise ArtifactValidationError("Uploaded file is empty")
        if len(command.payload) > self._config.max_upload_bytes:
            raise ArtifactValidationError("Uploaded file exceeds the configured size limit")
        if not command.ruleset_id.strip():
            raise ArtifactValidationError("ruleset_id is required")
        if not command.ruleset_version.strip():
            raise ArtifactValidationError("ruleset_version is required")

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        cleaned = Path(filename).name.strip()
        return cleaned
