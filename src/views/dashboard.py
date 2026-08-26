"""Composer da area principal do dashboard."""

from collections.abc import Callable

import flet as ft

from src.utils.ft_controls import ControlsUtils
from src.utils.ft_icons import get_icon
from src.views.view_config import ViewConfig


class DashboardComposer:
    """Compoe o cabecalho e o conteudo principal do acervo."""

    def __init__(
        self,
        scale: float,
        config: ViewConfig,
        on_insert_work: Callable[[], None],
    ):
        self.scale = scale
        self.config = config
        self.on_insert_work = on_insert_work

    def _compose_header(self) -> ft.Container:
        """Cria o cabecalho e sua acao de insercao."""

        def open_insert_modal(e):
            self.on_insert_work()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                value=self.config.texts["app"][
                                    "main_view_title"
                                ],
                                weight=self.config.font_weight["semibold"],
                                color=self.config.colors["text"],
                                font_family=self.config.fonts["cormorant"],
                                size=self.config.font_size["page_title"],
                            ),
                            ft.Text(
                                value=self.config.texts["app"][
                                    "main_view_subtitle"
                                ],
                                weight=self.config.font_weight["semibold"],
                                color=self.config.colors["muted"],
                                font_family=self.config.fonts["montserrat"],
                                size=self.config.font_size["page_subtitle"],
                            ),
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.ElevatedButton(
                        content=ft.Text(
                            value="+ Inserir Nova Obra",
                            weight=self.config.font_weight["semibold"],
                            font_family=self.config.fonts["montserrat"],
                            color=self.config.colors["text"],
                            size=self.config.font_size["action"],
                            style=ft.TextStyle(letter_spacing=2),
                        ),
                        bgcolor=self.config.colors["gold"],
                        on_click=open_insert_modal,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(
                left=self.config.ui["header_horizontal_padding"],
                right=self.config.ui["header_horizontal_padding"],
                top=self.config.ui["header_top_padding"],
                bottom=self.config.ui["header_bottom_padding"],
            ),
        )

    def _compose_cards(self) -> ft.ResponsiveRow:
        """Cria a grade responsiva de atalhos do acervo."""
        cards: list[ft.Control] = [
            ft.Container(
                content=ControlsUtils.create_main_view_card(
                    config=self.config,
                    label_str=title,
                    icon_data=get_icon(data["icon"], ft.Icons.HELP_OUTLINE),
                    description_str=data["description"],
                    scale=self.scale,
                ),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 3},
            )
            for title, data in self.config.main_view_cards.items()
        ]
        return ft.ResponsiveRow(
            controls=cards,
            spacing=self.config.ui["grid_gap"],
            run_spacing=self.config.ui["grid_gap"],
        )

    def compose(self) -> ft.Container:
        """Monta a area de conteudo que ocupa o lado principal."""
        return ft.Container(
            expand=True,
            padding=ft.Padding(
                top=self.config.ui["content_top_padding"],
                right=0,
                bottom=0,
                left=0,
            ),
            bgcolor=self.config.colors["surface"],
            content=ft.Column(
                controls=[
                    self._compose_header(),
                    ft.Container(
                        content=self._compose_cards(),
                        border=ft.Border(
                            top=ft.BorderSide(1, self.config.colors["border"])
                        ),
                        padding=self.config.ui["content_padding"],
                        expand=True,
                        bgcolor=self.config.colors["bg"],
                    ),
                ],
                spacing=self.config.ui["modal_gap"],
                expand=True,
            ),
        )
