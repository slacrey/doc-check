from __future__ import annotations

from pathlib import Path

from docx import Document as load_document

from doc_check.domain.documents import LocationAnchorKind, StoryType
from doc_check.domain.findings import CommentWriteResult
from doc_check.domain.rules import RuleFinding
from doc_check.parsers.docx_reader import iter_container_paragraphs


class CommentWriteError(ValueError):
    """Raised when an annotated document cannot be produced."""


def write_annotated_docx(
    *,
    source_path: str | Path,
    findings: tuple[RuleFinding, ...] | list[RuleFinding],
    output_path: str | Path,
    author: str = "doc-check",
    initials: str = "DC",
) -> CommentWriteResult:
    source = Path(source_path).resolve()
    destination = Path(output_path).resolve()

    try:
        document = load_document(source)
    except Exception as exc:  # pragma: no cover - guarded by parser tests and API validation
        raise CommentWriteError(f"Unable to open source document: {source.name}") from exc

    paragraphs = [paragraph for _, paragraph in iter_container_paragraphs(document)]
    commented: list[RuleFinding] = []
    summary_only: list[RuleFinding] = []
    skipped: list[RuleFinding] = []

    for finding in findings:
        location = finding.location
        if (
            location is None
            or location.story_type is not StoryType.MAIN
            or location.anchor_kind is not LocationAnchorKind.COMMENTABLE
        ):
            summary_only.append(finding)
            continue

        if location.paragraph_index >= len(paragraphs):
            skipped.append(finding)
            continue

        paragraph = paragraphs[location.paragraph_index]
        if location.run_start is None or location.run_end is None:
            summary_only.append(finding)
            continue

        runs = paragraph.runs
        if location.run_start >= len(runs) or location.run_end >= len(runs):
            summary_only.append(finding)
            continue

        selected_runs = runs[location.run_start : location.run_end + 1]
        if not selected_runs:
            summary_only.append(finding)
            continue

        try:
            document.add_comment(
                selected_runs,
                _format_comment_text(finding),
                author=author,
                initials=initials,
            )
        except Exception:
            summary_only.append(finding)
            continue

        commented.append(finding)

    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(destination)

    return CommentWriteResult(
        output_path=destination,
        commented_findings=tuple(commented),
        summary_only_findings=tuple(summary_only),
        skipped_findings=tuple(skipped),
    )


def _format_comment_text(finding: RuleFinding) -> str:
    lines = [finding.message]
    if finding.suggestion:
        lines.append(f"建议：{finding.suggestion}")
    if finding.evidence:
        lines.append(f"证据：{finding.evidence}")
    lines.append(f"规则：{finding.rule_id}")
    return "\n".join(lines)
