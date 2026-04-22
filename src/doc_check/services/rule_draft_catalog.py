from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from doc_check.domain.rule_drafts import RuleDraftTask
from doc_check.domain.rules import RulePack
from doc_check.rules.rule_pack import RulePackError, load_rule_pack

OUTPUT_FILENAMES = (
    "manifest.yaml",
    "structure.yaml",
    "style.yaml",
    "terminology.csv",
    "banned_terms.csv",
    "evidence.json",
)


@dataclass(frozen=True, slots=True)
class GeneratedDraftVersion:
    version: str
    files: tuple[str, ...]
    evidence_summary_lines: tuple[str, ...]
    diff_summary_lines: tuple[str, ...]
    has_changes: bool
    is_latest: bool


class RuleDraftCatalogService:
    def list_generated_versions(
        self,
        *,
        task: RuleDraftTask,
        rulesets_dir: Path,
    ) -> tuple[GeneratedDraftVersion, ...]:
        generated_root = task.output_dir / "generated"
        if not generated_root.exists():
            return ()

        try:
            active_pack = load_rule_pack(rulesets_dir / task.ruleset_id)
        except RulePackError:
            return ()

        versions: list[GeneratedDraftVersion] = []
        version_dirs = sorted((path for path in generated_root.iterdir() if path.is_dir()), reverse=True)
        for index, version_dir in enumerate(version_dirs):
            files = tuple(filename for filename in OUTPUT_FILENAMES if (version_dir / filename).exists())
            evidence_summary_lines = summarize_evidence(version_dir / "evidence.json")
            try:
                generated_pack = load_rule_pack(version_dir)
                diff_summary_lines = summarize_rule_pack_diff(active_pack, generated_pack)
            except RulePackError:
                diff_summary_lines = ("草案规则包无法加载，无法生成差异摘要。",)
            versions.append(
                GeneratedDraftVersion(
                    version=version_dir.name,
                    files=files,
                    evidence_summary_lines=evidence_summary_lines,
                    diff_summary_lines=diff_summary_lines,
                    has_changes=diff_summary_lines != ("与当前活动规则无差异。",),
                    is_latest=index == 0,
                )
            )

        return tuple(versions)


def summarize_rule_pack_diff(active_pack: RulePack, generated_pack: RulePack) -> tuple[str, ...]:
    lines: list[str] = []

    active_headings = {(rule.text, rule.level) for rule in active_pack.structure_rules.required_headings}
    generated_headings = {(rule.text, rule.level) for rule in generated_pack.structure_rules.required_headings}
    added_headings = generated_headings - active_headings
    removed_headings = active_headings - generated_headings
    if added_headings or removed_headings:
        lines.append(f"必备标题新增 {len(added_headings)} 项，移除 {len(removed_headings)} 项。")

    active_toc = active_pack.structure_rules.toc_rule
    generated_toc = generated_pack.structure_rules.toc_rule
    active_toc_state = (
        active_toc.required if active_toc is not None else None,
        active_toc.match_headings if active_toc is not None else None,
    )
    generated_toc_state = (
        generated_toc.required if generated_toc is not None else None,
        generated_toc.match_headings if generated_toc is not None else None,
    )
    if active_toc_state != generated_toc_state:
        lines.append("目录规则发生变化。")

    layout_changes = _count_mapping_differences(
        {rule.field: rule.expected for rule in active_pack.layout_rules},
        {rule.field: rule.expected for rule in generated_pack.layout_rules},
    )
    if layout_changes:
        lines.append(f"版式规则变更 {layout_changes} 项。")

    style_changes = _count_mapping_differences(
        {rule.rule_id: rule.expected for rule in active_pack.style_rules},
        {rule.rule_id: rule.expected for rule in generated_pack.style_rules},
    )
    if style_changes:
        lines.append(f"正文样式规则变更 {style_changes} 项。")

    active_terms = {(rule.canonical, rule.variant) for rule in active_pack.preferred_terms}
    generated_terms = {(rule.canonical, rule.variant) for rule in generated_pack.preferred_terms}
    added_terms = generated_terms - active_terms
    removed_terms = active_terms - generated_terms
    if added_terms or removed_terms:
        lines.append(f"术语词表新增 {len(added_terms)} 项，移除 {len(removed_terms)} 项。")

    active_banned = {rule.term for rule in active_pack.banned_terms}
    generated_banned = {rule.term for rule in generated_pack.banned_terms}
    added_banned = generated_banned - active_banned
    removed_banned = active_banned - generated_banned
    if added_banned or removed_banned:
        lines.append(f"禁用词表新增 {len(added_banned)} 项，移除 {len(removed_banned)} 项。")

    if not lines:
        return ("与当前活动规则无差异。",)
    return tuple(lines)


def summarize_evidence(evidence_path: Path) -> tuple[str, ...]:
    if not evidence_path.exists():
        return ("证据摘要不可用。",)

    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ("证据摘要不可用。",)

    if not isinstance(payload, dict):
        return ("证据摘要不可用。",)

    sources = payload.get("sources")
    if not isinstance(sources, dict):
        sources = {}

    required_headings = payload.get("required_headings")
    if not isinstance(required_headings, list):
        required_headings = []

    toc_required = bool(payload.get("toc_required"))
    layout_rule_count = _coerce_nonnegative_int(payload.get("layout_rule_count"))
    paragraph_rule_count = _coerce_nonnegative_int(payload.get("paragraph_rule_count"))
    terminology_count = _coerce_nonnegative_int(payload.get("terminology_count"))
    banned_term_count = _coerce_nonnegative_int(payload.get("banned_term_count"))

    return (
        "输入来源：正式规范 "
        f"{_coerce_nonnegative_int(sources.get('standard'))} 份，"
        f"标准模板 {_coerce_nonnegative_int(sources.get('template'))} 份，"
        f"样本文档 {_coerce_nonnegative_int(sources.get('sample'))} 份。",
        "推断结果：必备标题 "
        f"{len(required_headings)} 项，目录规则{'已启用' if toc_required else '未启用'}，"
        f"版式规则 {layout_rule_count} 项，正文样式规则 {paragraph_rule_count} 项。",
        f"术语候选：推荐术语 {terminology_count} 项，禁用表达 {banned_term_count} 项。",
    )


def _coerce_nonnegative_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _count_mapping_differences(active_values: dict[str, object], generated_values: dict[str, object]) -> int:
    keys = set(active_values) | set(generated_values)
    return sum(1 for key in keys if active_values.get(key) != generated_values.get(key))
