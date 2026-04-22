from __future__ import annotations

from pathlib import Path

from doc_check.services.rule_catalog import load_ruleset_guide, list_ruleset_guides


def test_list_ruleset_guides_reads_all_supported_rulesets():
    guides = list_ruleset_guides(Path("rulesets"))

    assert [guide.ruleset_id for guide in guides] == ["aeos", "news_publicity", "speech"]


def test_load_ruleset_guide_flattens_aeos_rules_and_notes():
    guide = load_ruleset_guide(Path("rulesets"), "aeos")

    assert guide.document_type == "AEOS 制度文件"
    assert guide.total_rules == 18
    assert "国标版式" in guide.note.basis_summary
    assert any(entry.rule_id == "layout.page-width.a4" for entry in guide.entries)
    assert any(entry.rule_id == "punctuation.ascii-parentheses-cjk" for entry in guide.entries)


def test_load_ruleset_guide_flattens_speech_scope_labels():
    guide = load_ruleset_guide(Path("rulesets"), "speech")

    entry = next(entry for entry in guide.entries if entry.rule_id == "structure.speech.slogan-ending")
    assert entry.scope_label == "正文后 2 段"
