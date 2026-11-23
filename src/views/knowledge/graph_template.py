import json
from pathlib import Path
from typing import Any, Dict

from src.configs.settings import ASSETS_DIR, template_palette

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
    palette = template_palette(theme_mode)
    bg_color = palette["bg"]
    surface_color = palette["surface"]
    text_color = palette["text"]
    text_muted = palette["text_muted"]
    border_color = palette["border"]
    gold_accent = palette["gold"]
    link_stroke = palette["link_stroke"]

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
