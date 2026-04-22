from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt


def ensure_docx_samples(fixtures_dir: Path) -> dict[str, Path]:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    valid_path = fixtures_dir / "aeos-valid-sample.docx"
    format_errors_path = fixtures_dir / "aeos-format-errors.docx"

    _build_valid_sample(valid_path)
    _build_format_error_sample(format_errors_path)

    return {
        "valid": valid_path,
        "format_errors": format_errors_path,
    }


def _build_valid_sample(path: Path) -> None:
    document = Document()
    body_style = _ensure_paragraph_style(document, "AEOS Body")
    toc_one = _ensure_paragraph_style(document, "TOC 1", base_style_name="Normal")
    toc_two = _ensure_paragraph_style(document, "TOC 2", base_style_name="Normal")

    document.add_paragraph("1 总则\t1", style=toc_one.name)
    document.add_paragraph("1.1 目的\t2", style=toc_two.name)
    document.add_paragraph("1 总则", style="Heading 1")
    document.add_paragraph("本制度适用于 AEOS 管理体系。", style=body_style.name)
    document.add_paragraph("网络与信息安全要求统一执行。", style=body_style.name)

    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "表格中的适用条款"
    table.cell(0, 0).paragraphs[0].style = body_style

    document.add_page_break()
    document.add_paragraph("1.1 目的", style="Heading 2")
    document.add_paragraph("统一检查格式和术语。", style=body_style.name)

    section = document.sections[0]
    section.header.paragraphs[0].text = "AEOS 文件页眉"
    section.footer.paragraphs[0].text = "AEOS 文件页脚"

    document.save(path)


def _build_format_error_sample(path: Path) -> None:
    document = Document()
    body_style = _ensure_paragraph_style(document, "AEOS Body")

    document.add_paragraph("1 总则", style="Heading 1")
    inherited = document.add_paragraph("继承样式的正文段落。", style=body_style.name)
    inherited.paragraph_format.alignment = None

    nonstandard = document.add_paragraph("直接设置为单倍行距的段落。", style=body_style.name)
    nonstandard.paragraph_format.line_spacing = 1.0
    nonstandard.paragraph_format.space_after = Pt(0)
    document.add_paragraph("网络安全,黑名单管理要求。", style=body_style.name)

    section = document.sections[0]
    section.header.paragraphs[0].text = "格式错误样本页眉"
    section.footer.paragraphs[0].text = "格式错误样本页脚"

    document.save(path)


def _ensure_paragraph_style(
    document: Document,
    name: str,
    *,
    base_style_name: str = "Normal",
):
    try:
        style = document.styles[name]
    except KeyError:
        style = document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)

    style.base_style = document.styles[base_style_name]
    style.font.name = "SimSun"
    style.font.size = Pt(12)
    style.paragraph_format.line_spacing = 1.5
    style.paragraph_format.left_indent = Pt(24)
    style.paragraph_format.space_after = Pt(6)
    return style
