"""Composer da tela de configurações da aplicação."""

from collections.abc import Callable
from typing import Any

import flet as ft

from src.services.cloud_sync_service import CloudSyncService
from src.utils.types import ViewConfig
from src.views.settings_cloud import SettingsCloudMixin
from src.views.settings_preview import SettingsPreviewMixin
from src.views.settings_scale import SettingsScaleMixin
from src.views.settings_theme import SettingsThemeMixin


class SettingsComposer(
    SettingsThemeMixin,
    SettingsScaleMixin,
    SettingsPreviewMixin,
    SettingsCloudMixin,
):
    """Compõe a interface visual do painel de Configurações."""

    def __init__(
        self,
        scale: float,
        config: ViewConfig,
        current_theme_mode: str,
        auto_scale: bool,
        manual_scale: float,
        effective_scale: float,
        on_navigate: Callable[[str], None],
        on_change_theme: Callable[[str], None],
        on_toggle_auto_scale: Callable[[bool], None],
        on_change_scale: Callable[[float], None],
        on_reset_settings: Callable[[], None],
        cloud_sync_service: Any = None,
        page: ft.Page | None = None,
    ) -> None:
        self.scale = scale
        self.config = config
        self.current_theme_mode = current_theme_mode
        self.auto_scale = auto_scale
        self.manual_scale = manual_scale
        self.effective_scale = effective_scale
        self.on_navigate = on_navigate
        self.on_change_theme = on_change_theme
        self.on_toggle_auto_scale = on_toggle_auto_scale
        self.on_change_scale = on_change_scale
        self.on_reset_settings = on_reset_settings
        self.cloud_sync_service = cloud_sync_service or CloudSyncService()
        self.page = page

        self.settings_texts = self.config.texts.get("settings", {})
        self.scale_value_text: ft.Text | None = None
        self.scale_slider: ft.Slider | None = None

    def _compose_header(self) -> ft.Container:
        """Cria o cabeçalho padronizado da tela de configurações."""
        title = self.settings_texts.get("title", "Configurações")
        subtitle = self.settings_texts.get(
            "subtitle",
            "Personalize a aparência, tema e proporções visuais do gabinete.",
        )
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                value=title,
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
                                value=subtitle,
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

    def _compose_card_container(
        self,
        icon: ft.IconData,
        title: str,
        subtitle: str,
        content: ft.Control,
    ) -> ft.Container:
        """Estrutura base estilizada para os cards de configuração."""
        card_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            icon,
                            color=self.config.colors["gold"],
                            size=26,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    value=title,
                                    font_family=self.config.font_families[
                                        "cormorant"
                                    ],
                                    weight=self.config.font_weights[
                                        "cormorant_semibold"
                                    ],
                                    size=self.config.font_sizes[
                                        "cormorant_large"
                                    ],
                                    color=self.config.colors["text"],
                                ),
                                ft.Text(
                                    value=subtitle,
                                    font_family=self.config.font_families[
                                        "montserrat"
                                    ],
                                    weight=self.config.font_weights[
                                        "montserrat_normal"
                                    ],
                                    size=self.config.font_sizes[
                                        "montserrat_micro"
                                    ],
                                    color=self.config.colors["muted"],
                                ),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(
                    color=self.config.colors["border"],
                    height=20,
                    thickness=1,
                ),
                content,
            ],
            spacing=10,
        )

        return ft.Container(
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=ft.BorderRadius.all(
                self.config.ui.get("card_radius", 6)
            ),
            padding=22,
            content=card_content,
        )

    def _compose_cards(self) -> ft.ResponsiveRow:
        """Gera a grade responsiva contendo os cards de configuração."""
        cards: list[ft.Control] = [
            ft.Container(
                content=self._compose_theme_card(),
                col={"xs": 12, "sm": 12, "md": 6, "lg": 6},
            ),
            ft.Container(
                content=self._compose_scale_card(),
                col={"xs": 12, "sm": 12, "md": 6, "lg": 6},
            ),
            ft.Container(
                content=self._compose_preview_card(),
                col={"xs": 12, "sm": 12, "md": 6, "lg": 6},
            ),
            ft.Container(
                content=self._compose_cloud_sync_card(),
                col={"xs": 12, "sm": 12, "md": 6, "lg": 6},
            ),
        ]

        return ft.ResponsiveRow(
            controls=cards,
            spacing=self.config.ui["grid_gap"],
            run_spacing=self.config.ui["grid_gap"],
        )

    def compose(self) -> ft.Container:
        """Monta a visualização completa do painel de configurações."""
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
                        content=ft.Column(
                            controls=[self._compose_cards()],
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        ),
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
