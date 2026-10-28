import math
from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, List, Optional
import flet as ft
import flet.canvas as cv

from src.utils.types import ViewConfig
from src.views.knowledge.graph_template import generate_graph_html
from src.views.knowledge.knowledge_panel import KnowledgePanel
from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
from src.utils.ft_responsiveness import Responsive


def compute_graph_layout(
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
    width: float = 1600.0,
    height: float = 1100.0,
) -> None:
    """Calcula coordenadas 2D orgânicas e distribuídas por clusters para os nós."""
    if not nodes:
        return

    clusters: Dict[int, List[Dict[str, Any]]] = {}
    for n in nodes:
        c_id = n.get("cluster_id") or 0
        clusters.setdefault(c_id, []).append(n)

    num_clusters = len(clusters)
    cluster_centers: Dict[int, tuple[float, float]] = {}
    cx, cy = width / 2.0, height / 2.0
    r_x = width * 0.30
    r_y = height * 0.30

    for idx, c_id in enumerate(clusters.keys()):
        angle = 2.0 * math.pi * idx / max(1, num_clusters)
        cluster_centers[c_id] = (
            cx + r_x * math.cos(angle),
            cy + r_y * math.sin(angle),
        )

    for c_id, c_nodes in clusters.items():
        cc_x, cc_y = cluster_centers[c_id]
        m = len(c_nodes)
        for i, n in enumerate(c_nodes):
            sub_angle = 2.0 * math.pi * i / max(1, m)
            dist = 45.0 + (i % 3) * 40.0
            n["x"] = cc_x + dist * math.cos(sub_angle)
            n["y"] = cc_y + dist * math.sin(sub_angle)

    # Relaxação rápida tipo mola (25 passos)
    node_map = {n["id"]: n for n in nodes}
    for _ in range(25):
        # Repulsão entre nós próximos
        for i in range(len(nodes)):
            n1 = nodes[i]
            for j in range(i + 1, len(nodes)):
                n2 = nodes[j]
                dx = n1["x"] - n2["x"]
                dy = n1["y"] - n2["y"]
                dist = math.hypot(dx, dy)
                if 0 < dist < 140.0:
                    force = (140.0 - dist) / dist * 0.45
                    n1["x"] += dx * force
                    n1["y"] += dy * force
                    n2["x"] -= dx * force
                    n2["y"] -= dy * force

        # Atração pelas arestas de ressonância
        for l in links:
            s_id = l.get("source")
            t_id = l.get("target")
            s = node_map.get(s_id)
            t = node_map.get(t_id)
            if s and t:
                dx = t["x"] - s["x"]
                dy = t["y"] - s["y"]
                dist = math.hypot(dx, dy)
                if dist > 80.0:
                    w = float(l.get("weight") or 0.5)
                    fx = dx * 0.04 * w
                    fy = dy * 0.04 * w
                    s["x"] += fx
                    s["y"] += fy
                    t["x"] -= fx
                    t["y"] -= fy

        # Manter dentro dos limites da área de desenho
        for n in nodes:
            n["x"] = max(80.0, min(width - 80.0, n["x"]))
            n["y"] = max(80.0, min(height - 80.0, n["y"]))


class KnowledgeComposer:
    """
    Compositor da visão 'Estruturas de Saber'.
    Apresenta visualizador de malha semântica interativo em tela cheia com zoom/pan,
    filtro por busca em tempo real, ajuste de sensibilidade de ressonância,
    integração com exportação D3.js e painel retrátil de inspeção.
    """

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        scale: float,
        on_navigate: Callable[[str], None],
        get_graph_data: Callable[[float], Dict[str, Any]],
        sync_mesh: Callable[[], Dict[str, Any]],
        get_resonances: Callable[[str, int, float, int], List[Dict[str, Any]]],
        on_add_to_compilation: Optional[Callable[[int, int], bool]] = None,
        list_compilations: Optional[Callable[[], List[Any]]] = None,
        on_create_link: Optional[Callable[..., bool]] = None,
        current_theme_mode: str = "light",
    ) -> None:
        self.page = page
        self.config = config
        self.scale = scale
        self.on_navigate = on_navigate
        self.get_graph_data = get_graph_data
        self.sync_mesh = sync_mesh
        self.get_resonances = get_resonances
        self.on_add_to_compilation = on_add_to_compilation
        self.list_compilations = list_compilations
        self.on_create_link = on_create_link
        self.current_theme_mode = current_theme_mode

        self.min_similarity = 0.40
        self.graph_data: Dict[str, Any] = {"nodes": [], "links": [], "clusters": []}
        self.selected_node_id: Optional[str] = None
        self.node_containers: Dict[str, ft.Container] = {}
        self.filter_mode = "all"  # 'all', 'works', 'fragments'

        # Dimensões dinâmicas calculadas com base no viewport disponível
        init_w, init_h = self._compute_viewport_dimensions()
        self.canvas_width = 1800.0  # Para mapa 2D com pan & zoom
        self.canvas_height = 1200.0

        # Sub-painel retrátil de inspeção
        self.panel = KnowledgePanel(
            config=self.config,
            scale=self.scale,
            on_close=self._handle_panel_close,
            on_select_resonance=self._handle_resonance_selected,
            on_add_to_compilation=self.on_add_to_compilation,
            list_compilations=self.list_compilations,
            page=self.page,
        )

        # Controles da barra de ferramentas
        self.search_field = ft.TextField(
            hint_text="Buscar nós, conceitos, trechos ou autores...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._handle_search_change,
            border_radius=8,
            height=38 * self.scale,
            text_size=12 * self.scale,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["surface"],
            expand=True,
            content_padding=ft.Padding(10, 0, 10, 0),
        )

        self.stats_text = ft.Text(
            "0 Estrelas • 0 Ressonâncias • 0 Clusters",
            size=self.config.font_sizes["montserrat_tiny"] * self.scale,
            font_family=self.config.font_families["montserrat"],
            weight=self.config.font_weights["montserrat_semibold"],
            color=self.config.colors["muted"],
        )

        self.filter_mode_dropdown = ft.Dropdown(
            label="Camada Celeste",
            value="all",
            options=[
                ft.dropdown.Option("all", "Todas as Estrelas"),
                ft.dropdown.Option("works", "Apenas Obras (Macro)"),
                ft.dropdown.Option("fragments", "Apenas Fragmentos (Micro)"),
            ],
            on_select=self._handle_filter_mode_change,
            width=145 * self.scale,
            height=38 * self.scale,
            text_size=11 * self.scale,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["surface"],
            content_padding=ft.Padding(8, 0, 8, 0),
        )

        self.sensitivity_dropdown = ft.Dropdown(
            label="Sensibilidade",
            value="0.40",
            options=[
                ft.dropdown.Option("0.30", "Alta (30%)"),
                ft.dropdown.Option("0.40", "Equilibrada (40%)"),
                ft.dropdown.Option("0.55", "Rigorosa (55%)"),
                ft.dropdown.Option("0.70", "Intensa (70%)"),
            ],
            on_select=self._handle_sensitivity_change,
            width=125 * self.scale,
            height=38 * self.scale,
            text_size=11 * self.scale,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["surface"],
            content_padding=ft.Padding(8, 0, 8, 0),
        )

        self.sync_button = ft.FilledButton(
            content="Sincronizar",
            icon=ft.Icons.SYNC,
            on_click=self._handle_sync_mesh,
            style=ft.ButtonStyle(
                bgcolor=self.config.colors["gold"],
                color="#FFFFFF",
                padding=ft.Padding(10, 0, 10, 0),
            ),
        )

        self.d3_button = ft.OutlinedButton(
            content="D3.js",
            icon=ft.Icons.OPEN_IN_BROWSER,
            on_click=self._handle_open_browser_graph,
            style=ft.ButtonStyle(
                color=self.config.colors["text"],
                side=ft.BorderSide(1, self.config.colors["border"]),
                padding=ft.Padding(10, 0, 10, 0),
            ),
        )

        # Camadas da malha interativa 2D
        self.canvas = cv.Canvas(
            width=self.canvas_width,
            height=self.canvas_height,
            shapes=[],
        )

        self.graph_stack = ft.Stack(
            controls=[self.canvas],
            width=self.canvas_width,
            height=self.canvas_height,
        )

        self.interactive_viewer = ft.InteractiveViewer(
            content=self.graph_stack,
            pan_enabled=True,
            scale_enabled=True,
            min_scale=0.3,
            max_scale=3.0,
            boundary_margin=400,
            expand=True,
        )

        self.view_mode = "3d"  # Padrão: Constelação 3D Esfera Armilar
        self.armillary_3d = ArmillaryConstellation3D(
            config=self.config,
            scale=self.scale,
            on_select_node=self._handle_node_clicked,
            current_theme_mode=self.current_theme_mode,
            canvas_width=init_w,
            canvas_height=init_h,
        )

        self.viewport_container = ft.Container(
            content=self.armillary_3d.compose(),
            alignment=ft.Alignment(0, 0),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        self.grid_toggle_btn = ft.IconButton(
            icon=ft.Icons.GRID_4X4,
            tooltip="Exibir/Ocultar Grade Celeste",
            icon_color=self.config.colors["gold"],
            icon_size=18 * self.scale,
            on_click=self._handle_toggle_celestial_grid,
        )

        self.mode_toggle_btn = ft.OutlinedButton(
            content="Mapa 2D",
            icon=ft.Icons.GRID_VIEW,
            on_click=self._handle_toggle_view_mode,
            style=ft.ButtonStyle(
                color=self.config.colors["text"],
                side=ft.BorderSide(1, self.config.colors["border"]),
                padding=ft.Padding(10, 0, 10, 0),
            ),
        )

        self.root_container = ft.Container(
            expand=True,
            bgcolor=self.config.colors["bg"],
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=self._build_layout(),
        )

    def _compute_viewport_dimensions(self, panel_open: bool = False) -> Tuple[float, float]:
        """Calcula precisamente a área visível do canvas 3D no dashboard."""
        pw, ph = Responsive.get_page_dimensions(self.page)
        sidebar_w = float(self.config.ui.get("sidebar_width", 350))
        panel_w = (380.0 * self.scale) if panel_open else 0.0

        # Subtrai sidebar, toolbar superior e margens de layout
        avail_w = max(400.0, pw - sidebar_w - panel_w)
        avail_h = max(300.0, ph - 116.0)
        return avail_w, avail_h

    def on_window_resized(self) -> None:
        """Notificado pelo WindowControllerMixin quando a janela muda de tamanho."""
        panel_open = bool(self.panel and self.panel.panel_container and self.panel.panel_container.visible)
        vw, vh = self._compute_viewport_dimensions(panel_open=panel_open)
        self.armillary_3d.update_dimensions(vw, vh)
        try:
            self.viewport_container.update()
            self.root_container.update()
        except Exception:
            pass

    def _build_layout(self) -> ft.Control:
        self.toolbar = ft.Container(
            bgcolor=self.config.colors["surface"],
            border=ft.Border(bottom=ft.BorderSide(1, self.config.colors["border"])),
            padding=ft.Padding.only(
                left=self.config.ui["header_horizontal_padding"] * self.scale,
                right=self.config.ui["header_horizontal_padding"] * self.scale,
                top=self.config.ui["header_top_padding"] * self.scale,
                bottom=self.config.ui["header_bottom_padding"] * self.scale,
            ),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Estruturas de Saber",
                                size=self.config.font_sizes["cormorant_big"] * self.scale,
                                font_family=self.config.font_families["cormorant"],
                                weight=self.config.font_weights["cormorant_semibold"],
                                color=self.config.colors["text"],
                            ),
                            self.stats_text,
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.CENTER,
                        tight=True,
                    ),
                    ft.Container(
                        content=self.search_field,
                        width=240 * self.scale,
                        padding=ft.Padding(10 * self.scale, 0, 10 * self.scale, 0),
                    ),
                    ft.Row(
                        controls=[
                            self.filter_mode_dropdown,
                            self.sensitivity_dropdown,
                            self.grid_toggle_btn,
                            self.mode_toggle_btn,
                            self.sync_button,
                            self.d3_button,
                        ],
                        spacing=6 * self.scale,
                        alignment=ft.MainAxisAlignment.END,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # Empty state placeholder overlay
        self.empty_state_text = ft.Container(
            visible=False,
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.AUTO_AWESOME_OUTLINED,
                        size=48 * self.scale,
                        color=self.config.colors["muted"],
                    ),
                    ft.Text(
                        "Nenhuma citação ou obra vetorizada ainda.",
                        size=self.config.font_sizes["cormorant_medium"] * self.scale,
                        font_family=self.config.font_families["cormorant"],
                        color=self.config.colors["muted"],
                    ),
                    ft.Text(
                        "Cadastre obras e citações no Acervo para construir a malha semântica,\nou clique em 'Sincronizar' para processar o acervo existente.",
                        size=12 * self.scale,
                        color=self.config.colors["muted"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=8 * self.scale),
                    ft.FilledButton(
                        content="Sincronizar Agora",
                        icon=ft.Icons.BOLT,
                        on_click=self._handle_sync_mesh,
                        style=ft.ButtonStyle(
                            bgcolor=self.config.colors["gold"],
                            color="#FFFFFF",
                        ),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8 * self.scale,
                tight=True,
            ),
            expand=True,
        )

        main_body = ft.Row(
            controls=[
                ft.Stack(
                    controls=[
                        self.viewport_container,
                        self.empty_state_text,
                    ],
                    expand=True,
                ),
                self.panel.compose(),
            ],
            expand=True,
            spacing=0,
        )

        return ft.Column(
            controls=[
                self.toolbar,
                main_body,
            ],
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def compose(self) -> ft.Control:
        """Carrega e monta a visualização da malha de conhecimento."""
        panel_open = bool(self.panel and self.panel.panel_container and self.panel.panel_container.visible)
        vw, vh = self._compute_viewport_dimensions(panel_open=panel_open)
        self.armillary_3d.update_dimensions(vw, vh)
        self._refresh_graph()
        return self.root_container

    def _get_filtered_nodes(self) -> List[Dict[str, Any]]:
        all_nodes = self.graph_data.get("nodes") or []
        if self.filter_mode == "works":
            return [n for n in all_nodes if n.get("type") == "work"]
        elif self.filter_mode == "fragments":
            return [n for n in all_nodes if n.get("type") != "work"]
        return all_nodes

    def _get_filtered_links(self, visible_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        all_links = self.graph_data.get("links") or []
        v_ids = {n["id"] for n in visible_nodes}
        return [l for l in all_links if l.get("source") in v_ids and l.get("target") in v_ids]

    def _update_stats_display(self) -> None:
        nodes = self._get_filtered_nodes()
        links = self._get_filtered_links(nodes)
        clusters = self.graph_data.get("clusters") or []
        if self.filter_mode == "works":
            self.stats_text.value = f"{len(nodes)} Obras • {len(links)} Ressonâncias • {len(clusters)} Clusters"
        elif self.filter_mode == "fragments":
            self.stats_text.value = f"{len(nodes)} Fragmentos • {len(links)} Ressonâncias • {len(clusters)} Clusters"
        else:
            works_cnt = sum(1 for n in nodes if n.get("type") == "work")
            frags_cnt = len(nodes) - works_cnt
            self.stats_text.value = f"{len(nodes)} Estrelas ({works_cnt} Obras, {frags_cnt} Fragmentos) • {len(links)} Ressonâncias • {len(clusters)} Clusters"

    def _refresh_graph(self) -> None:
        """Recarrega os dados do grafo, executa o layout e renderiza nós e arestas."""
        try:
            self.graph_data = self.get_graph_data(self.min_similarity)
        except Exception:
            self.graph_data = {"nodes": [], "links": [], "clusters": []}

        nodes = self.graph_data.get("nodes") or []
        links = self.graph_data.get("links") or []
        clusters = self.graph_data.get("clusters") or []

        self._update_stats_display()

        if not nodes:
            self.empty_state_text.visible = True
            self.canvas.shapes.clear()
            self.graph_stack.controls = [self.canvas]
            try:
                self.root_container.update()
            except Exception:
                pass
            return

        self.empty_state_text.visible = False
        # Atualiza a Constelação 3D Esfera Armilar
        self.armillary_3d.set_data(nodes, links, clusters)

        # Calcula coordenadas orgânicas
        compute_graph_layout(nodes, links, width=self.canvas_width, height=self.canvas_height)

        # Monta arestas no Canvas 2D
        filtered_nodes = self._get_filtered_nodes()
        filtered_links = self._get_filtered_links(filtered_nodes)
        self._render_links(filtered_nodes, filtered_links)

        # Monta nós no Stack 2D
        self._render_nodes(filtered_nodes)

        try:
            self.root_container.update()
        except Exception:
            pass

    def _render_links(self, nodes: List[Dict[str, Any]], links: List[Dict[str, Any]]) -> None:
        node_map = {n["id"]: n for n in nodes}
        shapes: list[cv.Shape] = []

        is_dark = (self.current_theme_mode or "dark").lower() == "dark"
        base_color = "#D4AF37" if is_dark else "#896200"

        for l in links:
            s_id = l.get("source")
            t_id = l.get("target")
            s = node_map.get(s_id)
            t = node_map.get(t_id)
            if not s or not t:
                continue

            weight = float(l.get("weight") or 0.5)
            is_highlighted = self.selected_node_id and (
                s_id == self.selected_node_id or t_id == self.selected_node_id
            )

            if is_highlighted:
                stroke_color = base_color
                stroke_width = 3.0 * self.scale
            else:
                stroke_color = f"{base_color}4D"
                stroke_width = max(1.0, weight * 2.5) * self.scale

            shapes.append(
                cv.Line(
                    x1=s["x"],
                    y1=s["y"],
                    x2=t["x"],
                    y2=t["y"],
                    paint=ft.Paint(
                        color=stroke_color,
                        stroke_width=stroke_width,
                    ),
                )
            )

        self.canvas.shapes = shapes

    def _render_nodes(self, nodes: List[Dict[str, Any]]) -> None:
        self.node_containers.clear()
        node_controls: list[ft.Control] = [self.canvas]

        for n in nodes:
            n_id = n["id"]
            node_type = n.get("type") or "fragment"
            is_selected = (n_id == self.selected_node_id)
            node_color = n.get("color") or self.config.colors["gold"]

            # Icon por tipo
            if node_type == "fragment":
                icon = ft.Icons.FORMAT_QUOTE
            elif node_type == "work":
                icon = ft.Icons.MENU_BOOK
            else:
                icon = ft.Icons.HUB

            node_size = 40.0 * self.scale
            circle = ft.Container(
                content=ft.Icon(
                    icon,
                    size=18 * self.scale,
                    color="#FFFFFF",
                ),
                width=node_size,
                height=node_size,
                border_radius=node_size / 2,
                bgcolor=node_color,
                border=ft.Border.all(
                    2 * self.scale,
                    self.config.colors["gold"] if is_selected else self.config.colors["surface"],
                ),
                shadow=ft.BoxShadow(
                    spread_radius=2,
                    blur_radius=10,
                    color=f"{self.config.colors['gold']}88",
                ) if is_selected else None,
                alignment=ft.Alignment(0, 0),
            )

            label_text = n.get("label") or ""
            if len(label_text) > 22:
                label_text = label_text[:20] + "..."

            label_ctrl = ft.Text(
                label_text,
                size=10 * self.scale,
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.W_400,
                color=self.config.colors["gold"] if is_selected else self.config.colors["text"],
                text_align=ft.TextAlign.CENTER,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )

            card_width = 130.0 * self.scale
            node_ctrl = ft.Container(
                left=n["x"] - (card_width / 2.0),
                top=n["y"] - (node_size / 2.0),
                width=card_width,
                content=ft.Column(
                    controls=[circle, label_ctrl],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=3 * self.scale,
                    tight=True,
                ),
                tooltip=f"{n.get('label')}\n{n.get('work_title', '')}",
                on_click=lambda _, target_node=n: self._handle_node_clicked(target_node),
            )

            self.node_containers[n_id] = node_ctrl
            node_controls.append(node_ctrl)

        self.graph_stack.controls = node_controls

    def _handle_toggle_celestial_grid(self, _e: ft.ControlEvent) -> None:
        """Alterna a exibição da grade cartográfica de coordenadas celestes."""
        is_shown = self.armillary_3d.toggle_celestial_grid()
        self.grid_toggle_btn.icon_color = (
            self.config.colors["gold"] if is_shown else self.config.colors["muted"]
        )
        try:
            self.grid_toggle_btn.update()
        except Exception:
            pass

    def _handle_toggle_view_mode(self, _e: ft.ControlEvent) -> None:
        """Alterna entre a Constelação 3D Esfera Armilar e a Malha 2D Plana."""
        if self.view_mode == "3d":
            self.view_mode = "2d"
            self.viewport_container.content = self.interactive_viewer
            self.mode_toggle_btn.content = "Ver Constelação 3D"
            self.mode_toggle_btn.icon = ft.Icons.AUTO_AWESOME
            self.grid_toggle_btn.visible = False
        else:
            self.view_mode = "3d"
            self.viewport_container.content = self.armillary_3d.compose()
            self.mode_toggle_btn.content = "Ver Mapa 2D"
            self.mode_toggle_btn.icon = ft.Icons.GRID_VIEW
            self.grid_toggle_btn.visible = True
        try:
            self.viewport_container.update()
            self.mode_toggle_btn.update()
            self.grid_toggle_btn.update()
        except Exception:
            pass

    def _handle_filter_mode_change(self, e: ft.ControlEvent) -> None:
        """Alterna a camada celeste entre todas as estrelas, apenas obras ou apenas fragmentos."""
        mode = self.filter_mode_dropdown.value or "all"
        self.filter_mode = mode
        self.armillary_3d.set_filter_mode(mode)
        self._update_stats_display()

        if self.view_mode == "2d":
            nodes = self._get_filtered_nodes()
            links = self._get_filtered_links(nodes)
            self._render_links(nodes, links)
            self._render_nodes(nodes)

        try:
            self.root_container.update()
        except Exception:
            pass

    def _handle_node_clicked(self, node: Dict[str, Any]) -> None:
        """Trata seleção de nó e abre o painel lateral de ressonâncias."""
        self.selected_node_id = node.get("id")
        self.armillary_3d.select_node_id(self.selected_node_id)

        # Ajusta centralização da esfera considerando o painel lateral aberto
        vw, vh = self._compute_viewport_dimensions(panel_open=True)
        self.armillary_3d.update_dimensions(vw, vh)

        # Busca ressonâncias semânticas do nó
        node_type = node.get("type") or "fragment"
        entity_id = int(node.get("entity_id") or 0)
        resonances = self.get_resonances(node_type, entity_id, self.min_similarity, 8)

        # Atualiza o painel retrátil
        self.panel.set_node(node, resonances)

        # Re-renderiza conexões destacadas
        nodes = self._get_filtered_nodes()
        links = self._get_filtered_links(nodes)
        self._render_links(nodes, links)
        self._render_nodes(nodes)
        try:
            self.root_container.update()
        except Exception:
            pass

    def _handle_resonance_selected(self, target_node: Dict[str, Any]) -> None:
        """Pivota para outro nó através da lista de ressonâncias."""
        target_id = target_node.get("id")
        nodes = self.graph_data.get("nodes") or []
        found = next((n for n in nodes if n.get("id") == target_id), None)
        if found:
            self._handle_node_clicked(found)
        else:
            self._handle_node_clicked(target_node)

    def _handle_panel_close(self) -> None:
        """Desmarca o nó ao fechar o painel."""
        self.selected_node_id = None
        self.armillary_3d.select_node_id(None)

        # Restaura centralização da esfera considerando o painel lateral fechado
        vw, vh = self._compute_viewport_dimensions(panel_open=False)
        self.armillary_3d.update_dimensions(vw, vh)

        nodes = self._get_filtered_nodes()
        links = self._get_filtered_links(nodes)
        self._render_links(nodes, links)
        self._render_nodes(nodes)
        try:
            self.root_container.update()
        except Exception:
            pass

    def _handle_search_change(self, e: ft.ControlEvent) -> None:
        """Filtra nós por termo em tempo real."""
        query = (self.search_field.value or "").strip().lower()
        nodes = self.graph_data.get("nodes") or []

        for n in nodes:
            n_id = n["id"]
            ctrl = self.node_containers.get(n_id)
            if not ctrl:
                continue
            if not query:
                ctrl.opacity = 1.0
            else:
                full = f"{n.get('label', '')} {n.get('full_text', '')} {n.get('work_title', '')}".lower()
                ctrl.opacity = 1.0 if query in full else 0.2

        try:
            self.graph_stack.update()
        except Exception:
            pass

    def _handle_sensitivity_change(self, e: ft.ControlEvent) -> None:
        """Altera o limiar de similaridade para reconstrução das arestas."""
        try:
            self.min_similarity = float(self.sensitivity_dropdown.value or "0.40")
        except ValueError:
            self.min_similarity = 0.40
        self._refresh_graph()

    def _handle_sync_mesh(self, _e: ft.ControlEvent) -> None:
        """Sincroniza embeddings pendentes e recalcula clusters."""
        try:
            result = self.sync_mesh()
            self._refresh_graph()
            if self.page:
                vec_count = result.get("vectorized", 0)
                clust_count = result.get("clusters", 0)
                snack = ft.SnackBar(
                    ft.Text(f"Malha sincronizada: {vec_count} itens vetorizados, {clust_count} clusters."),
                )
                self.page.overlay.append(snack)
                snack.open = True
                self.page.update()
        except Exception as err:
            if self.page:
                snack = ft.SnackBar(ft.Text(f"Erro ao sincronizar malha: {err}"))
                self.page.overlay.append(snack)
                snack.open = True
                self.page.update()

    def _handle_open_browser_graph(self, _e: ft.ControlEvent) -> None:
        """Exporta e abre visualizador D3.js no navegador padrão."""
        try:
            html_content = generate_graph_html(
                self.graph_data,
                theme_mode=self.current_theme_mode,
                scale=self.scale,
            )
            export_dir = Path("data")
            export_dir.mkdir(exist_ok=True)
            export_file = export_dir / "knowledge_mesh.html"
            export_file.write_text(html_content, encoding="utf-8")

            abs_uri = export_file.resolve().as_uri()
            import webbrowser
            opened = webbrowser.open(abs_uri)
            if not opened and self.page:
                self.page.launch_url(abs_uri)

            if self.page:
                snack = ft.SnackBar(ft.Text("Visualização D3.js aberta no seu navegador."))
                self.page.overlay.append(snack)
                snack.open = True
                self.page.update()
        except Exception as err:
            if self.page:
                snack = ft.SnackBar(ft.Text(f"Erro ao abrir visualização: {err}"))
                self.page.overlay.append(snack)
                snack.open = True
                self.page.update()
