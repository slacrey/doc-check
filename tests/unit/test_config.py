from __future__ import annotations

from pathlib import Path

from doc_check.config import AppConfig


def test_from_env_uses_workspace_relative_defaults(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)

    assert config.workspace_dir == tmp_path.resolve()
    assert config.data_dir == (tmp_path / ".doc-check-data").resolve()
    assert config.artifacts_dir == (tmp_path / ".doc-check-data" / "artifacts").resolve()
    assert config.database_path == (tmp_path / ".doc-check-data" / "doc-check.sqlite3").resolve()
    assert config.rulesets_dir == (tmp_path / "rulesets").resolve()
    assert config.templates_dir == (tmp_path / "src" / "doc_check" / "web" / "templates").resolve()
    assert config.identity_headers[0] == "x-forwarded-user"
    assert config.retention_days == 7


def test_from_env_applies_overrides_and_normalizes_headers(tmp_path):
    config = AppConfig.from_env(
        {
            "DOC_CHECK_DATA_DIR": "runtime-data",
            "DOC_CHECK_ARTIFACTS_DIR": "runtime-artifacts",
            "DOC_CHECK_DB_PATH": "runtime-data/service.sqlite3",
            "DOC_CHECK_RULESETS_DIR": "runtime-rules",
            "DOC_CHECK_TEMPLATES_DIR": "runtime-templates",
            "DOC_CHECK_RETENTION_DAYS": "14",
            "DOC_CHECK_MAX_UPLOAD_BYTES": "2048",
            "DOC_CHECK_LOCAL_USER_ID": "review-bot",
            "DOC_CHECK_IDENTITY_HEADERS": "X-Remote-User, X-Forwarded-Email",
        },
        cwd=tmp_path,
    )

    assert config.data_dir == (tmp_path / "runtime-data").resolve()
    assert config.artifacts_dir == (tmp_path / "runtime-artifacts").resolve()
    assert config.database_path == (tmp_path / "runtime-data" / "service.sqlite3").resolve()
    assert config.rulesets_dir == (tmp_path / "runtime-rules").resolve()
    assert config.templates_dir == (tmp_path / "runtime-templates").resolve()
    assert config.retention_days == 14
    assert config.max_upload_bytes == 2048
    assert config.local_user_id == "review-bot"
    assert config.identity_headers == ("x-remote-user", "x-forwarded-email")


def test_ensure_directories_creates_expected_paths(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)

    config.ensure_directories()

    assert config.data_dir.is_dir()
    assert config.artifacts_dir.is_dir()
    assert config.database_path.parent.is_dir()
