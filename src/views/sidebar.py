"""Composer da barra lateral de navegacao."""

import flet as ft

from typing import Callable
from src.utils.ft_controls import ControlsUtils
from src.utils.ft_icons import get_icon
from src.utils.types import ViewConfig


class SidebarComposer:
    """Compoe marca, navegacao e nota da barra lateral."""

    def __init__(
            self, scale: float, config: ViewConfig,
            on_navigate: Callable[[str], None]
    ) -> None:
        self.scale = scale
        self.config = config
        self.on_navigate = on_navigate

    def _compose_branding(self) -> ft.Container:
        """Cria a marca e o slogan exibidos no topo."""
        return ft.Container(
            padding=self.config.ui["sidebar_padding"],
            bgcolor=self.config.colors["surface"],
            content=ft.Column(
                controls=[
                    ft.TextButton(
                        content=ft.Text(
                            value=self.config.texts["app"]["name_normalized"],
                            size=self.config.font_sizes["greek_brand"],
                            weight=self.config.font_weights["greek_semibold"],
                            color=self.config.colors["text"],
                            font_family=self.config.font_families["greek"],
                            style=ft.TextStyle(letter_spacing=4),
                            align=ft.Alignment.CENTER
                        ),
                        on_click=lambda e: self.on_navigate("dashboard")
                    ),
                    ft.Text(
                        value=self.config.texts["app"]["slogan"],
                        align=ft.Alignment.BOTTOM_CENTER,
                        font_family=self.config.font_families["cormorant"],
                        color=self.config.colors["muted"],
                        style=ft.TextStyle(letter_spacing=3),
                        size=self.config.font_sizes["cormorant_small"],
                        weight=self.config.font_weights[
                            "cormorant_semibold"
                        ],
                    ),
                ],
                spacing=6,
            ),
        )

    def _compose_navigation(self) -> ft.Container:
        """Cria os itens de navegacao da secao de cadernos."""
        menu_items = [
            ControlsUtils.create_sidebar_menu(
                label_ref=label,
                icon_data=get_icon(icon_name),
                scale=self.scale,
                config=self.config,
                on_navigate=self.on_navigate
            )
            for label, icon_name in self.config.core_menus.items()
        ]
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value="Cadernos",
                        font_family=self.config.font_families["greek"],
                        size=self.config.font_sizes["cormorant_small"],
                        color=self.config.colors["muted"],
                        weight=self.config.font_weights[
                            "montserrat_semibold"
                        ],
                    ),
                    *menu_items,
                ],
                spacing=self.config.ui["modal_gap"] - 6,
                expand=True,
            ),
            padding=self.config.ui["navigation_padding"],
            expand=True,
        )

    def _compose_footnote(self) -> ft.Container:
        """Cria a citacao exibida no rodape da barra lateral."""
        return ft.Container(
            content=ft.Text(
                value=self.config.texts["messages"]["placeholder_citation"],
                size=(
                    self.config.font_sizes["cormorant_small"]
                    * self.scale
                ),
                color=self.config.colors["muted"],
                font_family=self.config.font_families["cormorant"],
                align=ft.Alignment.CENTER_LEFT,
                text_align=ft.TextAlign.JUSTIFY,
                no_wrap=False,
                expand=True,
                weight=self.config.font_weights["cormorant_semibold"],
            ),
            height=self.config.ui["sidebar_footnote_height"] * self.scale,
            padding=self.config.ui["navigation_padding"],
            border=ft.Border(
                top=ft.BorderSide(1, self.config.colors["border"])
            ),
        )

    def compose(self) -> ft.Container:
        """Monta a barra lateral completa."""
        return ft.Container(
            width=self.config.ui["sidebar_width"],
            bgcolor=self.config.colors["surface"],
            border=ft.Border(
                right=ft.BorderSide(1, self.config.colors["border"])
            ),
            content=ft.Column(
                controls=[
                    self._compose_branding(),
                    self._compose_navigation(),
                    self._compose_footnote(),
                ],
                spacing=self.config.ui["modal_gap"] - 10,
                alignment=ft.MainAxisAlignment.START,
                expand=True,
            ),
        )
