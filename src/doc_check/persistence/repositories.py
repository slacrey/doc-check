from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator

from doc_check.domain.documents import ArtifactRecord
from doc_check.domain.rule_drafts import RuleDraftSource, RuleDraftTask
from doc_check.persistence.models import (
    ARTIFACTS_SCHEMA,
    RULE_DRAFTS_SCHEMA,
    artifact_record_to_row,
    artifact_row_to_record,
    rule_draft_source_from_row,
    rule_draft_source_to_row,
    rule_draft_task_from_row,
    rule_draft_task_to_row,
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


class RuleDraftRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def init_schema(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(RULE_DRAFTS_SCHEMA)
            self._migrate_rule_draft_schema(connection)
            connection.commit()

    def create_task(self, task: RuleDraftTask) -> RuleDraftTask:
        row = rule_draft_task_to_row(task)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rule_draft_tasks (
                    task_id,
                    ruleset_id,
                    status,
                    created_at,
                    created_by,
                    auth_source,
                    output_dir
                ) VALUES (
                    :task_id,
                    :ruleset_id,
                    :status,
                    :created_at,
                    :created_by,
                    :auth_source,
                    :output_dir
                )
                """,
                row,
            )
            connection.commit()
        return task

    def get_task(self, task_id: str) -> RuleDraftTask | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM rule_draft_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()

        if row is None:
            return None
        return rule_draft_task_from_row(row)

    def list_tasks(self) -> list[RuleDraftTask]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM rule_draft_tasks
                ORDER BY created_at DESC, task_id DESC
                """
            ).fetchall()

        return [rule_draft_task_from_row(row) for row in rows]

    def update_task(self, task: RuleDraftTask) -> RuleDraftTask:
        row = rule_draft_task_to_row(task)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE rule_draft_tasks
                SET
                    ruleset_id = :ruleset_id,
                    status = :status,
                    created_at = :created_at,
                    created_by = :created_by,
                    auth_source = :auth_source,
                    output_dir = :output_dir
                WHERE task_id = :task_id
                """,
                row,
            )
            connection.commit()
        return task

    def create_source(self, source: RuleDraftSource) -> RuleDraftSource:
        row = rule_draft_source_to_row(source)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rule_draft_sources (
                    source_id,
                    task_id,
                    source_type,
                    original_filename,
                    stored_filename,
                    storage_path,
                    content_type,
                    size_bytes,
                    is_excluded,
                    uploaded_at,
                    normalized_path,
                    parse_error
                ) VALUES (
                    :source_id,
                    :task_id,
                    :source_type,
                    :original_filename,
                    :stored_filename,
                    :storage_path,
                    :content_type,
                    :size_bytes,
                    :is_excluded,
                    :uploaded_at,
                    :normalized_path,
                    :parse_error
                )
                """,
                row,
            )
            connection.commit()
        return source

    def get_source(self, task_id: str, source_id: str) -> RuleDraftSource | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM rule_draft_sources
                WHERE task_id = ? AND source_id = ?
                """,
                (task_id, source_id),
            ).fetchone()

        if row is None:
            return None
        return rule_draft_source_from_row(row)

    def update_source_exclusion(
        self,
        *,
        task_id: str,
        source_id: str,
        is_excluded: bool,
    ) -> RuleDraftSource | None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE rule_draft_sources
                SET is_excluded = ?
                WHERE task_id = ? AND source_id = ?
                """,
                (int(is_excluded), task_id, source_id),
            )
            connection.commit()

        return self.get_source(task_id, source_id)

    def list_sources(self, task_id: str) -> list[RuleDraftSource]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM rule_draft_sources
                WHERE task_id = ?
                ORDER BY uploaded_at ASC, source_id ASC
                """,
                (task_id,),
            ).fetchall()

        return [rule_draft_source_from_row(row) for row in rows]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _migrate_rule_draft_schema(connection: sqlite3.Connection) -> None:
        source_columns = _load_table_columns(connection, "rule_draft_sources")
        if "is_excluded" not in source_columns:
            connection.execute(
                """
                ALTER TABLE rule_draft_sources
                ADD COLUMN is_excluded INTEGER NOT NULL DEFAULT 0
                """
            )
        if "normalized_path" not in source_columns:
            connection.execute(
                """
                ALTER TABLE rule_draft_sources
                ADD COLUMN normalized_path TEXT
                """
            )
        if "parse_error" not in source_columns:
            connection.execute(
                """
                ALTER TABLE rule_draft_sources
                ADD COLUMN parse_error TEXT
                """
            )


def _load_table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}
