from __future__ import annotations

from doc_check.domain.rule_drafts import RuleDraftSourceType
from doc_check.services.source_normalizer import SourceNormalizer
from tests.support.docx_samples import ensure_docx_samples


def test_source_normalizer_extracts_headings_layout_and_body_signals(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)

    snapshot = SourceNormalizer().normalize(
        source_type=RuleDraftSourceType.TEMPLATE,
        source_path=fixture_paths["valid"],
    )

    assert snapshot.source_type is RuleDraftSourceType.TEMPLATE
    assert snapshot.headings[:2] == ("1 总则", "1.1 目的")
    assert snapshot.toc_titles == ("1 总则", "1.1 目的")
    assert snapshot.header_texts == ("AEOS 文件页眉",)
    assert snapshot.footer_texts == ("AEOS 文件页脚",)
    assert snapshot.sections[0].page_width_mm == 210.0
    assert any(paragraph.text == "本制度适用于 AEOS 管理体系。" for paragraph in snapshot.body_paragraphs)
