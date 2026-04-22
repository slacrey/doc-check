from __future__ import annotations

from datetime import datetime, timezone

from doc_check.config import AppConfig
from doc_check.domain.rule_drafts import (
    RuleDraftSource,
    RuleDraftSourceType,
    RuleDraftStatus,
    RuleDraftTask,
)
from doc_check.persistence.repositories import RuleDraftRepository


def make_task(config: AppConfig, *, task_id: str) -> RuleDraftTask:
    created_at = datetime.now(timezone.utc)
    output_dir = config.rule_drafts_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    return RuleDraftTask(
        task_id=task_id,
        ruleset_id="aeos",
        status=RuleDraftStatus.CREATED,
        created_at=created_at,
        created_by="admin@example.com",
        auth_source="x-forwarded-user",
        output_dir=output_dir,
    )


def test_repository_round_trips_rule_draft_tasks(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    config.ensure_directories()
    repository = RuleDraftRepository(config.database_path)
    repository.init_schema()

    task = make_task(config, task_id="draft-1")
    repository.create_task(task)

    loaded = repository.get_task("draft-1")

    assert loaded == task


def test_repository_lists_rule_draft_tasks_in_reverse_created_order(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    config.ensure_directories()
    repository = RuleDraftRepository(config.database_path)
    repository.init_schema()

    first = make_task(config, task_id="draft-1")
    second = make_task(config, task_id="draft-2")
    repository.create_task(first)
    repository.create_task(second)

    task_ids = [task.task_id for task in repository.list_tasks()]

    assert task_ids == ["draft-2", "draft-1"]


def test_repository_round_trips_rule_draft_sources(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    config.ensure_directories()
    repository = RuleDraftRepository(config.database_path)
    repository.init_schema()

    task = make_task(config, task_id="draft-1")
    repository.create_task(task)

    source_dir = task.output_dir / "sources" / "source-1"
    source_dir.mkdir(parents=True, exist_ok=True)
    storage_path = source_dir / "original.docx"
    storage_path.write_bytes(b"placeholder")
    normalized_path = source_dir / "snapshot.json"
    normalized_path.write_text("{}", encoding="utf-8")
    source = RuleDraftSource(
        source_id="source-1",
        task_id=task.task_id,
        source_type=RuleDraftSourceType.TEMPLATE,
        original_filename="template.docx",
        stored_filename="original.docx",
        storage_path=storage_path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=11,
        is_excluded=False,
        uploaded_at=datetime.now(timezone.utc),
        normalized_path=normalized_path,
        parse_error=None,
    )

    repository.create_source(source)

    loaded_sources = repository.list_sources(task.task_id)

    assert loaded_sources == [source]


def test_repository_updates_source_exclusion_status(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    config.ensure_directories()
    repository = RuleDraftRepository(config.database_path)
    repository.init_schema()

    task = make_task(config, task_id="draft-1")
    repository.create_task(task)

    source_dir = task.output_dir / "sources" / "source-1"
    source_dir.mkdir(parents=True, exist_ok=True)
    storage_path = source_dir / "original.docx"
    storage_path.write_bytes(b"placeholder")
    source = RuleDraftSource(
        source_id="source-1",
        task_id=task.task_id,
        source_type=RuleDraftSourceType.SAMPLE,
        original_filename="sample.docx",
        stored_filename="original.docx",
        storage_path=storage_path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=11,
        is_excluded=False,
        uploaded_at=datetime.now(timezone.utc),
        normalized_path=None,
        parse_error=None,
    )
    repository.create_source(source)

    repository.update_source_exclusion(
        task_id=task.task_id,
        source_id=source.source_id,
        is_excluded=True,
    )

    loaded_source = repository.list_sources(task.task_id)[0]

    assert loaded_source.is_excluded is True


def test_init_schema_migrates_legacy_rule_draft_source_table(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    config.ensure_directories()
    repository = RuleDraftRepository(config.database_path)

    with repository._connect() as connection:
        connection.executescript(
            """
            CREATE TABLE rule_draft_tasks (
                task_id TEXT PRIMARY KEY,
                ruleset_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                auth_source TEXT NOT NULL,
                output_dir TEXT NOT NULL
            );

            CREATE TABLE rule_draft_sources (
                source_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES rule_draft_tasks(task_id)
            );
            """
        )
        connection.commit()

    repository.init_schema()

    task = make_task(config, task_id="draft-legacy")
    repository.create_task(task)

    source_dir = task.output_dir / "sources" / "source-legacy"
    source_dir.mkdir(parents=True, exist_ok=True)
    storage_path = source_dir / "original.docx"
    storage_path.write_bytes(b"placeholder")
    normalized_path = source_dir / "snapshot.json"
    normalized_path.write_text("{}", encoding="utf-8")
    source = RuleDraftSource(
        source_id="source-legacy",
        task_id=task.task_id,
        source_type=RuleDraftSourceType.TEMPLATE,
        original_filename="template.docx",
        stored_filename="original.docx",
        storage_path=storage_path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=11,
        is_excluded=False,
        uploaded_at=datetime.now(timezone.utc),
        normalized_path=normalized_path,
        parse_error=None,
    )

    repository.create_source(source)

    loaded_source = repository.list_sources(task.task_id)[0]

    assert loaded_source.normalized_path == normalized_path
    assert loaded_source.parse_error is None
