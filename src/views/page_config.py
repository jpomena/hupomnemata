"""Configuracao visual e de janela da pagina Flet."""

import flet as ft
from src.utils.types import ViewConfig


class PageConfigurator:
    """Aplica as configuracoes visuais fornecidas a uma pagina Flet."""

    def __init__(
        self,
        config: ViewConfig,
    ):
        self.config = config

    def configure_page(self, page: ft.Page) -> None:
        """Aplica fontes, tema, titulo e dimensoes da janela."""
        page.fonts = self.config.page_fonts
        page.theme = ft.Theme(
            font_family=self.config.font_families["cormorant"],
            tooltip_theme=ft.TooltipTheme(
                text_style=(
                    ft.TextStyle(
                        font_family=self.config.font_families["montserrat"]
                    )
                )
            )
        )
        page.title = (
            f"{self.config.texts['app']['name']} "
            f"{self.config.texts['app']['version']}"
        )
        page.padding = 0
        page.window.width = 1350
        page.window.height = 870
        page.window.resizable = True
        page.window.frameless = True
        page.window.title_bar_hidden = True
        page.window.title_bar_buttons_hidden = True
        page.window.maximizable = True
        page.window.minimizable = True
        page.window.prevent_close = False
