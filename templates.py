"""Funções de template para placeholders no formato {{coluna}}."""

import re
from typing import Any, Dict

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render_template(template: str, context: Dict[str, Any]) -> str:
    """Renderiza placeholders {{chave}} usando os dados de contexto.

    Placeholders sem correspondência são substituídos por string vazia.
    """

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        value = context.get(key, "")
        if value is None:
            return ""
        return str(value)

    return PLACEHOLDER_PATTERN.sub(_replace, template)
