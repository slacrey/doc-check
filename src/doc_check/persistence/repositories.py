from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator

from doc_check.domain.documents import ArtifactRecord
from doc_check.persistence.models import (
    ARTIFACTS_SCHEMA,
    artifact_record_to_row,
    artifact_row_to_record,
)


class ArtifactRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def init_schema(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(ARTIFACTS_SCHEMA)
            connection.commit()

    def create(self, record: ArtifactRecord) -> ArtifactRecord:
        row = artifact_record_to_row(record)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO artifacts (
                    artifact_id,
                    original_filename,
                    stored_filename,
                    storage_path,
                    content_type,
                    size_bytes,
                    ruleset_id,
                    ruleset_version,
                    status,
                    created_at,
                    expires_at,
                    created_by,
                    auth_source,
                    annotated_path,
                    summary_path
                ) VALUES (
                    :artifact_id,
                    :original_filename,
                    :stored_filename,
                    :storage_path,
                    :content_type,
                    :size_bytes,
                    :ruleset_id,
                    :ruleset_version,
                    :status,
                    :created_at,
                    :expires_at,
                    :created_by,
                    :auth_source,
                    :annotated_path,
                    :summary_path
                )
                """,
                row,
            )
            connection.commit()
        return record

    def get(self, artifact_id: str) -> ArtifactRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()

        if row is None:
            return None
        return artifact_row_to_record(row)

    def update(self, record: ArtifactRecord) -> ArtifactRecord:
        row = artifact_record_to_row(record)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE artifacts
                SET
                    original_filename = :original_filename,
                    stored_filename = :stored_filename,
                    storage_path = :storage_path,
                    content_type = :content_type,
                    size_bytes = :size_bytes,
                    ruleset_id = :ruleset_id,
                    ruleset_version = :ruleset_version,
                    status = :status,
                    created_at = :created_at,
                    expires_at = :expires_at,
                    created_by = :created_by,
                    auth_source = :auth_source,
                    annotated_path = :annotated_path,
                    summary_path = :summary_path
                WHERE artifact_id = :artifact_id
                """,
                row,
            )
            connection.commit()
        return record

    def list_unexpired(
        self,
        *,
        as_of: datetime | None = None,
    ) -> list[ArtifactRecord]:
        reference_time = as_of or datetime.now(timezone.utc)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM artifacts
                WHERE expires_at >= ?
                ORDER BY created_at ASC
                """,
                (reference_time.isoformat(),),
            ).fetchall()

        return [artifact_row_to_record(row) for row in rows]

    def list_expired(
        self,
        *,
        as_of: datetime | None = None,
    ) -> list[ArtifactRecord]:
        reference_time = as_of or datetime.now(timezone.utc)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM artifacts
                WHERE expires_at < ?
                ORDER BY created_at ASC
                """,
                (reference_time.isoformat(),),
            ).fetchall()

        return [artifact_row_to_record(row) for row in rows]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()
