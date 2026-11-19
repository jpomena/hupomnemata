import json
from pathlib import Path
from typing import Any, Dict

from src.configs.settings import ASSETS_DIR

_TEMPLATE_PATH = ASSETS_DIR / "templates" / "knowledge_graph.html"


def _load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(
            f"Template de grafo não encontrado: {path}. "
            "Verifique se assets/templates/knowledge_graph.html existe."
        )
    return path.read_text(encoding="utf-8")


def generate_graph_html(graph_data: Dict[str, Any], theme_mode: str = "dark", scale: float = 1.0) -> str:
    """
    Gera uma página HTML completa, autônoma e interativa com visualização D3.js v7.
    Apresenta física de forças (force-directed), zoom/pan, realce de ressonâncias,
    filtros e cartão de inspeção de nós, estilizado com a estética editorial clássica.

    O template é carregado de assets/templates/knowledge_graph.html. Os dados JSON
    são serializados com escape da sequência '</' para impedir injeção de fechamento
    de script.
    """
    is_dark = (theme_mode or "dark").lower() == "dark"
    bg_color = "#121212" if is_dark else "#F9F9FB"
    surface_color = "#1E1E1E" if is_dark else "#FFFFFF"
    text_color = "#E7E7E7" if is_dark else "#1A1A1A"
    text_muted = "#A0A0A0" if is_dark else "#666666"
    border_color = "#2E2E2E" if is_dark else "#E0E0E0"
    gold_accent = "#D4AF37" if is_dark else "#896200"
    link_stroke = "rgba(212, 175, 55, 0.35)" if is_dark else "rgba(137, 98, 0, 0.28)"

    data_json = json.dumps(graph_data, ensure_ascii=False).replace("</", r"<\/")

    template = _load_template(_TEMPLATE_PATH)
    rendered = template \
        .replace("__BG_COLOR__", bg_color) \
        .replace("__SURFACE_COLOR__", surface_color) \
        .replace("__TEXT_COLOR__", text_color) \
        .replace("__TEXT_MUTED__", text_muted) \
        .replace("__BORDER_COLOR__", border_color) \
        .replace("__GOLD_ACCENT__", gold_accent) \
        .replace("__LINK_STROKE__", link_stroke) \
        .replace("__THEME_MODE__", theme_mode or "dark")
    # Dados do usuário entram por último: um label contendo "__THEME_MODE__"
    # não pode ser interpretado como placeholder do template.
    return rendered.replace("__GRAPH_DATA__", data_json)
