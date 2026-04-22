from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class RuleDraftStatus(StrEnum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RuleDraftSourceType(StrEnum):
    STANDARD = "standard"
    TEMPLATE = "template"
    SAMPLE = "sample"


@dataclass(frozen=True, slots=True)
class RuleDraftTask:
    task_id: str
    ruleset_id: str
    status: RuleDraftStatus
    created_at: datetime
    created_by: str
    auth_source: str
    output_dir: Path

    def as_public_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "ruleset_id": self.ruleset_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "auth_source": self.auth_source,
        }


@dataclass(frozen=True, slots=True)
class RuleDraftSource:
    source_id: str
    task_id: str
    source_type: RuleDraftSourceType
    original_filename: str
    stored_filename: str
    storage_path: Path
    content_type: str
    size_bytes: int
    is_excluded: bool
    uploaded_at: datetime
    normalized_path: Path | None = None
    parse_error: str | None = None
