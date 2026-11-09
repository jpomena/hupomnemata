"""Estilos de campo compartilhados (v2).

Montserrat 13 no texto, rótulo 12/600 sem espaçamento de letras, borda de 1 px
em ``border_strong``, foco dourado e raio 6, como em ``design/DESIGN.md``.
Telas novas devem preferir ``ui_kit.input_field`` + ``ui_kit.form_field``, que
põem o rótulo acima do campo. Estes dicionários existem para as telas que ainda
passam ``label=`` direto ao ``TextField``/``Dropdown``.
"""

from typing import TypedDict

import flet as ft

from src.utils.types import ViewConfig


class TextFieldStyle(TypedDict, total=False):
    border_color: str
    focused_border_color: str
    cursor_color: str
    color: str
    label_style: ft.TextStyle
    border_radius: int | float
    content_padding: int | float | ft.Padding
    bgcolor: str
    border_width: int | float
    focused_border_width: int | float
    text_style: ft.TextStyle
    hint_style: ft.TextStyle


class DropdownStyle(TypedDict, total=False):
    border_color: str
    focused_border_color: str
    color: str
    label_style: ft.TextStyle
    border_radius: int | float
    content_padding: int | float | ft.Padding
    bgcolor: str
    border_width: int | float
    focused_border_width: int | float
    text_style: ft.TextStyle


def _color(config: ViewConfig, key: str, fallback: str) -> str:
    colors = config.colors
    return colors.get(key) or colors[fallback]


def _label_style(config: ViewConfig) -> ft.TextStyle:
    return ft.TextStyle(
        color=config.colors['muted'],
        weight=ft.FontWeight.W_600,
        font_family=config.font_families['montserrat'],
        size=12,
    )


def _input_text_style(config: ViewConfig) -> ft.TextStyle:
    return ft.TextStyle(
        color=config.colors['text'],
        size=13,
        weight=ft.FontWeight.W_500,
        font_family=config.font_families['montserrat'],
    )


def text_field_base_style(config: ViewConfig) -> TextFieldStyle:
    return {
        'border_color': _color(config, 'border_strong', 'border'),
        'focused_border_color': config.colors['gold'],
        'cursor_color': config.colors['gold'],
        'color': config.colors['text'],
        'label_style': _label_style(config),
        'border_radius': 6,
        'content_padding': ft.Padding.symmetric(horizontal=10, vertical=10),
        'bgcolor': _color(config, 'bg', 'surface'),
        'border_width': 1,
        'focused_border_width': 1,
    }


def text_field_style(config: ViewConfig) -> TextFieldStyle:
    return {
        **text_field_base_style(config),
        'text_style': _input_text_style(config),
        'hint_style': ft.TextStyle(
            color=_color(config, 'faint', 'muted'),
            weight=ft.FontWeight.W_500,
            font_family=config.font_families['montserrat'],
            size=13,
            letter_spacing=-0.08,
        ),
    }


def button_text_style(
    config: ViewConfig,
    size: str = 'montserrat_medium',
    weight: str = 'montserrat_normal',
) -> ft.TextStyle:
    return ft.TextStyle(
        font_family=config.font_families['montserrat'],
        size=config.font_sizes[size],
        weight=config.font_weights[weight],
        color=_color(config, 'on_gold', 'bg'),
    )


def dropdown_style(
    config: ViewConfig,
    theme: str | None = 'dark',
) -> DropdownStyle:
    del theme  # as cores já vêm do tema ativo em ``config.colors``
    return {
        'border_color': _color(config, 'border_strong', 'border'),
        'focused_border_color': config.colors['gold'],
        'color': config.colors['text'],
        'label_style': _label_style(config),
        'border_radius': 6,
        'content_padding': ft.Padding.symmetric(horizontal=10, vertical=8),
        'bgcolor': config.colors['surface'],
        'border_width': 1,
        'focused_border_width': 1,
        'text_style': _input_text_style(config),
    }
