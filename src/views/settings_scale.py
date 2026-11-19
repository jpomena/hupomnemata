"""SettingsScaleMixin extraído de ``settings.py``.

Movimentação literal: métodos sem ``__init__``, colaborando com
``SettingsComposer`` via ``self``.
"""

import flet as ft


class SettingsScaleMixin:
    """Card de escala e proporções da tela de Configurações."""

    def _compose_scale_card(self) -> ft.Container:
        """Card de ajuste de escala e responsividade."""
        def on_switch_change(event: ft.Event[ft.Switch]) -> None:
            self.on_toggle_auto_scale(bool(event.control.value))

        def on_slider_change(event: ft.Event[ft.Slider]) -> None:
            if self.scale_value_text is not None:
                new_val = int(round(float(event.control.value) * 100))
                self.scale_value_text.value = f"{new_val}%"
                self.scale_value_text.update()

        def on_slider_change_end(event: ft.Event[ft.Slider]) -> None:
            self.on_change_scale(round(float(event.control.value), 2))

        auto_switch = ft.Switch(
            value=self.auto_scale,
            active_color=self.config.colors["gold"],
            on_change=on_switch_change,
        )

        auto_row = ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text(
                            value=self.settings_texts.get(
                                "auto_scale_label", "Escala Automática"
                            ),
                            font_family=self.config.font_families["montserrat"],
                            weight=self.config.font_weights[
                                "montserrat_semibold"
                            ],
                            size=self.config.font_sizes["montserrat_small"],
                            color=self.config.colors["text"],
                        ),
                        ft.Text(
                            value=self.settings_texts.get(
                                "auto_scale_description",
                                "Recalcular proporções dinamicamente conforme a janela é redimensionada.",
                            ),
                            font_family=self.config.font_families["montserrat"],
                            weight=self.config.font_weights["montserrat_normal"],
                            size=self.config.font_sizes["montserrat_micro"],
                            color=self.config.colors["muted"],
                            no_wrap=False,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                auto_switch,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        display_percent = int(
            round(
                (self.effective_scale if self.auto_scale else self.manual_scale)
                * 100
            )
        )
        badge_text = (
            f"{display_percent}% (Automático)"
            if self.auto_scale
            else f"{display_percent}%"
        )

        self.scale_value_text = ft.Text(
            value=badge_text,
            font_family=self.config.font_families["montserrat"],
            weight=self.config.font_weights["montserrat_semibold"],
            size=12,
            color=self.config.colors["gold"],
        )

        badge_container = ft.Container(
            content=self.scale_value_text,
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=ft.BorderRadius.all(4),
            bgcolor=self.config.colors["surface"],
        )

        slider_header = ft.Row(
            controls=[
                ft.Text(
                    value=self.settings_texts.get(
                        "manual_scale_label", "Zoom Manual da UI"
                    ),
                    font_family=self.config.font_families["montserrat"],
                    weight=self.config.font_weights["montserrat_semibold"],
                    size=self.config.font_sizes["montserrat_small"],
                    color=(
                        self.config.colors["muted"]
                        if self.auto_scale
                        else self.config.colors["text"]
                    ),
                ),
                badge_container,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.scale_slider = ft.Slider(
            min=0.80,
            max=1.40,
            divisions=12,
            value=self.manual_scale,
            active_color=self.config.colors["gold"],
            inactive_color=self.config.colors["border"],
            disabled=self.auto_scale,
            on_change=on_slider_change,
            on_change_end=on_slider_change_end,
        )

        slider_hint = ft.Text(
            value=(
                "Ajuste manual suspenso enquanto a escala automática estiver ativa."
                if self.auto_scale
                else "Arraste o marcador para ajustar o zoom geral da interface (80% a 140%)."
            ),
            font_family=self.config.font_families["montserrat"],
            weight=self.config.font_weights["montserrat_normal"],
            size=self.config.font_sizes["montserrat_micro"],
            color=self.config.colors["muted"],
            italic=self.auto_scale,
        )

        content = ft.Column(
            controls=[
                auto_row,
                ft.Divider(
                    color=self.config.colors["border"],
                    height=14,
                    thickness=1,
                ),
                slider_header,
                self.scale_slider,
                slider_hint,
            ],
            spacing=8,
        )

        return self._compose_card_container(
            icon=ft.Icons.ASPECT_RATIO_OUTLINED,
            title=self.settings_texts.get(
                "scale_title", "Escala e Proporções"
            ),
            subtitle=self.settings_texts.get(
                "scale_subtitle",
                "Ajuste o zoom dos elementos da interface de forma responsiva.",
            ),
            content=content,
        )
