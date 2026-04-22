from __future__ import annotations

from datetime import datetime, timedelta, timezone

from doc_check.config import AppConfig
from doc_check.domain.documents import ArtifactRecord, ArtifactStatus
from doc_check.persistence.repositories import ArtifactRepository


def make_record(config: AppConfig, *, artifact_id: str, expires_at: datetime) -> ArtifactRecord:
    storage_path = config.artifacts_dir / artifact_id / "original.docx"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(b"placeholder")
    created_at = expires_at - timedelta(days=1)

    return ArtifactRecord(
        artifact_id=artifact_id,
        original_filename=f"{artifact_id}.docx",
        stored_filename="original.docx",
        storage_path=storage_path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=11,
        ruleset_id="aeos",
        ruleset_version="2026.04",
        status=ArtifactStatus.UPLOADED,
        created_at=created_at,
        expires_at=expires_at,
        created_by="reviewer@example.com",
        auth_source="x-forwarded-user",
    )


def test_repository_round_trips_artifact_records(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    config.ensure_directories()
    repository = ArtifactRepository(config.database_path)
    repository.init_schema()

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    record = make_record(config, artifact_id="artifact-1", expires_at=expires_at)
    repository.create(record)

    loaded = repository.get("artifact-1")

    assert loaded == record


def test_repository_lists_only_unexpired_records_across_instances(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    config.ensure_directories()
    repository = ArtifactRepository(config.database_path)
    repository.init_schema()

    now = datetime.now(timezone.utc)
    fresh = make_record(config, artifact_id="fresh", expires_at=now + timedelta(days=2))
    expired = make_record(config, artifact_id="expired", expires_at=now - timedelta(minutes=5))
    repository.create(fresh)
    repository.create(expired)

    restarted_repository = ArtifactRepository(config.database_path)
    active_records = restarted_repository.list_unexpired(as_of=now)

    assert [record.artifact_id for record in active_records] == ["fresh"]
