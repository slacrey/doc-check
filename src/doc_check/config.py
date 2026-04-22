from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Mapping

DEFAULT_IDENTITY_HEADERS = (
    "x-forwarded-user",
    "x-auth-request-email",
    "x-remote-user",
)


def _resolve_path(raw_value: str | None, *, cwd: Path, default: Path) -> Path:
    if raw_value is None:
        return default.resolve()

    path = Path(raw_value)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def _parse_identity_headers(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None:
        return DEFAULT_IDENTITY_HEADERS

    headers = tuple(
        part.strip().lower()
        for part in raw_value.split(",")
        if part.strip()
    )
    return headers or DEFAULT_IDENTITY_HEADERS


@dataclass(frozen=True, slots=True)
class AppConfig:
    workspace_dir: Path
    data_dir: Path
    artifacts_dir: Path
    database_path: Path
    rulesets_dir: Path
    templates_dir: Path
    retention_days: int
    identity_headers: tuple[str, ...]
    local_user_id: str
    max_upload_bytes: int

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        cwd: Path | None = None,
    ) -> "AppConfig":
        env = os.environ if env is None else env
        workspace_dir = (cwd or Path.cwd()).resolve()
        default_data_dir = workspace_dir / ".doc-check-data"

        data_dir = _resolve_path(
            env.get("DOC_CHECK_DATA_DIR"),
            cwd=workspace_dir,
            default=default_data_dir,
        )
        artifacts_dir = _resolve_path(
            env.get("DOC_CHECK_ARTIFACTS_DIR"),
            cwd=workspace_dir,
            default=data_dir / "artifacts",
        )
        database_path = _resolve_path(
            env.get("DOC_CHECK_DB_PATH"),
            cwd=workspace_dir,
            default=data_dir / "doc-check.sqlite3",
        )
        rulesets_dir = _resolve_path(
            env.get("DOC_CHECK_RULESETS_DIR"),
            cwd=workspace_dir,
            default=workspace_dir / "rulesets",
        )
        templates_dir = _resolve_path(
            env.get("DOC_CHECK_TEMPLATES_DIR"),
            cwd=workspace_dir,
            default=workspace_dir / "src" / "doc_check" / "web" / "templates",
        )
        retention_days = int(env.get("DOC_CHECK_RETENTION_DAYS", "7"))
        max_upload_bytes = int(env.get("DOC_CHECK_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
        local_user_id = env.get("DOC_CHECK_LOCAL_USER_ID", "local")
        identity_headers = _parse_identity_headers(env.get("DOC_CHECK_IDENTITY_HEADERS"))

        if retention_days <= 0:
            raise ValueError("DOC_CHECK_RETENTION_DAYS must be greater than zero")
        if max_upload_bytes <= 0:
            raise ValueError("DOC_CHECK_MAX_UPLOAD_BYTES must be greater than zero")

        return cls(
            workspace_dir=workspace_dir,
            data_dir=data_dir,
            artifacts_dir=artifacts_dir,
            database_path=database_path,
            rulesets_dir=rulesets_dir,
            templates_dir=templates_dir,
            retention_days=retention_days,
            identity_headers=identity_headers,
            local_user_id=local_user_id,
            max_upload_bytes=max_upload_bytes,
        )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
