"""Compositor da visão 'Nous' (Inteligência Artificial & Cognição).
Apresenta configuração BYOK (Google Gemini), tutorial didático passo a passo,
gestão de sínteses epistemológicas e enriquecimento das obras do acervo.
"""

from collections.abc import Callable
import threading
from typing import Any, Dict, List, Optional
import webbrowser
import flet as ft

from src.services.nous_service import NousAIService
from src.utils.types import ViewConfig


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
            italic=True,
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
            size=11 * self.scale,
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
            text_size=12 * self.scale,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["surface"],
            width=360 * self.scale,
            content_padding=ft.Padding(10, 0, 10, 0),
        )

        # Contadores de métricas
        self.stat_total = ft.Text("0", size=18 * self.scale, weight=ft.FontWeight.W_700, color=self.config.colors["text"])
        self.stat_with_ai = ft.Text("0", size=18 * self.scale, weight=ft.FontWeight.W_700, color=self.config.colors["gold"])
        self.stat_custom = ft.Text("0", size=18 * self.scale, weight=ft.FontWeight.W_700, color="#5A6B7C")
        self.stat_pending = ft.Text("0", size=18 * self.scale, weight=ft.FontWeight.W_700, color=self.config.colors["muted"])

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
        """Card de configuração BYOK com instruções didáticas passo a passo."""
        tutorial_steps = ft.Container(
            bgcolor=f"{self.config.colors['bg']}",
            border=ft.Border(left=ft.BorderSide(3 * self.scale, self.config.colors["gold"])),
            border_radius=6,
            padding=14 * self.scale,
            content=ft.Column(
                controls=[
                    ft.Text(
                        "COMO OBTER SUA CHAVE GRATUITA DO GOOGLE GEMINI EM 3 PASSOS:",
                        size=11 * self.scale,
                        weight=ft.FontWeight.W_700,
                        color=self.config.colors["gold"],
                    ),
                    ft.Text(
                        "1. Acesse o portal oficial do Google AI Studio (aistudio.google.com/app/apikey). O uso do modelo Gemini 2.5 Flash é 100% gratuito e não exige cartão de crédito.",
                        size=12 * self.scale,
                        color=self.config.colors["text"],
                    ),
                    ft.Text(
                        "2. Faça login com sua conta Google e clique no botão azul 'Get API key' (ou 'Create API key') para gerar uma nova chave.",
                        size=12 * self.scale,
                        color=self.config.colors["text"],
                    ),
                    ft.Text(
                        "3. Copie a chave (começa com 'AIzaSy...'), cole no campo abaixo e clique em 'Salvar e Testar Conexão'. Sua chave é gravada localmente de forma privada.",
                        size=12 * self.scale,
                        color=self.config.colors["text"],
                    ),
                ],
                spacing=6 * self.scale,
                tight=True,
            ),
        )

        input_row = ft.Row(
            controls=[
                self.api_key_field,
                ft.FilledButton(
                    content="Salvar e Testar",
                    icon=ft.Icons.CHECK,
                    on_click=self._handle_save_and_test_key,
                    style=ft.ButtonStyle(
                        bgcolor=self.config.colors["gold"],
                        color="#FFFFFF",
                    ),
                ),
                ft.OutlinedButton(
                    content="Abrir AI Studio",
                    icon=ft.Icons.OPEN_IN_NEW,
                    on_click=self._handle_open_ai_studio,
                    style=ft.ButtonStyle(
                        color=self.config.colors["text"],
                        side=ft.BorderSide(1, self.config.colors["border"]),
                    ),
                ),
            ],
            spacing=10 * self.scale,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=10,
            padding=18 * self.scale,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.KEY, size=18 * self.scale, color=self.config.colors["gold"]),
                            ft.Text(
                                "Configuração BYOK (Bring Your Own Key)",
                                size=self.config.font_sizes["cormorant_medium"] * self.scale,
                                font_family=self.config.font_families["cormorant"],
                                weight=self.config.font_weights["cormorant_semibold"],
                                color=self.config.colors["gold"],
                            ),
                        ],
                        spacing=8 * self.scale,
                    ),
                    tutorial_steps,
                    input_row,
                    self.status_feedback,
                ],
                spacing=12 * self.scale,
                tight=True,
            ),
        )

    def _build_acervo_management_card(self) -> ft.Control:
        """Card de gestão de sínteses do acervo e processamento em lote."""
        self.metrics_row = ft.Row(
            controls=[
                self._metric_chip("Total de Obras", self.stat_total, self.config.colors["text"]),
                self._metric_chip("Com Síntese IA", self.stat_with_ai, self.config.colors["gold"]),
                self._metric_chip("Personalizadas", self.stat_custom, "#5A6B7C"),
                self._metric_chip("Pendentes", self.stat_pending, self.config.colors["muted"]),
            ],
            spacing=14 * self.scale,
        )

        batch_actions_row = ft.Row(
            controls=[
                self.search_filter,
                ft.FilledButton(
                    content="Gerar para Todas as Obras Pendentes",
                    icon=ft.Icons.BOLT,
                    on_click=self._handle_batch_generation,
                    style=ft.ButtonStyle(
                        bgcolor=self.config.colors["gold"],
                        color="#FFFFFF",
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        return ft.Container(
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=10,
            padding=18 * self.scale,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.AUTO_AWESOME, size=18 * self.scale, color=self.config.colors["gold"]),
                            ft.Text(
                                "Gestão de Síntese Epistemológica do Acervo",
                                size=self.config.font_sizes["cormorant_medium"] * self.scale,
                                font_family=self.config.font_families["cormorant"],
                                weight=self.config.font_weights["cormorant_semibold"],
                                color=self.config.colors["gold"],
                            ),
                        ],
                        spacing=8 * self.scale,
                    ),
                    ft.Text(
                        "As sínteses epistemológicas contextualizam as teses fundamentais de cada obra e "
                        "posicionam os nós na Constelação 3D. Você pode gerar com IA e sobrepor com suas próprias anotações a qualquer momento.",
                        size=12 * self.scale,
                        color=self.config.colors["muted"],
                    ),
                    self.metrics_row,
                    ft.Divider(color=self.config.colors["border"], height=10 * self.scale),
                    batch_actions_row,
                    self.batch_progress_bar,
                    self.batch_progress_text,
                    ft.Container(height=6 * self.scale),
                    self.works_column,
                ],
                spacing=12 * self.scale,
                tight=True,
            ),
        )

    def _metric_chip(self, label: str, value_ctrl: ft.Text, accent_color: str) -> ft.Control:
        return ft.Container(
            bgcolor=self.config.colors["bg"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=8,
            padding=ft.Padding(16 * self.scale, 10 * self.scale, 16 * self.scale, 10 * self.scale),
            content=ft.Column(
                controls=[
                    ft.Text(label.upper(), size=9 * self.scale, weight=ft.FontWeight.W_700, color=self.config.colors["muted"]),
                    value_ctrl,
                ],
                spacing=2 * self.scale,
                tight=True,
            ),
            expand=True,
        )

    def _refresh_works_data(self) -> None:
        """Carrega todas as obras do banco e calcula métricas de IA."""
        self.works_data = self.nous_service.list_works_ai_status()

        total = len(self.works_data)
        with_ai = sum(1 for w in self.works_data if w["has_llm"] and not w["has_custom"])
        custom = sum(1 for w in self.works_data if w["has_custom"])
        pending = sum(1 for w in self.works_data if not w["has_llm"] and not w["has_custom"])

        self.stat_total.value = str(total)
        self.stat_with_ai.value = str(with_ai)
        self.stat_custom.value = str(custom)
        self.stat_pending.value = str(pending)

        self._render_works_list(self.works_data)

    def _build_work_actions(self, w: Dict[str, Any]) -> ft.Control:
        w_id = w["id"]
        is_generating = w_id in self.generating_work_ids
        if is_generating:
            return ft.Container(
                bgcolor=self.config.colors["surface"],
                border=ft.Border.all(1, self.config.colors["border"]),
                border_radius=6,
                padding=ft.Padding(12 * self.scale, 8 * self.scale, 12 * self.scale, 8 * self.scale),
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.AUTO_AWESOME,
                                    size=14 * self.scale,
                                    color=self.config.colors["gold"],
                                ),
                                ft.Text(
                                    "Consultando Nous... gerando síntese conceitual",
                                    size=11 * self.scale,
                                    weight=ft.FontWeight.W_600,
                                    color=self.config.colors["text"],
                                ),
                            ],
                            spacing=6 * self.scale,
                            tight=True,
                        ),
                        ft.ProgressBar(
                            color=self.config.colors["gold"],
                            bgcolor=self.config.colors["border"],
                            height=4 * self.scale,
                        ),
                    ],
                    spacing=6 * self.scale,
                    tight=True,
                ),
            )
        return ft.Row(
            controls=[
                ft.FilledButton(
                    content="Gerar com Nous",
                    icon=ft.Icons.BOLT,
                    on_click=lambda _, wid=w_id: self._handle_single_generate(wid),
                    style=ft.ButtonStyle(
                        bgcolor=self.config.colors["gold"],
                        color="#FFFFFF",
                    ),
                ),
                ft.OutlinedButton(
                    content="Sobrepor / Editar",
                    icon=ft.Icons.EDIT_NOTE,
                    on_click=lambda _, work_item=w: self._open_override_dialog(work_item),
                    style=ft.ButtonStyle(
                        color=self.config.colors["text"],
                        side=ft.BorderSide(1, self.config.colors["border"]),
                    ),
                ),
            ],
            spacing=8 * self.scale,
        )

    def _render_works_list(self, items: List[Dict[str, Any]]) -> None:
        """Renderiza cartões de obras com opções de geração de IA e sobreposição."""
        self.works_column.controls.clear()
        self.work_actions_containers.clear()
        self.work_snippet_texts.clear()
        self.work_badge_containers.clear()

        if not items:
            self.works_column.controls.append(
                ft.Container(
                    alignment=ft.Alignment(0, 0),
                    padding=20 * self.scale,
                    content=ft.Text(
                        "Nenhuma obra encontrada no acervo.",
                        size=12 * self.scale,
                        color=self.config.colors["muted"],
                    ),
                )
            )
            return

        for w in items:
            w_id = w["id"]
            title = w["title"]
            authors = w["authors"]
            year = w["year"]
            status_label = w["status_label"]
            status_color = w["status_color"]
            snippet = w["snippet"] or "Sem síntese cadastrada."

            status_badge = ft.Container(
                content=ft.Text(status_label.upper(), size=9 * self.scale, weight=ft.FontWeight.W_700, color=status_color),
                bgcolor=self.config.colors["surface"],
                border=ft.Border.all(1, status_color),
                border_radius=4,
                padding=ft.Padding(8 * self.scale, 3 * self.scale, 8 * self.scale, 3 * self.scale),
            )
            self.work_badge_containers[w_id] = status_badge

            actions_box = ft.Container(
                content=self._build_work_actions(w),
            )
            self.work_actions_containers[w_id] = actions_box

            snippet_text = ft.Text(
                snippet,
                size=12 * self.scale,
                italic=True,
                font_family=self.config.font_families["cormorant"],
                color=self.config.colors["text"],
            )
            self.work_snippet_texts[w_id] = snippet_text

            snippet_box = ft.Container(
                bgcolor=self.config.colors["surface"],
                border=ft.Border(left=ft.BorderSide(2 * self.scale, status_color)),
                border_radius=4,
                padding=8 * self.scale,
                content=snippet_text,
            )

            card = ft.Container(
                bgcolor=self.config.colors["bg"],
                border=ft.Border.all(1, self.config.colors["border"]),
                border_radius=8,
                padding=12 * self.scale,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            title,
                                            size=14 * self.scale,
                                            font_family=self.config.font_families["cormorant"],
                                            weight=self.config.font_weights["cormorant_semibold"],
                                            color=self.config.colors["gold"],
                                        ),
                                        ft.Text(
                                            f"{authors} • {year or 's.d.'}",
                                            size=11 * self.scale,
                                            color=self.config.colors["muted"],
                                        ),
                                    ],
                                    spacing=2 * self.scale,
                                    tight=True,
                                    expand=True,
                                ),
                                status_badge,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        snippet_box,
                        actions_box,
                    ],
                    spacing=8 * self.scale,
                    tight=True,
                ),
            )
            self.works_column.controls.append(card)
    def _handle_open_ai_studio(self, _e: ft.ControlEvent) -> None:
        """Abre a página do Google AI Studio no navegador padrão."""
        url = "https://aistudio.google.com/app/apikey"
        try:
            webbrowser.open(url)
        except Exception:
            if self.page:
                self.page.launch_url(url)

    def _get_error_colors(self) -> tuple[str, str]:
        """Retorna (cor_texto, cor_fundo) com contraste dinâmico:
        - Fundo escuro: vermelho claro e luminoso (#FF6B6B).
        - Fundo claro: vermelho escuro e profundo (#B71C1C).
        """
        is_dark = (self.current_theme_mode or "light").lower() == "dark"
        if is_dark:
            return "#FF6B6B", "#FF6B6B25"
        return "#B71C1C", "#B71C1C18"

    def _handle_save_and_test_key(self, _e: ft.ControlEvent) -> None:
        """Salva a chave de API fornecida e executa teste de conectividade."""
        err_color, err_bg = self._get_error_colors()
        is_dark = (self.current_theme_mode or "light").lower() == "dark"
        key = (self.api_key_field.value or "").strip()
        if not key:
            self.status_feedback.value = "Por favor, digite ou cole a chave de API."
            self.status_feedback.color = err_color
            self.status_feedback.weight = ft.FontWeight.W_600
            self.page.update()
            return

        self.status_feedback.value = "Testando conexão com Google Gemini..."
        self.status_feedback.color = self.config.colors["muted"]
        self.status_feedback.weight = ft.FontWeight.W_400
        self.page.update()

        ok, msg = self.nous_service.test_connection(key)
        if ok:
            self.nous_service.save_api_key(key)
            self.has_key = True
            self.status_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE
            self.status_icon.color = self.config.colors["gold"]
            self.status_chip_text.value = "Conexão Ativa"
            self.status_chip_text.color = self.config.colors["gold"]
            self.status_chip_text.weight = ft.FontWeight.W_600
            self.status_chip.bgcolor = self.config.colors["surface"]
            self.status_chip.border = ft.Border.all(1, self.config.colors["gold"])
            self.status_feedback.value = "✓ " + msg
            self.status_feedback.color = self.config.colors["gold"]
            self.status_feedback.weight = ft.FontWeight.W_500
        else:
            self.status_icon.name = ft.Icons.ERROR_OUTLINE
            self.status_icon.color = err_color
            self.status_chip_text.value = "Falha na Conexão"
            self.status_chip_text.color = err_color
            self.status_chip_text.weight = ft.FontWeight.W_600
            self.status_chip.bgcolor = self.config.colors["surface"]
            self.status_chip.border = ft.Border.all(1, err_color)
            self.status_feedback.value = "✕ " + msg
            self.status_feedback.color = err_color
            self.status_feedback.weight = ft.FontWeight.W_600

        self.page.update()

    def _handle_single_generate(self, work_id: int) -> None:
        """Dispara a geração de descrição para uma única obra com feedback visual imediato em background thread mantendo o scroll."""
        if work_id in self.generating_work_ids or self.is_batch_running:
            return

        self.generating_work_ids.add(work_id)
        # Atualiza apenas o container de ações do card correspondente sem reconstruir a lista (mantém posição do scroll)
        work_item = next((w for w in self.works_data if w["id"] == work_id), None)
        actions_ctrl = self.work_actions_containers.get(work_id)
        if actions_ctrl is not None and work_item is not None:
            actions_ctrl.content = self._build_work_actions(work_item)
            try:
                actions_ctrl.update()
            except Exception:
                pass

        if hasattr(self.page, "overlay") and self.page.overlay is not None:
            snack = ft.SnackBar(ft.Text("Gerando síntese epistemológica com Nous..."))
            self.page.overlay.append(snack)

        def background_task():
            try:
                ok, msg = self.nous_service.generate_work_description(work_id)
            except Exception as err:
                ok, msg = False, str(err)
            finally:
                self.generating_work_ids.discard(work_id)

            if ok:
                if hasattr(self.page, "overlay") and self.page.overlay is not None:
                    res_snack = ft.SnackBar(ft.Text("✓ Síntese gerada e salva com sucesso!"))
                    self.page.overlay.append(res_snack)

                # Atualiza os dados locais e apenas os controles específicos da obra para não resetar o scroll
                updated_list = self.nous_service.list_works_ai_status()
                updated_item = next((w for w in updated_list if w["id"] == work_id), None)
                if updated_item is not None:
                    # Atualiza item em self.works_data
                    for idx, w in enumerate(self.works_data):
                        if w["id"] == work_id:
                            self.works_data[idx] = updated_item
                            break

                    # Atualiza métricas no topo in-place
                    total = len(self.works_data)
                    with_ai = sum(1 for w in self.works_data if w["has_llm"] and not w["has_custom"])
                    custom = sum(1 for w in self.works_data if w["has_custom"])
                    pending = sum(1 for w in self.works_data if not w["has_llm"] and not w["has_custom"])
                    self.stat_total.value = str(total)
                    self.stat_with_ai.value = str(with_ai)
                    self.stat_custom.value = str(custom)
                    self.stat_pending.value = str(pending)
                    if hasattr(self, "metrics_row") and self.metrics_row is not None:
                        try:
                            self.metrics_row.update()
                        except Exception:
                            pass

                    # Atualiza badge do card (fundo surface limpo, sem grená)
                    badge_box = self.work_badge_containers.get(work_id)
                    if badge_box is not None:
                        badge_box.content = ft.Text(
                            updated_item["status_label"].upper(),
                            size=9 * self.scale,
                            weight=ft.FontWeight.W_700,
                            color=updated_item["status_color"],
                        )
                        badge_box.bgcolor = self.config.colors["surface"]
                        badge_box.border = ft.Border.all(1, updated_item["status_color"])
                        try:
                            badge_box.update()
                        except Exception:
                            pass

                    # Atualiza snippet de texto do card
                    snip_box = self.work_snippet_texts.get(work_id)
                    if snip_box is not None:
                        snip_box.value = updated_item["snippet"] or "Sem síntese cadastrada."
                        try:
                            snip_box.update()
                        except Exception:
                            pass

                    # Atualiza botões de ação do card
                    act_box = self.work_actions_containers.get(work_id)
                    if act_box is not None:
                        act_box.content = self._build_work_actions(updated_item)
                        try:
                            act_box.update()
                        except Exception:
                            pass
                else:
                    self._refresh_works_data()
            else:
                if hasattr(self.page, "overlay") and self.page.overlay is not None:
                    res_snack = ft.SnackBar(ft.Text(f"Erro: {msg}"))
                    self.page.overlay.append(res_snack)
                target_w = next((w for w in self.works_data if w["id"] == work_id), None)
                act_box = self.work_actions_containers.get(work_id)
                if act_box is not None and target_w is not None:
                    act_box.content = self._build_work_actions(target_w)
                    try:
                        act_box.update()
                    except Exception:
                        pass

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
    def _handle_batch_generation(self, _e: ft.ControlEvent) -> None:
        """Executa processamento em lote para todas as obras pendentes em background thread."""
        if self.is_batch_running:
            return

        self.is_batch_running = True
        self.batch_progress_bar.visible = True
        self.batch_progress_text.visible = True
        self.batch_progress_bar.value = 0.0
        self.page.update()

        def update_progress(curr: int, total: int, title: str) -> None:
            self.batch_progress_bar.value = curr / max(1, total)
            self.batch_progress_text.value = f"Processando ({curr}/{total}): {title}"
            try:
                self.page.update()
            except Exception:
                pass

        def background_batch():
            try:
                results = self.nous_service.generate_batch_pending(on_progress=update_progress)
                res_msg = f"Concluído: {results['success']} obras processadas com sucesso, {results['failed']} falhas."
            except Exception as err:
                res_msg = f"Falha no processamento em lote: {err}"
            finally:
                self.is_batch_running = False
                self.batch_progress_bar.visible = False
                self.batch_progress_text.visible = False

            snack = ft.SnackBar(ft.Text(res_msg))
            self.page.overlay.append(snack)
            snack.open = True
            self._refresh_works_data()
            try:
                self.page.update()
            except Exception:
                pass

        thread = threading.Thread(target=background_batch, daemon=True)
        thread.start()

    def _open_override_dialog(self, work_item: Dict[str, Any]) -> None:
        """Abre diálogo para o usuário inspecionar e sobrepor a síntese com texto próprio."""
        work_id = work_item["id"]
        title = work_item["title"]
        current_custom = work_item.get("custom_description") or ""
        current_llm = work_item.get("llm_description") or ""

        text_input = ft.TextField(
            value=current_custom if current_custom else current_llm,
            label="Síntese Conceitual / Anotação da Obra",
            hint_text="Escreva ou ajuste a síntese da obra. Seu texto terá prioridade sobre a IA.",
            multiline=True,
            min_lines=6,
            max_lines=12,
            text_size=12 * self.scale,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["surface"],
        )

        def save_override(_):
            new_text = text_input.value or ""
            self.nous_service.override_work_description(work_id, new_text)
            dialog.open = False
            self.page.update()
            self._refresh_works_data()

        def clear_override(_):
            self.nous_service.override_work_description(work_id, None)
            dialog.open = False
            self.page.update()
            self._refresh_works_data()

        dialog = ft.AlertDialog(
            title=ft.Text(
                f"Personalizar Síntese: {title}",
                size=self.config.font_sizes["cormorant_medium"] * self.scale,
                font_family=self.config.font_families["cormorant"],
                color=self.config.colors["gold"],
            ),
            content=ft.Container(
                width=550 * self.scale,
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "O texto inserido aqui sobrepõe qualquer síntese gerada por IA e passará a orientar a posição da obra na Constelação 3D.",
                            size=11 * self.scale,
                            color=self.config.colors["muted"],
                        ),
                        text_input,
                    ],
                    spacing=10 * self.scale,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton(
                    content="Restaurar Síntese IA",
                    on_click=clear_override,
                ),
                ft.OutlinedButton(
                    content="Cancelar",
                    on_click=lambda _: setattr(dialog, "open", False) or self.page.update(),
                ),
                ft.FilledButton(
                    content="Salvar Síntese",
                    on_click=save_override,
                    style=ft.ButtonStyle(
                        bgcolor=self.config.colors["gold"],
                        color="#FFFFFF",
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _handle_search_filter(self, _e: ft.ControlEvent) -> None:
        """Filtra obras exibidas na lista em tempo real."""
        query = (self.search_filter.value or "").strip().lower()
        if not query:
            self._render_works_list(self.works_data)
        else:
            filtered = [
                w for w in self.works_data
                if query in w["title"].lower() or query in w["authors"].lower()
            ]
            self._render_works_list(filtered)
        self.page.update()