from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Mapping

from doc_check.domain.documents import ArtifactRecord, ArtifactStatus
from doc_check.domain.rule_drafts import RuleDraftSource, RuleDraftSourceType, RuleDraftStatus, RuleDraftTask

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

RULE_DRAFTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS rule_draft_tasks (
    task_id TEXT PRIMARY KEY,
    ruleset_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    auth_source TEXT NOT NULL,
    output_dir TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_draft_sources (
    source_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    is_excluded INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT NOT NULL,
    normalized_path TEXT,
    parse_error TEXT,
    FOREIGN KEY(task_id) REFERENCES rule_draft_tasks(task_id)
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


def rule_draft_task_to_row(task: RuleDraftTask) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "ruleset_id": task.ruleset_id,
        "status": task.status.value,
        "created_at": task.created_at.isoformat(),
        "created_by": task.created_by,
        "auth_source": task.auth_source,
        "output_dir": str(task.output_dir),
    }


def rule_draft_task_from_row(row: Mapping[str, object]) -> RuleDraftTask:
    return RuleDraftTask(
        task_id=str(row["task_id"]),
        ruleset_id=str(row["ruleset_id"]),
        status=RuleDraftStatus(str(row["status"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        created_by=str(row["created_by"]),
        auth_source=str(row["auth_source"]),
        output_dir=Path(str(row["output_dir"])),
    )


def rule_draft_source_to_row(source: RuleDraftSource) -> dict[str, object]:
    return {
        "source_id": source.source_id,
        "task_id": source.task_id,
        "source_type": source.source_type.value,
        "original_filename": source.original_filename,
        "stored_filename": source.stored_filename,
        "storage_path": str(source.storage_path),
        "content_type": source.content_type,
        "size_bytes": source.size_bytes,
        "is_excluded": int(source.is_excluded),
        "uploaded_at": source.uploaded_at.isoformat(),
        "normalized_path": str(source.normalized_path) if source.normalized_path else None,
        "parse_error": source.parse_error,
    }


def rule_draft_source_from_row(row: Mapping[str, object]) -> RuleDraftSource:
    normalized_path = row["normalized_path"]
    return RuleDraftSource(
        source_id=str(row["source_id"]),
        task_id=str(row["task_id"]),
        source_type=RuleDraftSourceType(str(row["source_type"])),
        original_filename=str(row["original_filename"]),
        stored_filename=str(row["stored_filename"]),
        storage_path=Path(str(row["storage_path"])),
        content_type=str(row["content_type"]),
        size_bytes=int(row["size_bytes"]),
        is_excluded=bool(row["is_excluded"]),
        uploaded_at=datetime.fromisoformat(str(row["uploaded_at"])),
        normalized_path=Path(str(normalized_path)) if normalized_path else None,
        parse_error=str(row["parse_error"]) if row["parse_error"] is not None else None,
    )
