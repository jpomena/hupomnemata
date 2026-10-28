"""Composer da tela de configurações da aplicação."""

from collections.abc import Callable
import flet as ft

from src.utils.types import ViewConfig


class SettingsComposer:
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
            on_click=lambda _: self.on_change_theme(key),
        )

        def handle_hover(event: ft.Event[ft.Container]) -> None:
            if is_active:
                return
            if event.data == "true":
                container.bgcolor = self.config.colors["card_hover"]
                container.border = ft.Border.all(
                    1, self.config.colors["text"]
                )
            else:
                container.bgcolor = self.config.colors["surface"]
                container.border = ft.Border.all(
                    1, self.config.colors["border"]
                )
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

    def _compose_cards(self) -> ft.ResponsiveRow:
        """Gera a grade responsiva contendo os cards de configuração."""
        cards: list[ft.Control] = [
            ft.Container(
                content=self._compose_theme_card(),
                col={"xs": 12, "sm": 12, "md": 6, "lg": 4},
            ),
            ft.Container(
                content=self._compose_scale_card(),
                col={"xs": 12, "sm": 12, "md": 6, "lg": 4},
            ),
            ft.Container(
                content=self._compose_preview_card(),
                col={"xs": 12, "sm": 12, "md": 12, "lg": 4},
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
