from __future__ import annotations

from pathlib import Path
from string import Template


def render_html_template(templates_dir: Path, template_name: str, **context: object) -> str:
    template_path = templates_dir / template_name
    template = Template(template_path.read_text(encoding="utf-8"))
    rendered_context = {
        key: (value if isinstance(value, str) else str(value))
        for key, value in context.items()
    }
    return template.safe_substitute(rendered_context)
