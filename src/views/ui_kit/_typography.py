"""Texto de interface, texto editorial e ícones.

Extraído de ``src/views/ui_kit.py``; a fachada reexporta a API pública.
"""

import flet as ft
from src.utils.types import ViewConfig
from src.utils.fa import fa_icon
from ._foundation import UI_TRACKING, W500, W600, s


def ui_text(
    c: ViewConfig,
    value: str,
    size: float = 13,
    weight: ft.FontWeight = W500,
    color: str | None = None,
    max_lines: int | None = 1,
    expand: bool | int | None = None,
    selectable: bool = False,
    italic: bool = False,
    tabular: bool = False,
    align: ft.TextAlign | None = None,
) -> ft.Text:
    """Texto de interface em Montserrat."""
    del tabular  # Flet 0.86 não expõe font features; Montserrat já tem algarismos alinhados
    return ft.Text(
        value=value,
        size=s(size),
        weight=weight,
        color=color or c.colors["text"],
        font_family=c.font_families["montserrat"],
        max_lines=max_lines,
        overflow=ft.TextOverflow.ELLIPSIS if max_lines else None,
        no_wrap=max_lines == 1,
        expand=expand,
        selectable=selectable,
        italic=italic,
        text_align=align,
        style=ft.TextStyle(letter_spacing=UI_TRACKING),
    )


def serif_text(
    c: ViewConfig,
    value: str,
    size: float = 18,
    weight: ft.FontWeight = W600,
    color: str | None = None,
    max_lines: int | None = None,
    italic: bool = False,
    selectable: bool = False,
    height: float | None = 1.5,
    expand: bool | int | None = None,
    align: ft.TextAlign | None = None,
    no_wrap: bool | None = None,
) -> ft.Text:
    """Texto de leitura em Cormorant (citações, sínteses, títulos)."""
    return ft.Text(
        value=value,
        size=s(size),
        weight=weight,
        color=color or c.colors["text"],
        font_family=c.font_families["cormorant"],
        max_lines=max_lines,
        overflow=ft.TextOverflow.ELLIPSIS if max_lines else None,
        no_wrap=(max_lines == 1) if no_wrap is None else no_wrap,
        expand=expand,
        text_align=align,
        italic=italic,
        selectable=selectable,
        style=ft.TextStyle(height=height),
    )


def label_text(c: ViewConfig, value: str, color: str | None = None) -> ft.Text:
    """Rótulo de seção: Montserrat 12/600, sem caixa alta."""
    return ui_text(c, value, size=12, weight=W600, color=color or c.colors["muted"])


def meta_text(c: ViewConfig, value: str, max_lines: int | None = 1) -> ft.Text:
    return ui_text(c, value, size=12, weight=W500, color=c.colors["faint"], max_lines=max_lines, tabular=True)


def icon(c: ViewConfig, name: str, size: float = 14, color: str | None = None, style: str = "solid") -> ft.Text:
    return fa_icon(name, size=s(size), color=color or c.colors["faint"], style=style)
