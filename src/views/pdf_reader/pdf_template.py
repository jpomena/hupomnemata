import html
import json
from pathlib import Path
from typing import Any

from src.configs.settings import ASSETS_DIR

_TEMPLATE_PATH = ASSETS_DIR / "templates" / "pdf_viewer.html"


def _load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(
            f"Template de PDF não encontrado: {path}. "
            "Verifique se assets/templates/pdf_viewer.html existe."
        )
    return path.read_text(encoding="utf-8")


def generate_pdf_viewer_html(
    pdf_base64: str,
    title: str,
    annotations: list[dict[str, Any]] | None = None,
    theme_mode: str = "dark",
) -> str:
    """Gera um visualizador de PDF completo e autônomo baseado em PDF.js (Mozilla).

    Apresenta tema escuro e dourado alinhado ao Hupomnemata, zoom, navegação de páginas,
    barra de anotações e interface responsiva.

    O template é carregado de assets/templates/pdf_viewer.html. O título é escapado
    com html.escape antes de ser interpolado em HTML.
    """
    is_dark = (theme_mode or "dark").lower() == "dark"
    bg_color = "#121212" if is_dark else "#F9F9FB"
    surface_color = "#1E1E1E" if is_dark else "#FFFFFF"
    text_color = "#E7E7E7" if is_dark else "#1A1A1A"
    gold_accent = "#D4AF37" if is_dark else "#896200"
    border_color = "#2E2E2E" if is_dark else "#E0E0E0"

    ann_json = json.dumps(annotations or [], ensure_ascii=False).replace(
        "</", r"<\/"
    )
    safe_title = html.escape(title, quote=True)

    template = _load_template(_TEMPLATE_PATH)
    rendered = template \
        .replace("__BG_COLOR__", bg_color) \
        .replace("__SURFACE_COLOR__", surface_color) \
        .replace("__TEXT_COLOR__", text_color) \
        .replace("__GOLD_ACCENT__", gold_accent) \
        .replace("__BORDER_COLOR__", border_color) \
        .replace("__THEME_MODE__", theme_mode or "dark")
    # Conteúdo dinâmico por último, para não colidir com placeholders.
    return rendered \
        .replace("__PDF_BASE64__", pdf_base64) \
        .replace("__TITLE__", safe_title) \
        .replace("__ANNOTATIONS_JSON__", ann_json)
