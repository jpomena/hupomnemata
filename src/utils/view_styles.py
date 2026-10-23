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
    content_padding: int | float
    bgcolor: str
    border_width: int | float
    text_style: ft.TextStyle
    hint_style: ft.TextStyle


class DropdownStyle(TypedDict, total=False):
    border_color: str
    focused_border_color: str
    color: str
    label_style: ft.TextStyle
    border_radius: int | float
    content_padding: int | float
    bgcolor: str
    border_width: int | float
    text_style: ft.TextStyle


def text_field_base_style(config: ViewConfig) -> TextFieldStyle:
    return {
        'border_color': config.colors['border'],
        'focused_border_color': config.colors['gold'],
        'cursor_color': config.colors['gold'],
        'color': config.colors['text'],
        'label_style': ft.TextStyle(
            color=config.colors['muted'],
            weight=config.font_weights['montserrat_normal'],
            font_family=config.font_families['montserrat'],
            letter_spacing=2,
            size=12,
        ),
        'border_radius': config.ui['card_radius'],
        'content_padding': config.ui['card_padding'],
        'bgcolor': config.colors['surface'],
        'border_width': 2,
    }


def text_field_style(config: ViewConfig) -> TextFieldStyle:
    return {
        **text_field_base_style(config),
        'text_style': ft.TextStyle(
            color=config.colors['text'],
            size=config.font_sizes['cormorant_small'],
            weight=config.font_weights['cormorant_semibold'],
            font_family=config.font_families['cormorant'],
        ),
        'hint_style': ft.TextStyle(
            color=config.colors['muted'],
            weight=config.font_weights['montserrat_normal'],
            font_family=config.font_families['montserrat'],
            letter_spacing=2,
            size=12,
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
        color=config.colors['bg']
    )


def dropdown_style(
    config: ViewConfig,
    theme: str | None = 'dark',
) -> DropdownStyle:
    option_text_color = (
        config.colors['black']
        if theme == 'light'
        else config.colors['muted']
    )
    text_style = ft.TextStyle(
        color=option_text_color,
        weight=config.font_weights['montserrat_normal'],
        font_family=config.font_families['montserrat'],
        letter_spacing=2,
        size=12,
    )
    return {
        'border_color': config.colors['border'],
        'focused_border_color': config.colors['gold'],
        'color': config.colors['text'],
        'label_style': text_style,
        'border_radius': config.ui['card_radius'],
        'content_padding': config.ui['card_padding'],
        'bgcolor': config.colors['surface'],
        'border_width': 2,
        'text_style': text_style,
    }
