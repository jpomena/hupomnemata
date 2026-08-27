"""Composer da area principal do dashboard."""
import flet as ft

from collections.abc import Callable
from src.utils import ControlsUtils, ViewConfig
from src.utils.ft_icons import get_icon


class DashboardComposer:
    """Compoe o cabecalho e o conteudo principal do acervo."""

    def __init__(
        self,
        scale: float,
        config: ViewConfig,
        on_navigate: Callable[[str], None],
    ):
        self.scale = scale
        self.config = config
        self.on_navigate = on_navigate

    def _compose_header(self) -> ft.Container:
        """Cria o cabecalho e sua acao de insercao."""

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                value=self.config.texts["app"][
                                    "main_view_title"
                                ],
                                weight=self.config.font_weights[
                                    "cormorant_semibold"
                                ],
                                color=self.config.colors["text"],
                                font_family=self.config.font_families[
                                    "cormorant"
                                ],
                                size=self.config.font_sizes["cormorant_big"],
                            ),
                            ft.Text(
                                value=self.config.texts["app"][
                                    "main_view_subtitle"
                                ],
                                weight=self.config.font_weights[
                                    "montserrat_semibold"
                                ],
                                color=self.config.colors["muted"],
                                font_family=self.config.font_families[
                                    "montserrat"
                                ],
                                size=self.config.font_sizes["montserrat_tiny"],
                            ),
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.CENTER,
                    )
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

        def open_insert_modal(e):
            self.on_navigate("work_insert")

        on_click_dict = {
            "work_insert": open_insert_modal
        }

        cards: list[ft.Control] = [
            ft.Container(
                content=ControlsUtils.create_main_view_card(
                    config=self.config,
                    label_str=title,
                    icon_data=get_icon(data["icon"], ft.Icons.HELP_OUTLINE),
                    description_str=data["description"],
                    scale=self.scale,
                    on_click=on_click_dict[data['on_click']]
                    if 'on_click' in data else None
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
