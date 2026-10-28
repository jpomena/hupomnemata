from collections.abc import Callable
from typing import Any, Dict, List, Optional
import flet as ft

from src.utils.types import ViewConfig


class KnowledgePanel:
    """
    Painel retrátil lateral para inspeção de nós da Malha de Conhecimento.
    Apresenta metadados do nó selecionado, trecho completo, lista de ressonâncias
    semânticas com indicador percentual, e ações diretas de pesquisa (compilar, vincular).
    """

    def __init__(
        self,
        config: ViewConfig,
        scale: float,
        on_close: Callable[[], None],
        on_select_resonance: Callable[[Dict[str, Any]], None],
        on_add_to_compilation: Optional[Callable[[int, int], bool]] = None,
        on_create_link: Optional[Callable[[Dict[str, Any]], None]] = None,
        list_compilations: Optional[Callable[[], List[Any]]] = None,
        page: Optional[ft.Page] = None,
    ) -> None:
        self.config = config
        self.scale = scale
        self.on_close = on_close
        self.on_select_resonance = on_select_resonance
        self.on_add_to_compilation = on_add_to_compilation
        self.on_create_link = on_create_link
        self.list_compilations = list_compilations
        self.page = page

        self.current_node: Optional[Dict[str, Any]] = None
        self.current_resonances: List[Dict[str, Any]] = []

        # UI Controls
        self.badge_text = ft.Text(
            "",
            size=10 * self.scale,
            weight=ft.FontWeight.W_700,
            color=self.config.colors["gold"],
        )
        self.badge_container = ft.Container(
            content=self.badge_text,
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, self.config.colors["gold"]),
            border_radius=4,
            padding=ft.Padding(8 * self.scale, 3 * self.scale, 8 * self.scale, 3 * self.scale),
        )

        self.title_text = ft.Text(
            "",
            size=self.config.font_sizes["cormorant_medium"] * self.scale,
            font_family=self.config.font_families["cormorant"],
            weight=self.config.font_weights["cormorant_bold"],
            color=self.config.colors["gold"],
            max_lines=3,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        self.meta_text = ft.Text(
            "",
            size=self.config.font_sizes["montserrat_tiny"] * self.scale,
            font_family=self.config.font_families["montserrat"],
            color=self.config.colors["muted"],
        )

        self.excerpt_text = ft.Text(
            "",
            size=self.config.font_sizes.get("cormorant_small", 16) * self.scale,
            font_family=self.config.font_families["cormorant"],
            italic=True,
            color=self.config.colors["text"],
            selectable=True,
        )

        self.excerpt_container = ft.Container(
            content=self.excerpt_text,
            bgcolor=f"{self.config.colors['bg']}",
            border=ft.Border(left=ft.BorderSide(3 * self.scale, self.config.colors["gold"])),
            padding=12 * self.scale,
            border_radius=4,
        )

        self.resonances_column = ft.Column(spacing=8 * self.scale, tight=True)

        self.compilation_dropdown = ft.Dropdown(
            label="Escolha a Compilação",
            options=[],
            width=280 * self.scale,
            text_size=self.config.font_sizes["montserrat_tiny"] * self.scale,
            visible=False,
        )

        self.compilation_action_btn = ft.OutlinedButton(
            content="Adicionar à Compilação",
            icon=ft.Icons.COLLECTIONS_BOOKMARK_OUTLINED,
            on_click=self._handle_compilation_click,
            style=ft.ButtonStyle(
                color=self.config.colors["text"],
                side=ft.BorderSide(1, self.config.colors["border"]),
            ),
        )

        self.compilation_confirm_btn = ft.FilledButton(
            content="Confirmar",
            on_click=self._confirm_add_compilation,
            visible=False,
            style=ft.ButtonStyle(
                bgcolor=self.config.colors["gold"],
                color="#FFFFFF",
            ),
        )

        self.panel_container = ft.Container(
            visible=False,
            width=380 * self.scale,
            bgcolor=self.config.colors["surface"],
            border=ft.Border(left=ft.BorderSide(1, self.config.colors["border"])),
            padding=16 * self.scale,
            content=self._build_content(),
        )

    def _build_content(self) -> ft.Control:
        return ft.Column(
            controls=[
                # Header
                ft.Row(
                    controls=[
                        self.badge_container,
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_size=18 * self.scale,
                            icon_color=self.config.colors["muted"],
                            on_click=lambda _: self.close(),
                            tooltip="Fechar painel",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.title_text,
                self.meta_text,
                ft.Divider(color=self.config.colors["border"], height=10 * self.scale),

                # Scrollable body
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "CONTEÚDO / TRECHO",
                                size=10 * self.scale,
                                weight=ft.FontWeight.W_700,
                                color=self.config.colors["muted"],
                            ),
                            self.excerpt_container,
                            ft.Container(height=8 * self.scale),

                            # Direct Actions
                            ft.Text(
                                "AÇÕES DE PESQUISA",
                                size=10 * self.scale,
                                weight=ft.FontWeight.W_700,
                                color=self.config.colors["muted"],
                            ),
                            ft.Column(
                                controls=[
                                    self.compilation_action_btn,
                                    self.compilation_dropdown,
                                    self.compilation_confirm_btn,
                                ],
                                spacing=6 * self.scale,
                                tight=True,
                            ),
                            ft.Container(height=12 * self.scale),

                            # Resonances
                            ft.Row(
                                controls=[
                                    ft.Icon(
                                        ft.Icons.AUTO_AWESOME,
                                        size=14 * self.scale,
                                        color=self.config.colors["gold"],
                                    ),
                                    ft.Text(
                                        "RESSONÂNCIAS SEMÂNTICAS",
                                        size=11 * self.scale,
                                        weight=ft.FontWeight.W_700,
                                        color=self.config.colors["gold"],
                                    ),
                                ],
                                spacing=6 * self.scale,
                            ),
                            self.resonances_column,
                        ],
                        scroll=ft.ScrollMode.ADAPTIVE,
                        spacing=10 * self.scale,
                    ),
                ),
            ],
            spacing=10 * self.scale,
            expand=True,
        )

    def set_node(self, node: Dict[str, Any], resonances: List[Dict[str, Any]]) -> None:
        """Atualiza os dados exibidos no painel e torna-o visível."""
        self.current_node = node
        self.current_resonances = resonances

        node_type = (node.get("type") or "Nó").upper()
        if node_type == "FRAGMENT":
            self.badge_text.value = "CITAÇÃO / FRAGMENTO"
        elif node_type == "WORK":
            self.badge_text.value = "OBRA / TEXTO"
        elif node_type == "CLUSTER":
            self.badge_text.value = "CLUSTER CONCEITUAL"
        else:
            self.badge_text.value = node_type

        self.title_text.value = node.get("label") or "Sem Título"
        meta_parts = []
        if node.get("work_title"):
            meta_parts.append(f"Obra: {node['work_title']}")
        if node.get("cluster_name"):
            meta_parts.append(f"Cluster: {node['cluster_name']}")
        self.meta_text.value = " • ".join(meta_parts) if meta_parts else ""

        full_text = node.get("full_text") or "Sem conteúdo textual disponível."
        self.excerpt_text.value = full_text

        # Configure action visibility
        is_fragment = node.get("type") == "fragment"
        self.compilation_action_btn.visible = is_fragment
        self.compilation_dropdown.visible = False
        self.compilation_confirm_btn.visible = False

        # Populate resonances
        self.resonances_column.controls.clear()
        if not resonances:
            self.resonances_column.controls.append(
                ft.Text(
                    "Nenhuma ressonância detectada acima do limiar selecionado.",
                    size=11 * self.scale,
                    color=self.config.colors["muted"],
                    italic=True,
                )
            )
        else:
            for res in resonances[:8]:
                sim_pct = int((res.get("weight") or 0.0) * 100)
                card = self._build_resonance_card(res, sim_pct)
                self.resonances_column.controls.append(card)

        self.panel_container.visible = True
        try:
            self.panel_container.update()
        except Exception:
            pass

    def _build_resonance_card(self, res: Dict[str, Any], sim_pct: int) -> ft.Control:
        label = res.get("label") or "Elemento ressonante"
        work_title = res.get("work_title") or ""
        target_node = res.get("target_node") or res

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                label,
                                size=12 * self.scale,
                                weight=ft.FontWeight.W_600,
                                color=self.config.colors["text"],
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    f"{sim_pct}%",
                                    size=10 * self.scale,
                                    weight=ft.FontWeight.W_700,
                                    color=self.config.colors["gold"],
                                ),
                                bgcolor=f"{self.config.colors['gold']}20",
                                border_radius=4,
                                padding=ft.Padding(6 * self.scale, 2 * self.scale, 6 * self.scale, 2 * self.scale),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        work_title,
                        size=10 * self.scale,
                        color=self.config.colors["muted"],
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ) if work_title else ft.Container(),
                    ft.ProgressBar(
                        value=sim_pct / 100.0,
                        color=self.config.colors["gold"],
                        bgcolor=self.config.colors["border"],
                        height=3 * self.scale,
                        border_radius=2,
                    ),
                ],
                spacing=4 * self.scale,
                tight=True,
            ),
            bgcolor=self.config.colors["bg"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=6,
            padding=8 * self.scale,
            on_click=lambda _, tn=target_node: self.on_select_resonance(tn),
            tooltip="Clique para pivotar a este nó",
        )

    def _handle_compilation_click(self, _e: ft.ControlEvent) -> None:
        if not self.list_compilations:
            return
        compilations = self.list_compilations()
        if not compilations:
            if self.page:
                snack = ft.SnackBar(ft.Text("Nenhuma compilação criada ainda. Crie uma em 'Compilações'."))
                self.page.overlay.append(snack)
                snack.open = True
                self.page.update()
            return

        options = []
        for c in compilations:
            c_id = str(c.get("id") if isinstance(c, dict) else getattr(c, "id"))
            c_title = str(c.get("title") if isinstance(c, dict) else getattr(c, "title", c_id))
            options.append(ft.dropdown.Option(key=c_id, text=c_title))
        self.compilation_dropdown.options = options
        if self.compilation_dropdown.options:
            self.compilation_dropdown.value = self.compilation_dropdown.options[0].key

        self.compilation_dropdown.visible = True
        self.compilation_confirm_btn.visible = True
        try:
            self.panel_container.update()
        except Exception:
            pass

    def _confirm_add_compilation(self, _e: ft.ControlEvent) -> None:
        if not self.current_node or not self.compilation_dropdown.value:
            return
        entity_id = self.current_node.get("entity_id")
        compilation_id = int(self.compilation_dropdown.value)

        if entity_id and self.on_add_to_compilation:
            success = self.on_add_to_compilation(entity_id, compilation_id)
            if self.page:
                msg = "Citação adicionada à compilação com sucesso!" if success else "Não foi possível adicionar."
                snack = ft.SnackBar(ft.Text(msg))
                self.page.overlay.append(snack)
                snack.open = True
                self.page.update()

        self.compilation_dropdown.visible = False
        self.compilation_confirm_btn.visible = False
        try:
            self.panel_container.update()
        except Exception:
            pass

    def close(self) -> None:
        self.current_node = None
        self.current_resonances = []
        self.panel_container.visible = False
        self.on_close()
        try:
            self.panel_container.update()
        except Exception:
            pass

    def compose(self) -> ft.Control:
        return self.panel_container
