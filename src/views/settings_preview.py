"""SettingsPreviewMixin extraído de ``settings.py``.

Movimentação literal: métodos sem ``__init__``, colaborando com
``SettingsComposer`` via ``self``.
"""

import flet as ft


class SettingsPreviewMixin:
    """Card de amostra visual e restauração de padrões."""

    def _compose_preview_card(self) -> ft.Container:
        """Card com amostra tipográfica da paleta e ação de restaurar padrões."""
        palette_indicators = ft.Row(
            controls=[
                self._palette_chip("Dourado", self.config.colors["gold"]),
                self._palette_chip("Texto", self.config.colors["text"]),
                self._palette_chip("Superfície", self.config.colors["surface"]),
                self._palette_chip("Borda", self.config.colors["border"]),
                self._palette_chip("Fundo", self.config.colors["bg"]),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
        )

        preview_box = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value="Hupomnēmata: A escrita de si",
                        font_family=self.config.font_families["cormorant"],
                        weight=self.config.font_weights["cormorant_semibold"],
                        size=self.config.font_sizes["cormorant_medium"],
                        color=self.config.colors["gold"],
                    ),
                    ft.Text(
                        value="hupomnemata",
                        font_family=self.config.font_families["greek"],
                        weight=self.config.font_weights["greek_semibold"],
                        size=14,
                        color=self.config.colors["text"],
                    ),
                    ft.Text(
                        value=(
                            "Espaço de guarda, rigor intelectual e reunião do já dito. "
                            "Tipografia e contrastes afinados para longas sessões de leitura."
                        ),
                        font_family=self.config.font_families["montserrat"],
                        weight=self.config.font_weights["montserrat_normal"],
                        size=self.config.font_sizes["montserrat_micro"],
                        color=self.config.colors["muted"],
                    ),
                    palette_indicators,
                ],
                spacing=8,
            ),
            bgcolor=self.config.colors["bg"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=ft.BorderRadius.all(
                self.config.ui.get("card_radius", 6)
            ),
            padding=14,
        )

        reset_button = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.RESTART_ALT_OUTLINED,
                        color=self.config.colors["gold"],
                        size=18,
                    ),
                    ft.Text(
                        value=self.settings_texts.get(
                            "reset_button", "Restaurar Padrões"
                        ),
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["montserrat"],
                        weight=self.config.font_weights[
                            "montserrat_semibold"
                        ],
                        size=self.config.font_sizes["montserrat_small"],
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, self.config.colors["border"]),
                shape=ft.RoundedRectangleBorder(
                    radius=self.config.ui.get("card_radius", 6)
                ),
                bgcolor=self.config.colors["surface"],
                padding=ft.Padding.symmetric(vertical=14, horizontal=16),
            ),
            on_click=lambda _: self.on_reset_settings(),
        )

        content = ft.Column(
            controls=[
                preview_box,
                ft.Divider(
                    color=self.config.colors["border"],
                    height=14,
                    thickness=1,
                ),
                reset_button,
            ],
            spacing=10,
        )

        return self._compose_card_container(
            icon=ft.Icons.AUTO_AWESOME_OUTLINED,
            title=self.settings_texts.get(
                "preview_title", "Amostra Visual & Padrões"
            ),
            subtitle=self.settings_texts.get(
                "preview_subtitle",
                "Pré-visualize a tipografia ativa ou restaure os valores originais.",
            ),
            content=content,
        )

    def _palette_chip(self, label: str, color_hex: str) -> ft.Container:
        """Pequena amostra de cor com indicador e tooltip."""
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=12,
                        height=12,
                        bgcolor=color_hex,
                        border_radius=ft.BorderRadius.all(6),
                        border=ft.Border.all(
                            1, self.config.colors["border"]
                        ),
                    ),
                    ft.Text(
                        value=label,
                        font_family=self.config.font_families["montserrat"],
                        size=10,
                        color=self.config.colors["muted"],
                    ),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            tooltip=f"{label}: {color_hex}",
        )
