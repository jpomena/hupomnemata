"""SettingsThemeMixin extraído de ``settings.py``.

Movimentação literal: métodos sem ``__init__``, colaborando com
``SettingsComposer`` via ``self``.
"""

import flet as ft

from src.views.ui_kit import MOTION_BASE, motion


class SettingsThemeMixin:
    """Card de tema da tela de Configurações."""

    def _compose_theme_option(
        self,
        key: str,
        label: str,
        icon: ft.IconData,
    ) -> ft.Container:
        """Cria um botão/card de seleção de tema com destaque ativo."""
        is_active = self.current_theme_mode == key
        border_color = (
            self.config.colors["gold"]
            if is_active
            else self.config.colors["border"]
        )
        bg_color = (
            self.config.colors["card_hover"]
            if is_active
            else self.config.colors["surface"]
        )
        icon_color = (
            self.config.colors["gold"]
            if is_active
            else self.config.colors["muted"]
        )
        text_color = (
            self.config.colors["text"]
            if is_active
            else self.config.colors["muted"]
        )

        container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(icon, color=icon_color, size=24),
                    ft.Text(
                        value=label,
                        color=text_color,
                        font_family=self.config.font_families["montserrat"],
                        weight=self.config.font_weights["montserrat_semibold"],
                        size=self.config.font_sizes["montserrat_tiny"],
                    ),
                    ft.Text(
                        value="(Ativo)" if is_active else "",
                        color=self.config.colors["gold"],
                        font_family=self.config.font_families["montserrat"],
                        weight=self.config.font_weights["montserrat_bold"],
                        size=10,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            border=ft.Border.all(2 if is_active else 1, border_color),
            border_radius=ft.BorderRadius.all(
                self.config.ui.get("card_radius", 6)
            ),
            bgcolor=bg_color,
            padding=ft.Padding.symmetric(vertical=16, horizontal=8),
            expand=True,
            animate=motion(MOTION_BASE),
            animate_scale=motion(MOTION_BASE),
            on_click=lambda _: self.on_change_theme(key),
        )

        def handle_hover(event: ft.Event[ft.Container]) -> None:
            if is_active:
                return
            hovering = event.data in (True, "true")
            if hovering:
                container.bgcolor = self.config.colors["card_hover"]
                container.border = ft.Border.all(
                    1, self.config.colors["text"]
                )
            else:
                container.bgcolor = self.config.colors["surface"]
                container.border = ft.Border.all(
                    1, self.config.colors["border"]
                )
            container.scale = 1.01 if hovering else 1.0
            container.update()

        container.on_hover = handle_hover
        return container

    def _compose_theme_card(self) -> ft.Container:
        """Card de seleção de tema (Claro, Escuro e Seguir Sistema)."""
        options_row = ft.Row(
            controls=[
                self._compose_theme_option(
                    key="light",
                    label=self.settings_texts.get("theme_light", "Claro"),
                    icon=ft.Icons.LIGHT_MODE_OUTLINED,
                ),
                self._compose_theme_option(
                    key="dark",
                    label=self.settings_texts.get("theme_dark", "Escuro"),
                    icon=ft.Icons.DARK_MODE_OUTLINED,
                ),
                self._compose_theme_option(
                    key="system",
                    label=self.settings_texts.get("theme_system", "Sistema"),
                    icon=ft.Icons.SETTINGS_BRIGHTNESS_OUTLINED,
                ),
            ],
            spacing=10,
        )

        theme_info = ft.Text(
            value=(
                "A paleta de cores altera imediatamente os menus laterais, "
                "cartões, formulários e diálogos do aplicativo."
            ),
            font_family=self.config.font_families["montserrat"],
            weight=self.config.font_weights["montserrat_normal"],
            size=self.config.font_sizes["montserrat_micro"],
            color=self.config.colors["muted"],
        )

        content = ft.Column(
            controls=[options_row, theme_info],
            spacing=14,
        )

        return self._compose_card_container(
            icon=ft.Icons.PALETTE_OUTLINED,
            title=self.settings_texts.get("theme_title", "Tema da Interface"),
            subtitle=self.settings_texts.get(
                "theme_subtitle",
                "Alterne entre a paleta escura, clara ou acompanhe o sistema.",
            ),
            content=content,
        )
