from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from doc_check.domain.documents import StoryType
from doc_check.domain.rules import RulePack, StyleRuleScope
from doc_check.rules.rule_pack import RulePackError, load_rule_pack

CATEGORY_LABELS = {
    "structure": "结构",
    "layout": "版式",
    "style": "样式",
    "terminology": "术语",
    "punctuation": "标点",
}

CATEGORY_ORDER = ("structure", "layout", "style", "terminology", "punctuation")

PUNCTUATION_RULES = {
    "detect_ascii_comma_in_cjk": (
        "punctuation.ascii-comma-cjk",
        "中文语境中使用了英文逗号。",
        "请将英文逗号替换为中文全角逗号。",
    ),
    "detect_mixed_commas": (
        "punctuation.mixed-comma",
        "同一段落中存在中英文逗号混用。",
        "请统一使用中文全角逗号或按规范统一标点风格。",
    ),
    "detect_ascii_colon_in_cjk": (
        "punctuation.ascii-colon-cjk",
        "中文语境中使用了英文冒号。",
        "请将英文冒号替换为中文全角冒号。",
    ),
    "detect_ascii_semicolon_in_cjk": (
        "punctuation.ascii-semicolon-cjk",
        "中文语境中使用了英文分号。",
        "请将英文分号替换为中文全角分号。",
    ),
    "detect_ascii_parentheses_in_cjk": (
        "punctuation.ascii-parentheses-cjk",
        "中文语境中使用了英文括号。",
        "请将英文括号替换为中文全角括号。",
    ),
}


@dataclass(frozen=True, slots=True)
class RulesetGuideNote:
    basis_summary: str
    scope_summary: str
    limitation_summary: str


RULESET_NOTES = {
    "aeos": RulesetGuideNote(
        basis_summary="基于国标版式与中文标点规范，并叠加 AEOS 制度文件的章节、目录、术语和禁用词要求。",
        scope_summary="适用于 AEOS 制度类 `.docx` 文件，覆盖版式、样式、目录、章节、术语、禁用词和中文标点。",
        limitation_summary="暂不覆盖依赖 Word 最终排版渲染的细项，也不替代人工做政策适用性判断。",
    ),
    "news_publicity": RulesetGuideNote(
        basis_summary="基于中文标点规范和新闻宣传写作常见审核口径，聚焦导语、标题、来源日期、绝对化和标题党表达。",
        scope_summary="适用于新闻宣传稿 `.docx` 文件，覆盖来源/日期、导语事实要素、标题表述、夸张和未经核实用语。",
        limitation_summary="不直接判断新闻事实真伪，也不替代宣传口径审批和舆情风险研判。",
    ),
    "speech": RulesetGuideNote(
        basis_summary="基于机关企事业单位常见发言稿写作规范，聚焦称谓、层次提示、收束语、讲话人口吻和网络化表达。",
        scope_summary="适用于讲话稿、发言稿、致辞、主持词等 `.docx` 文件，覆盖开场称谓、主体结构、结尾收束和口吻一致性。",
        limitation_summary="不替代领导意图把关、政策表态审定和现场语气风格调整。",
    ),
}


@dataclass(frozen=True, slots=True)
class RuleGuideEntry:
    rule_id: str
    category: str
    category_label: str
    severity: str
    disposition: str
    message: str
    suggestion: str | None
    scope_label: str


@dataclass(frozen=True, slots=True)
class RulesetGuide:
    ruleset_id: str
    version: str
    name: str
    document_type: str
    note: RulesetGuideNote
    entries: tuple[RuleGuideEntry, ...]
    category_counts: tuple[tuple[str, int], ...]

    @property
    def total_rules(self) -> int:
        return len(self.entries)


class RulesetGuideNotFoundError(LookupError):
    """Raised when a ruleset guide is unavailable."""


def list_ruleset_guides(rulesets_dir: Path) -> tuple[RulesetGuide, ...]:
    guides: list[RulesetGuide] = []
    if not rulesets_dir.exists():
        return ()

    for candidate in sorted(rulesets_dir.iterdir()):
        if not candidate.is_dir():
            continue
        try:
            guides.append(_build_ruleset_guide(load_rule_pack(candidate)))
        except RulePackError:
            continue

    return tuple(guides)


def load_ruleset_guide(rulesets_dir: Path, ruleset_id: str) -> RulesetGuide:
    ruleset_dir = (rulesets_dir / ruleset_id).resolve()
    try:
        rule_pack = load_rule_pack(ruleset_dir)
    except RulePackError as exc:
        raise RulesetGuideNotFoundError(f"Unknown ruleset: {ruleset_id}") from exc
    return _build_ruleset_guide(rule_pack)


def _build_ruleset_guide(rule_pack: RulePack) -> RulesetGuide:
    entries: list[RuleGuideEntry] = []

    for rule in rule_pack.structure_rules.required_headings:
        entries.append(
            RuleGuideEntry(
                rule_id=rule.rule_id,
                category="structure",
                category_label=CATEGORY_LABELS["structure"],
                severity=rule.severity.value,
                disposition=rule.disposition.value,
                message=f"文档应包含 {rule.text}，且标题层级为 {rule.level}。",
                suggestion=f"请补充 {rule.text} 章节，并使用标题 {rule.level} 样式。",
                scope_label="正文标题",
            )
        )

    toc_rule = rule_pack.structure_rules.toc_rule
    if toc_rule is not None:
        toc_message = "文档应包含目录。"
        if toc_rule.required and toc_rule.match_headings:
            toc_message = "文档应包含目录，且目录条目应与正文标题一致。"
        elif toc_rule.match_headings:
            toc_message = "目录条目应与正文标题一致。"

        entries.append(
            RuleGuideEntry(
                rule_id=toc_rule.rule_id,
                category="structure",
                category_label=CATEGORY_LABELS["structure"],
                severity=toc_rule.severity.value,
                disposition=toc_rule.disposition.value,
                message=toc_message,
                suggestion="请刷新目录并核对标题与页码。",
                scope_label="目录",
            )
        )

    for rule in rule_pack.structure_rules.story_text_rules:
        story_label = "页眉" if rule.story_type is StoryType.HEADER else "页脚"
        entries.append(
            RuleGuideEntry(
                rule_id=rule.rule_id,
                category="structure",
                category_label=CATEGORY_LABELS["structure"],
                severity=rule.severity.value,
                disposition=rule.disposition.value,
                message=f"{story_label}应包含：{rule.expected_contains}",
                suggestion=f"请补充标准 {story_label} 内容。",
                scope_label=story_label,
            )
        )

    for rule in rule_pack.structure_rules.paragraph_pattern_rules:
        entries.append(
            RuleGuideEntry(
                rule_id=rule.rule_id,
                category="structure",
                category_label=CATEGORY_LABELS["structure"],
                severity=rule.severity.value,
                disposition=rule.disposition.value,
                message=rule.message,
                suggestion=rule.suggestion,
                scope_label=_paragraph_scope_label(
                    first_n_paragraphs=rule.first_n_paragraphs,
                    last_n_paragraphs=rule.last_n_paragraphs,
                ),
            )
        )

    for rule in rule_pack.structure_rules.paragraph_signal_rules:
        entries.append(
            RuleGuideEntry(
                rule_id=rule.rule_id,
                category="structure",
                category_label=CATEGORY_LABELS["structure"],
                severity=rule.severity.value,
                disposition=rule.disposition.value,
                message=rule.message,
                suggestion=rule.suggestion,
                scope_label=_paragraph_scope_label(
                    first_n_paragraphs=rule.first_n_paragraphs,
                    last_n_paragraphs=rule.last_n_paragraphs,
                ),
            )
        )

    for rule in rule_pack.structure_rules.paragraph_metric_rules:
        entries.append(
            RuleGuideEntry(
                rule_id=rule.rule_id,
                category="structure",
                category_label=CATEGORY_LABELS["structure"],
                severity=rule.severity.value,
                disposition=rule.disposition.value,
                message=rule.message,
                suggestion=rule.suggestion,
                scope_label=_paragraph_scope_label(
                    first_n_paragraphs=rule.first_n_paragraphs,
                    last_n_paragraphs=rule.last_n_paragraphs,
                ),
            )
        )

    for rule in rule_pack.layout_rules:
        entries.append(
            RuleGuideEntry(
                rule_id=rule.rule_id,
                category="layout",
                category_label=CATEGORY_LABELS["layout"],
                severity=rule.severity.value,
                disposition=rule.disposition.value,
                message=rule.message,
                suggestion="请按规则要求调整页面版式。",
                scope_label="页面版式",
            )
        )

    for rule in rule_pack.style_rules:
        scope_label = "样式链" if rule.scope is StyleRuleScope.STYLE_CHAIN else "正文段落"
        entries.append(
            RuleGuideEntry(
                rule_id=rule.rule_id,
                category="style",
                category_label=CATEGORY_LABELS["style"],
                severity=rule.severity.value,
                disposition=rule.disposition.value,
                message=rule.message,
                suggestion="请按标准样式统一格式。",
                scope_label=scope_label,
            )
        )

    for rule in rule_pack.preferred_terms:
        entries.append(
            RuleGuideEntry(
                rule_id=rule.rule_id,
                category="terminology",
                category_label=CATEGORY_LABELS["terminology"],
                severity=rule.severity.value,
                disposition=rule.disposition.value,
                message=f"术语“{rule.variant}”应统一为“{rule.canonical}”。",
                suggestion=rule.suggestion,
                scope_label="正文全文",
            )
        )

    for rule in rule_pack.banned_terms:
        entries.append(
            RuleGuideEntry(
                rule_id=rule.rule_id,
                category="terminology",
                category_label=CATEGORY_LABELS["terminology"],
                severity=rule.severity.value,
                disposition=rule.disposition.value,
                message=rule.message,
                suggestion=rule.suggestion,
                scope_label="正文全文",
            )
        )

    for key, enabled in rule_pack.manifest.punctuation_rules.items():
        if not enabled or key not in PUNCTUATION_RULES:
            continue
        rule_id, message, suggestion = PUNCTUATION_RULES[key]
        entries.append(
            RuleGuideEntry(
                rule_id=rule_id,
                category="punctuation",
                category_label=CATEGORY_LABELS["punctuation"],
                severity="warning",
                disposition="suggestion",
                message=message,
                suggestion=suggestion,
                scope_label="正文全文",
            )
        )

    counter = Counter(entry.category for entry in entries)
    category_counts = tuple(
        (CATEGORY_LABELS[category], counter[category])
        for category in CATEGORY_ORDER
        if counter.get(category)
    )

    return RulesetGuide(
        ruleset_id=rule_pack.ruleset_id,
        version=rule_pack.version,
        name=rule_pack.manifest.name,
        document_type=rule_pack.manifest.document_type,
        note=RULESET_NOTES.get(
            rule_pack.ruleset_id,
            RulesetGuideNote(
                basis_summary="基于当前规则包中的可自动化检查项生成。",
                scope_summary=f"适用于 {rule_pack.manifest.document_type} `.docx` 文件。",
                limitation_summary="未覆盖的语义和业务判断仍需人工复核。",
            ),
        ),
        entries=tuple(entries),
        category_counts=category_counts,
    )


def _paragraph_scope_label(
    *,
    first_n_paragraphs: int | None,
    last_n_paragraphs: int | None,
) -> str:
    if first_n_paragraphs is not None and last_n_paragraphs is not None:
        return f"正文前 {first_n_paragraphs} 段 / 后 {last_n_paragraphs} 段"
    if first_n_paragraphs is not None:
        return f"正文前 {first_n_paragraphs} 段"
    if last_n_paragraphs is not None:
        return f"正文后 {last_n_paragraphs} 段"
    return "正文全文"
