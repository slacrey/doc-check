from __future__ import annotations

from pathlib import Path

from doc_check.parsers.docx_reader import read_docx_snapshot
from doc_check.rules.engine import RuleEngine
from doc_check.rules.rule_pack import load_rule_pack
from tests.support.docx_samples import ensure_docx_samples


def test_news_publicity_ruleset_accepts_valid_sample(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    rule_pack = load_rule_pack(Path("rulesets/news_publicity"))

    evaluation = RuleEngine().evaluate(read_docx_snapshot(fixture_paths["news_valid"]), rule_pack)

    assert evaluation.ruleset_id == "news_publicity"
    assert evaluation.ruleset_version == "2026.05"
    assert evaluation.findings == ()


def test_news_publicity_ruleset_flags_title_and_source_issues(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    rule_pack = load_rule_pack(Path("rulesets/news_publicity"))

    evaluation = RuleEngine().evaluate(read_docx_snapshot(fixture_paths["news_errors"]), rule_pack)
    rule_ids = {finding.rule_id for finding in evaluation.findings}

    assert "structure.news.source-or-date" in rule_ids
    assert "structure.news.title-no-ending-punctuation" in rule_ids
    assert "structure.news.lead-5w1h-lite" in rule_ids
    assert "structure.news.date-format" in rule_ids
    assert "structure.news.colloquial-adverb" in rule_ids
    assert "structure.news.title-overclaim" in rule_ids
    assert "structure.news.absolute-language" in rule_ids
    assert "structure.news.title-length" in rule_ids
    assert "structure.news.title-exclamation-count" in rule_ids
    assert "terminology.news.banned.unverified" in rule_ids
    assert "terminology.news.banned.clickbait-explosive" in rule_ids


def test_speech_ruleset_accepts_valid_sample(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    rule_pack = load_rule_pack(Path("rulesets/speech"))

    evaluation = RuleEngine().evaluate(read_docx_snapshot(fixture_paths["speech_valid"]), rule_pack)

    assert evaluation.ruleset_id == "speech"
    assert evaluation.ruleset_version == "2026.05"
    assert evaluation.findings == ()


def test_speech_ruleset_flags_title_salutation_and_informal_language(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    rule_pack = load_rule_pack(Path("rulesets/speech"))

    evaluation = RuleEngine().evaluate(read_docx_snapshot(fixture_paths["speech_errors"]), rule_pack)
    rule_ids = {finding.rule_id for finding in evaluation.findings}

    assert "structure.speech.title-keyword" in rule_ids
    assert "structure.speech.salutation" in rule_ids
    assert "structure.speech.no-news-byline" in rule_ids
    assert "structure.speech.closing" in rule_ids
    assert "structure.speech.layering-cue" in rule_ids
    assert "structure.speech.organization-voice" in rule_ids
    assert "structure.speech.first-person-voice" in rule_ids
    assert "terminology.speech.banned.internet-perfect" in rule_ids
    assert "terminology.speech.banned.internet-explosive" in rule_ids


def test_speech_ruleset_flags_salutation_colon_error(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    rule_pack = load_rule_pack(Path("rulesets/speech"))

    evaluation = RuleEngine().evaluate(
        read_docx_snapshot(fixture_paths["speech_salutation_errors"]),
        rule_pack,
    )
    rule_ids = {finding.rule_id for finding in evaluation.findings}

    assert "structure.speech.salutation-colon" in rule_ids
    assert "structure.speech.salutation" not in rule_ids


def test_speech_ruleset_flags_slogan_style_ending(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    rule_pack = load_rule_pack(Path("rulesets/speech"))

    evaluation = RuleEngine().evaluate(
        read_docx_snapshot(fixture_paths["speech_slogan_errors"]),
        rule_pack,
    )
    rule_ids = {finding.rule_id for finding in evaluation.findings}

    assert "structure.speech.slogan-ending" in rule_ids
    assert "structure.speech.closing" not in rule_ids
