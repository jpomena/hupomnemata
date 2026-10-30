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
    r_x = width * 0.36
    r_y = height * 0.36

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
            dist = 40.0 + (i % 3) * 35.0
            n["x"] = cc_x + dist * math.cos(sub_angle)
            n["y"] = cc_y + dist * math.sin(sub_angle)

    node_map = {n["id"]: n for n in nodes}
    for _ in range(25):
        # 1. Âncora de coesão da constelação
        for n in nodes:
            c_id = n.get("cluster_id") or 0
            cc_x, cc_y = cluster_centers[c_id]
            n["x"] += (cc_x - n["x"]) * 0.12
            n["y"] += (cc_y - n["y"]) * 0.12

        # 2. Repulsão anti-colisão entre nós
        for i in range(len(nodes)):
            n1 = nodes[i]
            for j in range(i + 1, len(nodes)):
                n2 = nodes[j]
                dx = n1["x"] - n2["x"]
                dy = n1["y"] - n2["y"]
                dist = math.hypot(dx, dy)
                if 0 < dist < 90.0:
                    force = (90.0 - dist) / dist * 0.40
                    n1["x"] += dx * force
                    n1["y"] += dy * force
                    n2["x"] -= dx * force
                    n2["y"] -= dy * force

        # 3. Atração por afinidade interna na constelação
        for l in links:
            s_id = l.get("source")
            t_id = l.get("target")
            s = node_map.get(s_id)
            t = node_map.get(t_id)
            if s and t and s.get("cluster_id") == t.get("cluster_id"):
                dx = t["x"] - s["x"]
                dy = t["y"] - s["y"]
                dist = math.hypot(dx, dy)
                if dist > 60.0:
                    w = float(l.get("weight") or 0.5)
                    fx = dx * 0.05 * w
                    fy = dy * 0.05 * w
                    s["x"] += fx
                    s["y"] += fy
                    t["x"] -= fx
                    t["y"] -= fy

        # 4. Limites do canvas
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
        get_work_fragments: Optional[Callable[[int], List[Dict[str, Any]]]] = None,
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
        self.get_work_fragments = get_work_fragments or (lambda _: [])
        self.on_add_to_compilation = on_add_to_compilation
        self.list_compilations = list_compilations
        self.on_create_link = on_create_link
        self.current_theme_mode = current_theme_mode

        self.min_similarity = 0.15
        self.graph_data: Dict[str, Any] = {"nodes": [], "links": [], "clusters": []}
        self.selected_node_id: Optional[str] = None
        self.node_containers: Dict[str, ft.Container] = {}
        self.filter_mode = "all"

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
            hint_text="Buscar obras ou autores...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._handle_search_change,
            border_radius=self.config.ui.get("card_radius", 6),
            height=40 * self.scale,
            text_size=13 * self.scale,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["bg"],
            content_padding=ft.Padding(10, 0, 10, 0),
            width=220 * self.scale,
        )

        self.stats_text = ft.Text(
            "0 Obras • 0 Afinidades • 0 Constelações",
            size=13 * self.scale,
            font_family=self.config.font_families["montserrat"],
            weight=ft.FontWeight.W_600,
            color=self.config.colors["text"],
        )

        self.subtitle_prefix = ft.Text(
            "Constelação de afinidades conceituais do Acervo",
            font_family=self.config.font_families["montserrat"],
            weight=ft.FontWeight.W_600,
            size=13 * self.scale,
            color=self.config.colors["muted"],
        )
        self.subtitle_dot = ft.Text(
            "•",
            font_family=self.config.font_families["montserrat"],
            weight=ft.FontWeight.W_700,
            size=13 * self.scale,
            color=self.config.colors["border"],
        )

        self.filter_mode_dropdown = ft.Dropdown(
            label="Constelação",
            value="all",
            options=[
                ft.dropdown.Option("all", "Todas as Obras"),
            ],
            on_select=self._handle_filter_mode_change,
            width=175 * self.scale,
            height=40 * self.scale,
            text_size=13 * self.scale,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["bg"],
            content_padding=ft.Padding(8, 0, 8, 0),
        )

        # Controle de sensibilidade de ressonância com Slider contínuo
        self.sensitivity_slider_label = ft.Text(
            f"Sensibilidade: {int(self.min_similarity * 100)}%",
            size=12 * self.scale,
            font_family=self.config.font_families["montserrat"],
            weight=ft.FontWeight.W_600,
            color=self.config.colors["text"],
        )
        self.sensitivity_slider = ft.Slider(
            min=0.05,
            max=0.50,
            divisions=45,
            value=self.min_similarity,
            label="{value:.0%}",
            active_color=self.config.colors["gold"],
            inactive_color=self.config.colors["border"],
            on_change=self._handle_sensitivity_slider_live,
            on_change_end=self._handle_sensitivity_slider_change,
            width=150 * self.scale,
        )
        self.sensitivity_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.sensitivity_slider_label,
                    self.sensitivity_slider,
                ],
                spacing=0,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(4, 0, 4, 0),
        )

        self.sync_button = ft.FilledButton(
            content=ft.Text(
                "Sincronizar",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=13 * self.scale,
                color=self.config.colors["bg"],
            ),
            icon=ft.Icons.SYNC,
            on_click=self._handle_sync_mesh,
            style=ft.ButtonStyle(
                bgcolor=self.config.colors["gold"],
                padding=ft.Padding(14 * self.scale, 0, 14 * self.scale, 0),
            ),
            height=40 * self.scale,
        )

        self.d3_button = ft.OutlinedButton(
            content=ft.Text(
                "D3.js",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=13 * self.scale,
                color=self.config.colors["text"],
            ),
            icon=ft.Icons.OPEN_IN_BROWSER,
            on_click=self._handle_open_browser_graph,
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, self.config.colors["border"]),
                padding=ft.Padding(14 * self.scale, 0, 14 * self.scale, 0),
            ),
            height=40 * self.scale,
        )

        # Motor Tridimensional da Constelação Celeste Esfera Armilar
        self.armillary_3d = ArmillaryConstellation3D(
            config=self.config,
            scale=self.scale,
            on_select_node=self._handle_node_clicked,
            current_theme_mode=self.current_theme_mode,
            canvas_width=init_w,
            canvas_height=init_h,
        )

        # HUD flutuante com zoom telescópico, restauração de visão e grade
        # Posicionado com coordenadas explícitas no Stack para jamais ocluir os gestos 3D da esfera
        self.floating_hud = ft.Container(
            content=ft.Column(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ZOOM_IN,
                        tooltip="Aproximar Constelação (Zoom +)",
                        icon_size=20 * self.scale,
                        icon_color="#E2E8F0",
                        on_click=lambda _: self.armillary_3d.zoom_in(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ZOOM_OUT,
                        tooltip="Afastar Constelação (Zoom -)",
                        icon_size=20 * self.scale,
                        icon_color="#E2E8F0",
                        on_click=lambda _: self.armillary_3d.zoom_out(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.RESTART_ALT,
                        tooltip="Restaurar Visão Padrão",
                        icon_size=19 * self.scale,
                        icon_color="#E2E8F0",
                        on_click=lambda _: self.armillary_3d.reset_view(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.GRID_4X4,
                        tooltip="Exibir/Ocultar Grade Celeste",
                        icon_size=19 * self.scale,
                        icon_color="#E2E8F0",
                        on_click=self._handle_toggle_celestial_grid,
                    ),
                ],
                spacing=2,
                tight=True,
            ),
            bgcolor="#0E1322C0",
            border=ft.Border.all(1, "#38BDF830"),
            border_radius=8,
            padding=2,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=10,
                color="#00000050",
            ),
            right=24 * self.scale,
            bottom=24 * self.scale,
        )

        space_gradient = ft.RadialGradient(
            center=ft.Alignment(0, 0),
            radius=1.25,
            colors=["#090D1C", "#050711", "#020306"],
        )

        self.viewport_container = ft.Container(
            content=ft.Stack(
                controls=[
                    self.armillary_3d.compose(),
                    self.floating_hud,
                ],
                expand=True,
            ),
            gradient=space_gradient,
            alignment=ft.Alignment(0, 0),
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        self.root_container = ft.Container(
            expand=True,
            padding=ft.Padding(
                top=self.config.ui["content_top_padding"],
                right=0,
                bottom=0,
                left=0,
            ),
            bgcolor=self.config.colors["surface"],
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=self._build_layout(),
        )

    def _compute_viewport_dimensions(
        self, panel_open: bool = False, is_maximized: Optional[bool] = None
    ) -> Tuple[float, float]:
        """Calcula precisamente a área visível do canvas 3D no dashboard."""
        pw, ph = Responsive.get_page_dimensions(self.page, is_maximized=is_maximized)
        sidebar_w = float(self.config.ui.get("sidebar_width", 350))
        panel_w = (380.0 * self.scale) if panel_open else 0.0

        # Subtrai sidebar, toolbar superior e margens de layout
        avail_w = max(400.0, pw - sidebar_w - panel_w)
        avail_h = max(300.0, ph - 116.0)
        return avail_w, avail_h

    def _update_toolbar_responsive(self, avail_w: float) -> None:
        """Adapta fluidamente os controles da toolbar aos limites da tela tanto no Maximizar quanto no Desmaximizar."""
        if avail_w >= 1220:
            # Modo Amplo (Widescreen / Maximizado)
            self.subtitle_prefix.visible = True
            self.subtitle_dot.visible = True
            self.search_field.width = 200 * self.scale
            self.filter_mode_dropdown.width = 160 * self.scale
            self.sensitivity_slider.width = 130 * self.scale
            self.sync_button.content = ft.Text(
                "Sincronizar",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=13 * self.scale,
                color=self.config.colors["bg"],
            )
            self.d3_button.content = ft.Text(
                "D3.js",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=13 * self.scale,
                color=self.config.colors["text"],
            )
            self.controls_row.spacing = 10 * self.scale
        elif avail_w >= 920:
            # Modo Médio (Janela Normal Desmaximizada ~1400px - 350px sidebar = 1050px)
            self.subtitle_prefix.visible = False
            self.subtitle_dot.visible = False
            self.search_field.width = 150 * self.scale
            self.filter_mode_dropdown.width = 135 * self.scale
            self.sensitivity_slider.width = 100 * self.scale
            self.sync_button.content = ft.Text(
                "Sincronizar",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=12 * self.scale,
                color=self.config.colors["bg"],
            )
            self.d3_button.content = ft.Text(
                "D3.js",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=12 * self.scale,
                color=self.config.colors["text"],
            )
            self.controls_row.spacing = 6 * self.scale
        else:
            # Modo Compacto (Janela Estreita ou Painel Lateral Aberto)
            self.subtitle_prefix.visible = False
            self.subtitle_dot.visible = False
            self.search_field.width = 115 * self.scale
            self.filter_mode_dropdown.width = 110 * self.scale
            self.sensitivity_slider.width = 75 * self.scale
            self.sync_button.content = ft.Text(
                "Sync",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=11 * self.scale,
                color=self.config.colors["bg"],
            )
            self.d3_button.content = ft.Text(
                "D3",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=11 * self.scale,
                color=self.config.colors["text"],
            )
            self.controls_row.spacing = 4 * self.scale

    def on_window_resized(self, is_maximized: Optional[bool] = None) -> None:
        """Notificado pelo WindowControllerMixin quando a janela muda de tamanho."""
        panel_open = bool(self.panel and self.panel.panel_container and self.panel.panel_container.visible)
        vw, vh = self._compute_viewport_dimensions(panel_open=panel_open, is_maximized=is_maximized)
        self.armillary_3d.update_dimensions(vw, vh)
        self._update_toolbar_responsive(vw)
        try:
            self.toolbar.update()
            self.viewport_container.update()
            self.root_container.update()
        except Exception:
            pass

    def _build_layout(self) -> ft.Control:
        self.controls_row = ft.Row(
            controls=[
                self.search_field,
                self.filter_mode_dropdown,
                self.sensitivity_container,
                self.sync_button,
                self.d3_button,
            ],
            spacing=self.config.ui.get("control_gap", 12),
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

        self.toolbar_row = ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text(
                            "Estruturas de Saber",
                            size=self.config.font_sizes["cormorant_big"] * self.scale,
                            font_family=self.config.font_families["cormorant"],
                            weight=ft.FontWeight.W_700,
                            color=self.config.colors["text"],
                        ),
                        ft.Row(
                            controls=[
                                self.subtitle_prefix,
                                self.subtitle_dot,
                                self.stats_text,
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            tight=True,
                        ),
                    ],
                    spacing=2,
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                ),
                self.controls_row,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.toolbar = ft.Container(
            padding=ft.Padding.only(
                left=self.config.ui["header_horizontal_padding"],
                right=self.config.ui["header_horizontal_padding"],
                top=self.config.ui["header_top_padding"],
                bottom=self.config.ui["header_bottom_padding"],
            ),
            content=self.toolbar_row,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        # Empty state placeholder overlay
        self.empty_state_text = ft.Container(
            visible=False,
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.AUTO_AWESOME_OUTLINED,
                        size=48,
                        color=self.config.colors["muted"],
                    ),
                    ft.Text(
                        "Nenhuma obra vetorizada ainda.",
                        size=22 * self.scale,
                        font_family=self.config.font_families["cormorant"],
                        weight=ft.FontWeight.W_700,
                        color=self.config.colors["text"],
                    ),
                    ft.Text(
                        "Cadastre obras e citações no Acervo para construir a malha semântica,\nou clique em 'Sincronizar' para processar o acervo existente.",
                        size=13 * self.scale,
                        font_family=self.config.font_families["montserrat"],
                        weight=ft.FontWeight.W_500,
                        color=self.config.colors["muted"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=8),
                    ft.FilledButton(
                        content=ft.Text(
                            "Sincronizar Agora",
                            font_family=self.config.font_families["montserrat"],
                            weight=ft.FontWeight.W_700,
                            size=13 * self.scale,
                            color=self.config.colors["bg"],
                        ),
                        icon=ft.Icons.BOLT,
                        on_click=self._handle_sync_mesh,
                        style=ft.ButtonStyle(
                            bgcolor=self.config.colors["gold"],
                            padding=ft.Padding(14 * self.scale, 0, 14 * self.scale, 0),
                        ),
                        height=40 * self.scale,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                tight=True,
            ),
            expand=True,
        )

        main_body = ft.Container(
            content=ft.Row(
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
            ),
            border=ft.Border(top=ft.BorderSide(1, self.config.colors["border"])),
            expand=True,
            bgcolor=self.config.colors["bg"],
        )

        return ft.Column(
            controls=[
                self.toolbar,
                main_body,
            ],
            expand=True,
            spacing=self.config.ui["modal_gap"],
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def compose(self) -> ft.Control:
        """Carrega e monta a visualização da malha de conhecimento."""
        panel_open = bool(self.panel and self.panel.panel_container and self.panel.panel_container.visible)
        vw, vh = self._compute_viewport_dimensions(panel_open=panel_open)
        self.armillary_3d.update_dimensions(vw, vh)
        self._update_toolbar_responsive(vw)
        self._refresh_graph()
        return self.root_container

    def _get_filtered_nodes(self) -> List[Dict[str, Any]]:
        all_nodes = self.graph_data.get("nodes") or []
        if self.filter_mode.startswith("cluster_"):
            try:
                target_c_id = int(self.filter_mode.split("_")[1])
                return [n for n in all_nodes if n.get("cluster_id") == target_c_id]
            except Exception:
                return all_nodes
        return all_nodes

    def _get_filtered_links(self, visible_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        all_links = self.graph_data.get("links") or []
        v_ids = {n["id"] for n in visible_nodes}
        return [l for l in all_links if l.get("source") in v_ids and l.get("target") in v_ids]

    def _update_stats_display(self) -> None:
        nodes = self._get_filtered_nodes()
        links = self._get_filtered_links(nodes)
        clusters = self.graph_data.get("clusters") or []
        self.stats_text.value = f"{len(nodes)} Obras • {len(links)} Afinidades • {len(clusters)} Constelações"

    def _refresh_graph(self) -> None:
        """Recarrega os dados do grafo, executa o layout e renderiza nós e arestas."""
        try:
            self.graph_data = self.get_graph_data(self.min_similarity)
        except Exception:
            self.graph_data = {"nodes": [], "links": [], "clusters": []}

        nodes = self.graph_data.get("nodes") or []
        links = self.graph_data.get("links") or []
        clusters = self.graph_data.get("clusters") or []

        # Popula o seletor de Constelações com as constelações existentes
        cluster_options = [ft.dropdown.Option("all", "Todas as Obras")]
        for c in clusters:
            c_name = c.get("name") or f"Constelação {c.get('id')}"
            if len(c_name) > 22:
                c_name = c_name[:20] + "…"
            cluster_options.append(ft.dropdown.Option(f"cluster_{c.get('id')}", c_name))
        self.filter_mode_dropdown.options = cluster_options
        if self.filter_mode not in [o.key for o in cluster_options]:
            self.filter_mode = "all"
            self.filter_mode_dropdown.value = "all"

        self._update_stats_display()

        self.node_containers.clear()
        for n in nodes:
            self.node_containers[n["id"]] = ft.Container(data=n)

        self._update_stats_display()

        if not nodes:
            self.empty_state_text.visible = True
            try:
                self.root_container.update()
            except Exception:
                pass
            return

        self.empty_state_text.visible = False
        # Atualiza a Constelação 3D Esfera Armilar
        self.armillary_3d.set_data(nodes, links, clusters)

        try:
            self.root_container.update()
        except Exception:
            pass

    def _render_links(self, nodes: List[Dict[str, Any]], links: List[Dict[str, Any]]) -> None:
        pass

    def _render_nodes(self, nodes: List[Dict[str, Any]]) -> None:
        pass

    def _handle_toggle_celestial_grid(self, _e: ft.ControlEvent) -> None:
        """Alterna a exibição da grade cartográfica de coordenadas celestes."""
        self.armillary_3d.toggle_celestial_grid()

    def _handle_filter_mode_change(self, e: ft.ControlEvent) -> None:
        """Alterna o filtro por constelação na esfera armilar 3D."""
        mode = self.filter_mode_dropdown.value or "all"
        self.filter_mode = mode
        self.armillary_3d.set_filter_mode(mode)
        self._update_stats_display()
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
        self._update_toolbar_responsive(vw)

        # Busca ressonâncias semânticas da obra e fragmentos associados
        node_type = node.get("type") or "work"
        entity_id = int(node.get("entity_id") or 0)
        resonances = self.get_resonances(node_type, entity_id, self.min_similarity, 8)
        work_fragments = self.get_work_fragments(entity_id) if node_type == "work" else []

        # Atualiza o painel retrátil
        self.panel.set_node(node, resonances, work_fragments=work_fragments)
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
        self._update_toolbar_responsive(vw)
        try:
            self.root_container.update()
        except Exception:
            pass

    def _handle_search_change(self, e: ft.ControlEvent) -> None:
        """Filtra nós por termo de busca e destaca na constelação."""
        query = (self.search_field.value or "").strip().lower()
        nodes = self.graph_data.get("nodes") or []
        for n in nodes:
            n_id = n["id"]
            ctrl = self.node_containers.get(n_id)
            if ctrl:
                full = f"{n.get('label', '')} {n.get('full_text', '')} {n.get('work_title', '')}".lower()
                ctrl.opacity = 1.0 if (not query or query in full) else 0.2

        if query:
            matched = next(
                (
                    n for n in nodes
                    if query in str(n.get("label", "")).lower()
                    or query in str(n.get("author", "")).lower()
                    or query in str(n.get("title", "")).lower()
                ),
                None,
            )
            if matched:
                self.selected_node_id = matched["id"]
                self.armillary_3d.select_node_id(matched["id"])

    def _handle_sensitivity_slider_live(self, e: ft.ControlEvent) -> None:
        """Atualiza dinamicamente o rótulo de sensibilidade durante o arrasto do slider."""
        val = float(e.control.value)
        self.sensitivity_slider_label.value = f"Sensibilidade: {int(val * 100)}%"
        try:
            self.sensitivity_slider_label.update()
        except Exception:
            pass

    def _handle_sensitivity_slider_change(self, e: ft.ControlEvent) -> None:
        """Dispara recálculo da malha de afinidades ao soltar o slider de sensibilidade."""
        val = float(e.control.value)
        self.min_similarity = round(val, 2)
        self.sensitivity_slider_label.value = f"Sensibilidade: {int(val * 100)}%"
        self._refresh_graph()

    def _handle_sync_mesh(self, _e: ft.ControlEvent) -> None:
        """Sincroniza embeddings pendentes e recalcula clusters."""
        try:
            result = self.sync_mesh()
            self._refresh_graph()
            if self.page:
                vec_count = result.get("vectorized", 0)
                clust_count = result.get("clusters", 0)
                total_nodes = len(self.graph_data.get("nodes") or [])
                if vec_count > 0:
                    msg = f"Malha sincronizada: {vec_count} novos itens vetorizados ({total_nodes} obras ativas, {clust_count} constelações)."
                else:
                    msg = f"Malha atualizada: todas as {total_nodes} obras estão vetorizadas em {clust_count} constelações."
                snack = ft.SnackBar(ft.Text(msg))
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
