from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Mapping

from doc_check.domain.documents import ArtifactRecord, ArtifactStatus

ARTIFACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    ruleset_id TEXT NOT NULL,
    ruleset_version TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    auth_source TEXT NOT NULL,
    annotated_path TEXT,
    summary_path TEXT
);
"""


def artifact_record_to_row(record: ArtifactRecord) -> dict[str, object]:
    return {
        "artifact_id": record.artifact_id,
        "original_filename": record.original_filename,
        "stored_filename": record.stored_filename,
        "storage_path": str(record.storage_path),
        "content_type": record.content_type,
        "size_bytes": record.size_bytes,
        "ruleset_id": record.ruleset_id,
        "ruleset_version": record.ruleset_version,
        "status": record.status.value,
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "created_by": record.created_by,
        "auth_source": record.auth_source,
        "annotated_path": str(record.annotated_path) if record.annotated_path else None,
        "summary_path": str(record.summary_path) if record.summary_path else None,
    }


def artifact_row_to_record(row: Mapping[str, object]) -> ArtifactRecord:
    annotated_path = row["annotated_path"]
    summary_path = row["summary_path"]

    return ArtifactRecord(
        artifact_id=str(row["artifact_id"]),
        original_filename=str(row["original_filename"]),
        stored_filename=str(row["stored_filename"]),
        storage_path=Path(str(row["storage_path"])),
        content_type=str(row["content_type"]),
        size_bytes=int(row["size_bytes"]),
        ruleset_id=str(row["ruleset_id"]),
        ruleset_version=str(row["ruleset_version"]),
        status=ArtifactStatus(str(row["status"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        expires_at=datetime.fromisoformat(str(row["expires_at"])),
        created_by=str(row["created_by"]),
        auth_source=str(row["auth_source"]),
        annotated_path=Path(str(annotated_path)) if annotated_path else None,
        summary_path=Path(str(summary_path)) if summary_path else None,
    )
