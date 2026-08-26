"""Contrato de configuracao visual recebido pelos composers."""

from dataclasses import dataclass

import flet as ft


@dataclass(frozen=True)
class ViewConfig:
    """Agrupa os parametros visuais carregados pelo ponto de composicao."""

    colors: dict[str, str]
    fonts: dict[str, str]
    page_fonts: dict[str, str]
    font_size: dict[str, int | float]
    font_weight: dict[str, ft.FontWeight]
    ui: dict[str, int | float]
    texts: dict[str, dict[str, str]]
    core_menus: dict[str, str]
    main_view_cards: dict[str, dict[str, str]]
