"""Ícones do Font Awesome Free desenhados como texto com a fonte local.

O mapa nome -> codepoint fica em ``src/configs/fa_codepoints.json``. Cada entrada
guarda ``[codepoint, estilos]``, onde ``estilos`` é uma máscara: 1 = solid,
2 = regular. Pedir ``regular`` para um ícone que só existe em ``solid`` cai
automaticamente no ``solid``.
"""

import json
from functools import lru_cache
from pathlib import Path

import flet as ft

_CODEPOINTS_PATH = (
    Path(__file__).resolve().parents[1] / "configs" / "fa_codepoints.json"
)
FA_SOLID = "FA Solid"
FA_REGULAR = "FA Regular"


@lru_cache(maxsize=1)
def _codepoints() -> dict[str, list[int]]:
    with open(_CODEPOINTS_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def has_icon(name: str) -> bool:
    return name in _codepoints()


def glyph(name: str, style: str = "solid") -> tuple[str, str]:
    """Retorna ``(caractere, família)`` para o ícone pedido."""
    entry = _codepoints().get(name) or _codepoints()["circle"]
    codepoint, styles = entry
    wants_regular = style == "regular" and bool(styles & 2)
    family = FA_REGULAR if wants_regular or not styles & 1 else FA_SOLID
    return chr(codepoint), family


def fa_icon(
    name: str,
    size: float = 14,
    color: str | None = None,
    style: str = "solid",
    tooltip: str | None = None,
) -> ft.Text:
    """Cria um ``ft.Text`` que desenha o ícone com a fonte do Font Awesome."""
    char, family = glyph(name, style)
    return ft.Text(
        value=char,
        size=size,
        color=color,
        font_family=family,
        tooltip=tooltip,
        no_wrap=True,
        text_align=ft.TextAlign.CENTER,
        width=size * 1.3,
    )
