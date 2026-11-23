import math
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional
import flet as ft

from src.configs.settings import COLORS_DARK
from src.utils.types import ViewConfig
from src.views.ui_kit import alpha, s, segmented, serif_text, ui_text
from src.views.knowledge.graph_template import generate_graph_html
from src.views.knowledge.knowledge_panel import KnowledgePanel
from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
from src.utils.ft_responsiveness import Responsive
from src.utils.control_safety import safe_update


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
        for lnk in links:
            s_id = lnk.get("source")
            t_id = lnk.get("target")
            s = node_map.get(s_id)
            t = node_map.get(t_id)
            if s and t and s.get("cluster_id") == t.get("cluster_id"):
                dx = t["x"] - s["x"]
                dy = t["y"] - s["y"]
                dist = math.hypot(dx, dy)
                if dist > 60.0:
                    w = float(lnk.get("weight") or 0.5)
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
        # O visor cósmico tem paleta própria e não herda o tema claro do app.
        self.cosmic_config = replace(config, colors=COLORS_DARK)
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
        self.type_filter = "all"

        # Dimensões dinâmicas calculadas com base no viewport disponível
        init_w, init_h = self._compute_viewport_dimensions()
        self.canvas_width = 1800.0  # Para mapa 2D com pan & zoom
        self.canvas_height = 1200.0
        self._last_avail_w = init_w

        # Sub-painel retrátil de inspeção
        self.panel = KnowledgePanel(
            config=self.cosmic_config,
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

        self.type_filter_control = segmented(
            self.config,
            [
                ("all", "Tudo", None),
                ("works", "Obras", None),
                ("fragments", "Fragmentos", None),
            ],
            "all",
            self._handle_type_filter_change,
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
                size=s(13),
                color=self.config.colors["on_gold"],
            ),
            icon=ft.Icons.SYNC,
            on_click=self._handle_sync_mesh,
            style=ft.ButtonStyle(
                bgcolor=self.config.colors["gold"],
                padding=ft.Padding(s(14), 0, s(14), 0),
            ),
            height=s(40),
        )

        self.d3_button = ft.OutlinedButton(
            content=ft.Text(
                "D3.js",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=s(13),
                color=self.config.colors["text"],
            ),
            icon=ft.Icons.OPEN_IN_BROWSER,
            on_click=self._handle_open_browser_graph,
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, self.config.colors["border"]),
                padding=ft.Padding(s(14), 0, s(14), 0),
            ),
            height=s(40),
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
                        tooltip="Aproximar constelação",
                        icon_size=s(20),
                        icon_color=self.cosmic_config.colors["text"],
                        on_click=lambda _: self.armillary_3d.zoom_in(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ZOOM_OUT,
                        tooltip="Afastar constelação",
                        icon_size=s(20),
                        icon_color=self.cosmic_config.colors["text"],
                        on_click=lambda _: self.armillary_3d.zoom_out(),
                    ),
                    ft.Container(
                        height=1,
                        width=s(22),
                        bgcolor=alpha(
                            self.cosmic_config.colors["gold"], 0.22
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.RESTART_ALT,
                        tooltip="Restaurar visão padronizada",
                        icon_size=s(19),
                        icon_color=self.cosmic_config.colors["text"],
                        on_click=lambda _: self.armillary_3d.reset_view(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.GRID_4X4,
                        tooltip="Exibir ou ocultar a grade celeste",
                        icon_size=s(19),
                        icon_color=self.cosmic_config.colors["text"],
                        on_click=self._handle_toggle_celestial_grid,
                    ),
                ],
                spacing=s(2),
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=alpha(self.cosmic_config.colors["surface"], 0.62),
            border=ft.Border.all(
                1, alpha(self.cosmic_config.colors["gold"], 0.26)
            ),
            border_radius=s(12),
            padding=s(4),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=18,
                color=alpha(self.cosmic_config.colors["black"], 0.45),
            ),
            right=s(24),
            bottom=s(24),
        )

        self._build_cosmic_overlays()

        space_gradient = ft.RadialGradient(
            center=ft.Alignment(0, 0),
            radius=1.25,
            colors=list(COLORS_DARK["space_gradient"]),
        )

        self.viewport_container = ft.Container(
            content=ft.Stack(
                controls=[
                    *self._build_nebula_layers(),
                    self.armillary_3d.compose(),
                    self.cosmic_header,
                    self.legend_container,
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

    def _build_cosmic_overlays(self) -> None:
        """Monta o cabeçalho de telemetria e a legenda sobre o céu profundo."""
        c = self.cosmic_config
        gold = c.colors["gold"]

        self.ov_works_value = ft.Text(
            "0",
            size=13 * self.scale,
            weight=ft.FontWeight.W_700,
            color=c.colors["text"],
            font_family=c.font_families["montserrat"],
        )
        self.ov_links_value = ft.Text(
            "0",
            size=13 * self.scale,
            weight=ft.FontWeight.W_700,
            color=c.colors["text"],
            font_family=c.font_families["montserrat"],
        )
        self.ov_clusters_value = ft.Text(
            "0",
            size=13 * self.scale,
            weight=ft.FontWeight.W_700,
            color=c.colors["text"],
            font_family=c.font_families["montserrat"],
        )

        def stat_label(text: str) -> ft.Text:
            return ft.Text(
                text,
                size=10.5 * self.scale,
                color=c.colors["muted"],
                font_family=c.font_families["montserrat"],
            )

        self.ov_works_label = stat_label("obras")
        self.ov_links_label = stat_label("afinidades")
        self.ov_clusters_label = stat_label("constelações")

        def stat_chip(value: ft.Text, label: ft.Text) -> ft.Container:
            return ft.Container(
                content=ft.Row(
                    controls=[value, label],
                    spacing=s(5),
                    tight=True,
                ),
                bgcolor=alpha(c.colors["surface"], 0.52),
                border=ft.Border.all(1, alpha(gold, 0.16)),
                border_radius=s(999),
                padding=ft.Padding(s(8), s(3), s(10), s(3)),
            )

        self.cosmic_eyebrow = ft.Text(
            "MALHA SEMÂNTICA",
            size=9.5 * self.scale,
            weight=ft.FontWeight.W_700,
            color=alpha(gold, 0.82),
            font_family=c.font_families["montserrat"],
            style=ft.TextStyle(letter_spacing=1.8),
        )
        self.cosmic_title = ft.Text(
            "Constelação do Acervo",
            size=25 * self.scale,
            weight=ft.FontWeight.W_700,
            color=c.colors["text"],
            font_family=c.font_families["cormorant"],
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.cosmic_meta = ft.Text(
            "Sincronize o Acervo para revelar a malha.",
            size=11.5 * self.scale,
            color=c.colors["muted"],
            font_family=c.font_families["montserrat"],
            max_lines=2,
        )
        self.cosmic_header = ft.Container(
            content=ft.Column(
                controls=[
                    self.cosmic_eyebrow,
                    self.cosmic_title,
                    self.cosmic_meta,
                    ft.Row(
                        controls=[
                            stat_chip(self.ov_works_value, self.ov_works_label),
                            stat_chip(self.ov_links_value, self.ov_links_label),
                            stat_chip(self.ov_clusters_value, self.ov_clusters_label),
                        ],
                        spacing=s(6),
                        tight=True,
                    ),
                ],
                spacing=s(5),
                tight=True,
            ),
            left=s(24),
            top=s(18),
            width=s(360),
            padding=ft.Padding(s(16), s(14), s(16), s(14)),
            bgcolor=alpha(c.colors["surface"], 0.58),
            border=ft.Border.all(1, alpha(gold, 0.20)),
            border_radius=s(12),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=22,
                color=alpha(c.colors["black"], 0.38),
            ),
            ignore_interactions=True,
        )

        def legend_dot(color: str) -> ft.Container:
            return ft.Container(
                width=s(7),
                height=s(7),
                bgcolor=color,
                border_radius=s(4),
            )

        def legend_line() -> ft.Container:
            return ft.Container(
                width=s(14),
                height=max(1.0, s(1)),
                bgcolor=alpha(gold, 0.55),
            )

        legend_row = ft.Row(
            controls=[
                legend_dot(gold),
                ft.Text(
                    "obra",
                    size=10.5 * self.scale,
                    color=c.colors["muted"],
                    font_family=c.font_families["montserrat"],
                ),
                ft.Container(width=s(6)),
                legend_dot(c.colors["constellation_node_fragment"]),
                ft.Text(
                    "fragmento",
                    size=10.5 * self.scale,
                    color=c.colors["muted"],
                    font_family=c.font_families["montserrat"],
                ),
                ft.Container(width=s(6)),
                legend_line(),
                ft.Text(
                    "afinidade",
                    size=10.5 * self.scale,
                    color=c.colors["muted"],
                    font_family=c.font_families["montserrat"],
                ),
            ],
            spacing=s(5),
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.legend_container = ft.Container(
            content=ft.Column(
                controls=[
                    legend_row,
                    ft.Text(
                        "Arraste para orbitar · scroll para zoom · clique para inspecionar",
                        size=10 * self.scale,
                        color=alpha(c.colors["muted"], 0.9),
                        font_family=c.font_families["montserrat"],
                        max_lines=1,
                    ),
                ],
                spacing=s(4),
                tight=True,
            ),
            left=s(24),
            bottom=s(24),
            padding=ft.Padding(s(12), s(8), s(12), s(8)),
            bgcolor=alpha(c.colors["surface"], 0.46),
            border=ft.Border.all(1, alpha(gold, 0.14)),
            border_radius=s(10),
            ignore_interactions=True,
        )

    def _build_nebula_layers(self) -> list[ft.Control]:
        """Adiciona profundidade atmosférica sem custo no Canvas 3D."""
        c = self.cosmic_config

        def layer(
            width: float,
            height: float,
            color: str,
            opacity: float,
            left: float | None = None,
            top: float | None = None,
            right: float | None = None,
            bottom: float | None = None,
        ) -> ft.Container:
            return ft.Container(
                width=s(width),
                height=s(height),
                left=s(left) if left is not None else None,
                top=s(top) if top is not None else None,
                right=s(right) if right is not None else None,
                bottom=s(bottom) if bottom is not None else None,
                gradient=ft.RadialGradient(
                    center=ft.Alignment(0, 0),
                    radius=1.0,
                    colors=[
                        alpha(color, opacity),
                        alpha("#050711", 0.0),
                    ],
                ),
                border_radius=s(999),
                ignore_interactions=True,
            )

        return [
            layer(
                620,
                620,
                c.colors["gold"],
                0.10,
                right=-180,
                top=-220,
            ),
            layer(
                720,
                720,
                c.colors["constellation_node_fragment"],
                0.11,
                left=-250,
                bottom=-280,
            ),
            layer(
                420,
                420,
                "#684E72",
                0.07,
                left=320,
                bottom=-120,
            ),
        ]

    def _update_cosmic_overlay(self) -> None:
        """Sincroniza telemetria, legenda e título do cabeçalho cósmico."""
        nodes = self._get_filtered_nodes()
        links = self._get_filtered_links(nodes)
        clusters = self.graph_data.get("clusters") or []
        self.ov_works_value.value = str(len(nodes))
        self.ov_links_value.value = str(len(links))
        self.ov_clusters_value.value = str(len(clusters))
        if self.type_filter == "works":
            self.ov_works_label.value = "obras"
        elif self.type_filter == "fragments":
            self.ov_works_label.value = "fragmentos"
        else:
            self.ov_works_label.value = "nós"

        if not nodes:
            self.cosmic_eyebrow.value = "MALHA SEMÂNTICA"
            self.cosmic_title.value = "Aguardando o primeiro astro"
            self.cosmic_meta.value = (
                "Cadastre obras e fragmentos para revelar a constelação."
            )
        elif not self.selected_node_id:
            self.cosmic_eyebrow.value = "MALHA SEMÂNTICA"
            self.cosmic_title.value = "Constelação do Acervo"
            self.cosmic_meta.value = (
                f"{len(nodes)} obras · {len(links)} afinidades · "
                f"{int(self.min_similarity * 100)}% de sensibilidade"
            )

        self.cosmic_header.visible = bool(nodes)
        self.legend_container.visible = bool(nodes) and self._last_avail_w >= 880
        safe_update(self.cosmic_header)
        safe_update(self.legend_container)

    def _compute_viewport_dimensions(
        self, panel_open: bool = False, is_maximized: Optional[bool] = None
    ) -> tuple[float, float]:
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
        self._last_avail_w = avail_w
        has_nodes = bool(self.graph_data.get("nodes"))
        self.cosmic_header.width = s(360 if avail_w >= 1000 else 300)
        self.legend_container.visible = has_nodes and avail_w >= 880
        self.type_filter_control.visible = avail_w >= 820
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
                size=s(13),
                color=self.config.colors["on_gold"],
            )
            self.d3_button.content = ft.Text(
                "D3.js",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=s(13),
                color=self.config.colors["text"],
            )
            self.controls_row.spacing = s(10)
        elif avail_w >= 920:
            # Modo Médio (Janela Normal Desmaximizada ~1400px - 350px sidebar = 1050px)
            self.subtitle_prefix.visible = False
            self.subtitle_dot.visible = False
            self.search_field.width = s(150)
            self.filter_mode_dropdown.width = s(135)
            self.sensitivity_slider.width = s(100)
            self.sync_button.content = ft.Text(
                "Sincronizar",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=s(12),
                color=self.config.colors["on_gold"],
            )
            self.d3_button.content = ft.Text(
                "D3.js",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=s(12),
                color=self.config.colors["text"],
            )
            self.controls_row.spacing = s(6)
        else:
            # Modo Compacto (Janela Estreita ou Painel Lateral Aberto)
            self.subtitle_prefix.visible = False
            self.subtitle_dot.visible = False
            self.search_field.width = s(115)
            self.filter_mode_dropdown.width = s(110)
            self.sensitivity_slider.width = s(75)
            self.sync_button.content = ft.Text(
                "Sync",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=s(11),
                color=self.config.colors["on_gold"],
            )
            self.d3_button.content = ft.Text(
                "D3",
                font_family=self.config.font_families["montserrat"],
                weight=ft.FontWeight.W_700,
                size=s(11),
                color=self.config.colors["text"],
            )
            self.controls_row.spacing = 4 * self.scale

    def on_window_resized(self, is_maximized: Optional[bool] = None) -> None:
        """Notificado pelo WindowControllerMixin quando a janela muda de tamanho."""
        panel_open = bool(self.panel and self.panel.panel_container and self.panel.panel_container.visible)
        vw, vh = self._compute_viewport_dimensions(panel_open=panel_open, is_maximized=is_maximized)
        self.armillary_3d.update_dimensions(vw, vh)
        self._update_toolbar_responsive(vw)
        safe_update(self.toolbar)
        safe_update(self.viewport_container)
        safe_update(self.root_container)

    def _build_layout(self) -> ft.Control:
        self.controls_row = ft.Row(
            controls=[
                self.search_field,
                self.type_filter_control,
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
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.AUTO_AWESOME_OUTLINED,
                            size=s(42),
                            color=self.cosmic_config.colors["gold"],
                        ),
                        width=s(92),
                        height=s(92),
                        alignment=ft.Alignment(0, 0),
                        border=ft.Border.all(
                            1,
                            alpha(self.cosmic_config.colors["gold"], 0.24),
                        ),
                        border_radius=s(999),
                        bgcolor=alpha(
                            self.cosmic_config.colors["surface"], 0.45
                        ),
                    ),
                    serif_text(
                        self.cosmic_config,
                        "Aguardando o primeiro astro.",
                        size=24,
                        weight=ft.FontWeight.W_700,
                        color=self.cosmic_config.colors["text"],
                    ),
                    ui_text(
                        self.cosmic_config,
                        "Cadastre obras e citações no Acervo para revelar a "
                        "constelação semântica. Se o acervo já existe, "
                        "sincronize a malha para calcular as afinidades.",
                        size=13,
                        weight=ft.FontWeight.W_500,
                        color=self.cosmic_config.colors["muted"],
                        align=ft.TextAlign.CENTER,
                        max_lines=None,
                    ),
                    ft.Container(height=s(8)),
                    ft.FilledButton(
                        content=ft.Text(
                            "Sincronizar Acervo",
                            font_family=self.cosmic_config.font_families[
                                "montserrat"
                            ],
                            weight=ft.FontWeight.W_700,
                            size=s(13),
                            color=self.cosmic_config.colors["on_gold"],
                        ),
                        icon=ft.Icons.BOLT,
                        on_click=self._handle_sync_mesh,
                        style=ft.ButtonStyle(
                            bgcolor=self.cosmic_config.colors["gold"],
                            padding=ft.Padding(s(16), 0, s(16), 0),
                        ),
                        height=s(40),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=s(8),
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
        nodes = all_nodes
        if self.filter_mode.startswith("cluster_"):
            try:
                target_c_id = int(self.filter_mode.split("_")[1])
                nodes = [
                    n for n in nodes if n.get("cluster_id") == target_c_id
                ]
            except Exception:
                nodes = all_nodes
        if self.type_filter == "works":
            nodes = [n for n in nodes if n.get("type") == "work"]
        elif self.type_filter == "fragments":
            nodes = [n for n in nodes if n.get("type") != "work"]
        return nodes

    def _get_filtered_links(self, visible_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        all_links = self.graph_data.get("links") or []
        v_ids = {n["id"] for n in visible_nodes}
        return [lnk for lnk in all_links if lnk.get("source") in v_ids and lnk.get("target") in v_ids]

    def _update_stats_display(self) -> None:
        nodes = self._get_filtered_nodes()
        links = self._get_filtered_links(nodes)
        clusters = self.graph_data.get("clusters") or []
        noun = (
            "Obras"
            if self.type_filter == "works"
            else ("Fragmentos" if self.type_filter == "fragments" else "Nós")
        )
        self.stats_text.value = (
            f"{len(nodes)} {noun} • {len(links)} Afinidades • "
            f"{len(clusters)} Constelações"
        )
        self._update_cosmic_overlay()

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
            safe_update(self.root_container)
            return

        self.empty_state_text.visible = False
        # Atualiza a Constelação 3D Esfera Armilar
        self.armillary_3d.set_data(nodes, links, clusters)

        safe_update(self.root_container)

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
        safe_update(self.root_container)

    def _handle_type_filter_change(self, mode: str) -> None:
        """Alterna entre todos os astros, apenas obras ou apenas fragmentos."""
        self.type_filter = mode if mode in {"all", "works", "fragments"} else "all"
        self.armillary_3d.set_type_filter(self.type_filter)
        self._update_stats_display()
        safe_update(self.root_container)

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

        self.cosmic_eyebrow.value = "NÓ INSPECIONADO"
        self.cosmic_title.value = (
            node.get("title") or node.get("label") or "Nó sem título"
        )
        meta_parts = []
        if node.get("author"):
            meta_parts.append(str(node["author"]))
        if node.get("cluster_name"):
            meta_parts.append(str(node["cluster_name"]))
        if node.get("type") == "work":
            meta_parts.append(
                f"{node.get('fragment_count', 0)} fragmentos"
            )
        self.cosmic_meta.value = " · ".join(meta_parts) or (
            "Selecione outro astro ou feche o painel para voltar à visão geral."
        )
        safe_update(self.cosmic_header)
        safe_update(self.root_container)

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
        self._update_cosmic_overlay()
        safe_update(self.root_container)

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
        safe_update(self.sensitivity_slider_label)

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
                self.page.run_task(self.page.launch_url, abs_uri)

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
