import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from templates import render_template


def test_render_template_replaces_existing_placeholders():
    template = "Olá {{nome}}, empresa: {{empresa}}"
    context = {"nome": "João", "empresa": "Empresa A"}
    result = render_template(template, context)
    assert result == "Olá João, empresa: Empresa A"


def test_render_template_missing_placeholder_returns_empty_string():
    template = "Olá {{nome}}, cargo: {{cargo}}"
    context = {"nome": "Maria"}
    result = render_template(template, context)
    assert result == "Olá Maria, cargo: "
