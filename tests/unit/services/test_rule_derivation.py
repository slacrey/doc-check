from __future__ import annotations

from datetime import datetime, timezone
import json

from doc_check.domain.rule_drafts import RuleDraftSource, RuleDraftSourceType, RuleDraftStatus, RuleDraftTask
from doc_check.services.rule_derivation import RuleDerivationService
from doc_check.services.source_normalizer import SourceNormalizer
from tests.support.app_config import make_test_config
from tests.support.docx_samples import ensure_docx_samples


def test_rule_derivation_generates_aeos_structure_style_and_term_candidates(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    task_output_dir = config.rule_drafts_dir / "draft-1"
    task_output_dir.mkdir(parents=True, exist_ok=True)
    task = RuleDraftTask(
        task_id="draft-1",
        ruleset_id="aeos",
        status=RuleDraftStatus.CREATED,
        created_at=datetime.now(timezone.utc),
        created_by="admin@example.com",
        auth_source="x-forwarded-user",
        output_dir=task_output_dir,
    )

    normalizer = SourceNormalizer()
    sources: list[RuleDraftSource] = []
    for source_id, source_type, path in (
        ("source-standard", RuleDraftSourceType.STANDARD, fixture_paths["aeos_standard"]),
        ("source-template", RuleDraftSourceType.TEMPLATE, fixture_paths["valid"]),
    ):
        source_dir = task_output_dir / source_id
        source_dir.mkdir(parents=True, exist_ok=True)
        normalized_path = source_dir / "snapshot.json"
        normalized_path.write_text(
            json.dumps(
                normalizer.normalize(source_type=source_type, source_path=path).as_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        sources.append(
            RuleDraftSource(
                source_id=source_id,
                task_id=task.task_id,
                source_type=source_type,
                original_filename=path.name,
                stored_filename=path.name,
                storage_path=path,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=path.stat().st_size,
                is_excluded=False,
                uploaded_at=task.created_at,
                normalized_path=normalized_path,
                parse_error=None,
            )
        )

    draft = RuleDerivationService().derive(
        task=task,
        sources=tuple(sources),
        rulesets_dir=config.rulesets_dir,
    )

    heading_texts = [item["text"] for item in draft.structure_data["required_headings"]]
    paragraph_rule_ids = [item["rule_id"] for item in draft.style_data["paragraph_rules"]]

    assert draft.manifest_data["ruleset_id"] == "aeos"
    assert "1 总则" in heading_texts
    assert "1.1 目的" in heading_texts
    assert draft.structure_data["toc"]["required"] is True
    assert "style.body.font-name" in paragraph_rule_ids
    assert any(row["canonical"] == "网络与信息安全" and row["variant"] == "网络安全" for row in draft.terminology_rows)
    assert any(row["term"] == "黑名单" for row in draft.banned_term_rows)
