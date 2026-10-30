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
            size=11.5 * self.scale,
            weight=ft.FontWeight.W_700,
            color=self.config.colors["muted"],
            font_family=self.config.font_families["montserrat"],
        )
        self.badge_container = ft.Container(
            content=self.badge_text,
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=4,
            padding=ft.Padding(8 * self.scale, 3 * self.scale, 8 * self.scale, 3 * self.scale),
        )

        self.title_text = ft.Text(
            "",
            size=24 * self.scale,
            font_family=self.config.font_families["cormorant"],
            weight=ft.FontWeight.W_700,
            color=self.config.colors["text"],
            max_lines=3,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        self.meta_text = ft.Text(
            "",
            size=13 * self.scale,
            font_family=self.config.font_families["montserrat"],
            weight=ft.FontWeight.W_600,
            color=self.config.colors["muted"],
        )

        self.excerpt_text = ft.Text(
            "",
            size=15 * self.scale,
            font_family=self.config.font_families["cormorant"],
            italic=True,
            weight=ft.FontWeight.W_500,
            color=self.config.colors["text"],
            selectable=True,
        )

        self.excerpt_container = ft.Container(
            content=self.excerpt_text,
            bgcolor=self.config.colors["surface"],
            border=ft.Border(
                left=ft.BorderSide(3 * self.scale, self.config.colors["border"]),
                top=ft.BorderSide(1, self.config.colors["border"]),
                right=ft.BorderSide(1, self.config.colors["border"]),
                bottom=ft.BorderSide(1, self.config.colors["border"]),
            ),
            padding=12 * self.scale,
            border_radius=6,
        )

        self.resonances_column = ft.Column(spacing=8 * self.scale, tight=True)
        self.fragments_column = ft.Column(spacing=8 * self.scale, tight=True)
        self._pending_fragment_id: Optional[int] = None

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
                                "SÍNTESE DA OBRA / RESUMO",
                                size=12 * self.scale,
                                weight=ft.FontWeight.W_700,
                                font_family=self.config.font_families["montserrat"],
                                color=self.config.colors["muted"],
                            ),
                            self.excerpt_container,
                            ft.Container(height=4 * self.scale),

                            # Direct Actions (Compilação)
                            ft.Column(
                                controls=[
                                    self.compilation_dropdown,
                                    self.compilation_confirm_btn,
                                ],
                                spacing=6 * self.scale,
                                tight=True,
                            ),
                            ft.Container(height=8 * self.scale),

                            # Resonances Section
                            ft.Row(
                                controls=[
                                    ft.Icon(
                                        ft.Icons.AUTO_AWESOME,
                                        size=15 * self.scale,
                                        color=self.config.colors["text"],
                                    ),
                                    ft.Text(
                                        "OBRAS PRÓXIMAS / RESSONANTES",
                                        size=13 * self.scale,
                                        weight=ft.FontWeight.W_700,
                                        color=self.config.colors["text"],
                                        font_family=self.config.font_families["montserrat"],
                                    ),
                                ],
                                spacing=6 * self.scale,
                            ),
                            self.resonances_column,
                            ft.Container(height=12 * self.scale),

                            # Fragments Section
                            ft.Row(
                                controls=[
                                    ft.Icon(
                                        ft.Icons.FORMAT_QUOTE,
                                        size=15 * self.scale,
                                        color=self.config.colors["text"],
                                    ),
                                    ft.Text(
                                        "FRAGMENTOS DESTA OBRA",
                                        size=13 * self.scale,
                                        weight=ft.FontWeight.W_700,
                                        color=self.config.colors["text"],
                                        font_family=self.config.font_families["montserrat"],
                                    ),
                                ],
                                spacing=6 * self.scale,
                            ),
                            self.fragments_column,
                        ],
                        scroll=ft.ScrollMode.ADAPTIVE,
                        spacing=10 * self.scale,
                    ),
                ),
            ],
            spacing=10 * self.scale,
            expand=True,
        )

    def set_node(
        self,
        node: Dict[str, Any],
        resonances: List[Dict[str, Any]],
        work_fragments: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Atualiza os dados exibidos no painel e torna-o visível."""
        self.current_node = node
        self.current_resonances = resonances

        node_type = (node.get("type") or "Nó").upper()
        if node_type == "WORK":
            doc_type = node.get("doc_type") or "Obra"
            self.badge_text.value = f"OBRA: {doc_type.upper()}"
        elif node_type == "CLUSTER":
            self.badge_text.value = "CLUSTER CONCEITUAL"
        else:
            self.badge_text.value = node_type

        self.title_text.value = node.get("title") or node.get("label") or "Sem Título"
        meta_parts = []
        if node.get("author"):
            meta_parts.append(node["author"])
        if node.get("cluster_name"):
            meta_parts.append(f"Constelação: {node['cluster_name']}")
        frag_count = node.get("fragment_count", 0)
        meta_parts.append(f"{frag_count} Fragmentos")
        self.meta_text.value = " • ".join(meta_parts) if meta_parts else ""

        full_text = node.get("full_text") or node.get("excerpt") or "Sem síntese conceitual disponível."
        self.excerpt_text.value = full_text

        # Configure action visibility
        self.compilation_dropdown.visible = False
        self.compilation_confirm_btn.visible = False
        self._pending_fragment_id = None

        # Populate resonances
        self.resonances_column.controls.clear()
        if not resonances:
            self.resonances_column.controls.append(
                ft.Text(
                    "Nenhuma obra ressonante detectada acima do limiar selecionado.",
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

        # Populate fragments of this work
        self.fragments_column.controls.clear()
        frags = work_fragments or []
        if not frags:
            self.fragments_column.controls.append(
                ft.Text(
                    "Esta obra ainda não possui citações ou fragmentos registrados no Acervo.",
                    size=11 * self.scale,
                    color=self.config.colors["muted"],
                    italic=True,
                )
            )
        else:
            for frag in frags:
                card = self._build_fragment_card(frag)
                self.fragments_column.controls.append(card)

        self.panel_container.visible = True
        try:
            self.panel_container.update()
        except Exception:
            pass

    def _build_fragment_card(self, frag: Dict[str, Any]) -> ft.Control:
        f_id = int(frag.get("id") or 0)
        excerpt = frag.get("excerpt") or ""
        loc = frag.get("location") or ""
        frag_type = (frag.get("fragment_type") or "quote").capitalize()
        type_label = "Citação" if frag_type.lower() == "quote" else "Comentário"

        badge_bg = self.config.colors.get("card_hover", self.config.colors["surface"])
        card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(
                                    f"{type_label} • {loc}" if loc else type_label,
                                    size=11.5 * self.scale,
                                    weight=ft.FontWeight.W_700,
                                    color=self.config.colors["muted"],
                                    font_family=self.config.font_families["montserrat"],
                                ),
                                bgcolor=badge_bg,
                                border=ft.Border.all(1, self.config.colors["border"]),
                                border_radius=4,
                                padding=ft.Padding(6 * self.scale, 2 * self.scale, 6 * self.scale, 2 * self.scale),
                            ),
                            ft.Row(
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.COPY_ALL_OUTLINED,
                                        icon_size=15 * self.scale,
                                        icon_color=self.config.colors["text"],
                                        tooltip="Copiar trecho",
                                        on_click=lambda _, t=excerpt: self._copy_text(t),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.COLLECTIONS_BOOKMARK_OUTLINED,
                                        icon_size=15 * self.scale,
                                        icon_color=self.config.colors["text"],
                                        tooltip="Adicionar à Compilação",
                                        on_click=lambda _, fid=f_id: self._handle_add_frag_click(fid),
                                    ),
                                ],
                                spacing=2,
                                tight=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        f'"{excerpt}"',
                        size=13 * self.scale,
                        italic=True,
                        weight=ft.FontWeight.W_500,
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["montserrat"],
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=4 * self.scale,
                tight=True,
            ),
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=self.config.ui.get("card_radius", 6),
            padding=8 * self.scale,
        )
        return card

    def _copy_text(self, text: str) -> None:
        if self.page and text:
            self.page.set_clipboard(text)
            snack = ft.SnackBar(ft.Text("Trecho copiado para a área de transferência."))
            self.page.overlay.append(snack)
            snack.open = True
            try:
                self.page.update()
            except Exception:
                pass

    def _handle_add_frag_click(self, frag_id: int) -> None:
        self._pending_fragment_id = frag_id
        self._handle_compilation_click(None)

    def _build_resonance_card(self, res: Dict[str, Any], sim_pct: int) -> ft.Control:
        label = res.get("label") or "Elemento ressonante"
        work_title = res.get("work_title") or ""
        target_node = res.get("target_node") or res

        badge_bg = self.config.colors.get("card_hover", self.config.colors["surface"])
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                label,
                                size=14 * self.scale,
                                weight=ft.FontWeight.W_700,
                                color=self.config.colors["text"],
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    f"{sim_pct}%",
                                    size=11.5 * self.scale,
                                    weight=ft.FontWeight.W_700,
                                    color=self.config.colors["text"],
                                    font_family=self.config.font_families["montserrat"],
                                ),
                                bgcolor=badge_bg,
                                border=ft.Border.all(1, self.config.colors["border"]),
                                border_radius=4,
                                padding=ft.Padding(6 * self.scale, 2 * self.scale, 6 * self.scale, 2 * self.scale),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        work_title,
                        size=12 * self.scale,
                        color=self.config.colors["muted"],
                        weight=ft.FontWeight.W_600,
                        font_family=self.config.font_families["montserrat"],
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ) if work_title else ft.Container(),
                    ft.ProgressBar(
                        value=sim_pct / 100.0,
                        color=self.config.colors["text"],
                        bgcolor=self.config.colors["border"],
                        height=4 * self.scale,
                        border_radius=2,
                    ),
                ],
                spacing=4 * self.scale,
                tight=True,
            ),
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=self.config.ui.get("card_radius", 6),
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
        if not self.compilation_dropdown.value:
            return
        entity_id = self._pending_fragment_id or (self.current_node.get("entity_id") if self.current_node else None)
        compilation_id = int(self.compilation_dropdown.value)

        if entity_id and self.on_add_to_compilation:
            success = self.on_add_to_compilation(int(entity_id), compilation_id)
            if self.page:
                msg = "Fragmento adicionado à compilação com sucesso!" if success else "Não foi possível adicionar."
                snack = ft.SnackBar(ft.Text(msg))
                self.page.overlay.append(snack)
                snack.open = True
                self.page.update()

        self.compilation_dropdown.visible = False
        self.compilation_confirm_btn.visible = False
        self._pending_fragment_id = None
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
