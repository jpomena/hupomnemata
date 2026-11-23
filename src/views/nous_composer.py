"""Compositor da visão 'Nous' (Inteligência Artificial & Cognição).
Apresenta configuração BYOK (Google Gemini), tutorial didático passo a passo,
gestão de sínteses epistemológicas e enriquecimento das obras do acervo.
"""

from collections.abc import Callable
from typing import Any, Dict, List, Optional
import flet as ft

from src.services.nous_service import NousAIService
from src.utils.types import ViewConfig
from src.views.nous import byok as _byok
from src.views.nous import acervo as _acervo
from src.views.nous import works as _works
from src.views.nous import generation as _generation
from src.views.nous import override as _override


class NousComposer:
    """Compositor da tela Nous: BYOK, conexão com Gemini e orquestração de IA."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        scale: float,
        on_navigate: Callable[[str], None],
        nous_service: Optional[NousAIService] = None,
        current_theme_mode: str = "light",
    ) -> None:
        self.page = page
        self.config = config
        self.scale = scale
        self.on_navigate = on_navigate
        self.nous_service = nous_service or NousAIService()
        self.current_theme_mode = current_theme_mode

        self.works_data: List[Dict[str, Any]] = []
        self.active_tab_index = 0
        self.is_batch_running = False
        self.generating_work_ids: set[int] = set()
        self.work_actions_containers: Dict[int, ft.Container] = {}
        self.work_snippet_texts: Dict[int, ft.Text] = {}
        self.work_badge_containers: Dict[int, ft.Container] = {}

        # Status de conexão inicial
        stored_key = self.nous_service.get_api_key()
        self.has_key = bool(stored_key)

        # Controles BYOK
        self.api_key_field = ft.TextField(
            value=stored_key,
            label="Chave de API do Google Gemini",
            hint_text="Cole sua chave aqui (ex: AIzaSy...)",
            password=True,
            can_reveal_password=True,
            width=500 * self.scale,
            height=46 * self.scale,
            text_size=12 * self.scale,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["surface"],
        )

        self.last_scroll_offset = 0.0
        self.metrics_row = None

        self.status_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE_OUTLINE if self.has_key else ft.Icons.KEY_OFF_OUTLINED,
            size=13 * self.scale,
            color=self.config.colors["gold"] if self.has_key else self.config.colors["muted"],
        )
        self.status_chip_text = ft.Text(
            "Conexão Ativa" if self.has_key else "Chave Não Configurada",
            size=11 * self.scale,
            weight=ft.FontWeight.W_600,
            font_family=self.config.font_families["montserrat"],
            color=self.config.colors["gold"] if self.has_key else self.config.colors["muted"],
        )

        self.status_chip = ft.Container(
            content=ft.Row(
                controls=[
                    self.status_icon,
                    self.status_chip_text,
                ],
                spacing=6 * self.scale,
                tight=True,
            ),
            border=ft.Border.all(1, self.config.colors["gold"] if self.has_key else self.config.colors["border"]),
            bgcolor=self.config.colors["surface"],
            border_radius=6,
            padding=ft.Padding(10 * self.scale, 5 * self.scale, 10 * self.scale, 5 * self.scale),
        )

        self.status_feedback = ft.Text(
            "",
            size=12 * self.scale,
            font_family=self.config.font_families["montserrat"],
            color=self.config.colors["muted"],
        )

        # Progresso em lote
        self.batch_progress_bar = ft.ProgressBar(
            value=0.0,
            visible=False,
            color=self.config.colors["gold"],
            bgcolor=self.config.colors["border"],
            height=4 * self.scale,
        )

        self.batch_progress_text = ft.Text(
            "",
            size=12 * self.scale,
            font_family=self.config.font_families["montserrat"],
            visible=False,
            color=self.config.colors["muted"],
        )

        # Lista de obras
        self.works_column = ft.Column(spacing=10 * self.scale, tight=True)
        self.search_filter = ft.TextField(
            hint_text="Filtrar obras por título ou autor...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._handle_search_filter,
            border_radius=8,
            height=38 * self.scale,
            text_size=13 * self.scale,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["surface"],
            width=360 * self.scale,
            content_padding=ft.Padding(10, 0, 10, 0),
        )

        # Contadores de métricas
        self.stat_total = ft.Text("0", size=24 * self.scale, font_family=self.config.font_families["cormorant"], weight=ft.FontWeight.W_700, color=self.config.colors["text"])
        self.stat_with_ai = ft.Text("0", size=24 * self.scale, font_family=self.config.font_families["cormorant"], weight=ft.FontWeight.W_700, color=self.config.colors["gold"])
        self.stat_custom = ft.Text("0", size=24 * self.scale, font_family=self.config.font_families["cormorant"], weight=ft.FontWeight.W_700, color=self.config.colors["muted"])
        self.stat_pending = ft.Text("0", size=24 * self.scale, font_family=self.config.font_families["cormorant"], weight=ft.FontWeight.W_700, color=self.config.colors["muted"])

    def compose(self) -> ft.Control:
        """Monta e retorna a visão completa do Menu Nous."""
        self._refresh_works_data()

        header = ft.Container(
            bgcolor=self.config.colors["surface"],
            border=ft.Border(bottom=ft.BorderSide(1, self.config.colors["border"])),
            padding=ft.Padding.only(
                left=self.config.ui["header_horizontal_padding"] * self.scale,
                right=self.config.ui["header_horizontal_padding"] * self.scale,
                top=self.config.ui["header_top_padding"] * self.scale,
                bottom=self.config.ui["header_bottom_padding"] * self.scale,
            ),
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Nous — Cognição & Inteligência Artificial",
                                size=self.config.font_sizes["cormorant_big"] * self.scale,
                                font_family=self.config.font_families["cormorant"],
                                weight=self.config.font_weights["cormorant_semibold"],
                                color=self.config.colors["text"],
                            ),
                            ft.Text(
                                "Integração BYOK (Google Gemini) e síntese conceitual do acervo para a Constelação 3D.",
                                size=self.config.font_sizes["montserrat_tiny"] * self.scale,
                                font_family=self.config.font_families["montserrat"],
                                weight=self.config.font_weights["montserrat_semibold"],
                                color=self.config.colors["muted"],
                            ),
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.CENTER,
                        tight=True,
                    ),
                    self.status_chip,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        self.scroll_column = ft.Column(
            key="nous_scroll_column",
            controls=[
                self._build_byok_card(),
                ft.Container(height=12 * self.scale),
                self._build_acervo_management_card(),
            ],
            scroll=ft.ScrollMode.ADAPTIVE,
            spacing=16 * self.scale,
            on_scroll=self._on_scroll_change,
        )

        body_content = ft.Container(
            expand=True,
            padding=ft.Padding(24 * self.scale, 20 * self.scale, 24 * self.scale, 20 * self.scale),
            content=self.scroll_column,
        )

        return ft.Container(
            expand=True,
            bgcolor=self.config.colors["bg"],
            content=ft.Column(
                controls=[header, body_content],
                expand=True,
                spacing=0,
            ),
        )

    def _on_scroll_change(self, e: ft.OnScrollEvent) -> None:
        """Rastreia o deslocamento vertical do scroll para preservação de posição."""
        if hasattr(e, "extent_before") and e.extent_before is not None:
            self.last_scroll_offset = float(e.extent_before)

    def _build_byok_card(self) -> ft.Control:
        return _byok.build_byok_card(self)

    def _build_acervo_management_card(self) -> ft.Control:
        return _acervo.build_acervo_management_card(self)

    def _metric_chip(self, label: str, value_ctrl: ft.Text, accent_color: str) -> ft.Control:
        return _acervo.metric_chip(self, label, value_ctrl, accent_color)

    def _refresh_works_data(self) -> None:
        _acervo.refresh_works_data(self)

    def _build_work_actions(self, w: Dict[str, Any]) -> ft.Control:
        return _works.build_work_actions(self, w)

    def _render_works_list(self, items: List[Dict[str, Any]]) -> None:
        _works.render_works_list(self, items)

    def _handle_open_ai_studio(self, _e: ft.ControlEvent) -> None:
        _byok.handle_open_ai_studio(self, _e)

    def _get_error_colors(self) -> tuple[str, str]:
        return _byok.get_error_colors(self)

    def _handle_save_and_test_key(self, _e: ft.ControlEvent) -> None:
        _byok.handle_save_and_test_key(self, _e)

    def _update_single_work_ui(self, work_id: int) -> None:
        _works.update_single_work_ui(self, work_id)

    def _handle_single_generate(self, work_id: int) -> None:
        _generation.handle_single_generate(self, work_id)

    def _handle_batch_generation(self, _e: ft.ControlEvent) -> None:
        _generation.handle_batch_generation(self, _e)

    def _open_override_dialog(self, work_item: Dict[str, Any]) -> None:
        _override.open_override_dialog(self, work_item)

    def _handle_search_filter(self, _e: ft.ControlEvent) -> None:
        _works.handle_search_filter(self, _e)
