"""Visualizador 3D da Constelação Celeste no estilo Esfera Armilar / Astrolábio Clássico.
Projeção perspectiva de alta performance com aceleração matemática, grade cartográfica astronômica e anéis armilares.
"""

from collections.abc import Callable
import math
import time
from typing import Any, Dict, List, Optional, Tuple
import flet as ft
import flet.canvas as cv

from src.utils.types import ViewConfig


class ArmillaryConstellation3D:
    """Motor de renderização e interação da Constelação 3D da Esfera Armilar."""

    ZOOM_MIN = 280.0
    ZOOM_MAX = 1200.0

    def __init__(
        self,
        config: ViewConfig,
        scale: float,
        on_select_node: Callable[[Dict[str, Any]], None],
        current_theme_mode: str = "light",
        canvas_width: float = 1600.0,
        canvas_height: float = 1000.0,
    ) -> None:
        self.config = config
        self.scale = scale
        self.on_select_node = on_select_node
        self.current_theme_mode = current_theme_mode
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self._cx = self.canvas_width / 2.0
        self._cy = self.canvas_height / 2.0

        # Modo de filtro celeste: 'all' (todas), 'works' (apenas obras), 'fragments' (apenas fragmentos)
        self.filter_mode: str = "all"

        # Controle de exibição da grade cartográfica de coordenadas celestes
        self.show_celestial_grid: bool = True

        # Ângulos da câmera orbital e zoom
        self.pitch = 0.38  # Inclinação vertical (radianos)
        self.yaw = 0.65    # Rotação horizontal (radianos)
        self.camera_distance = 680.0  # Distância focal / zoom
        self.sphere_radius = min(self.canvas_width, self.canvas_height) * 0.36   # Raio da esfera armilar proporcional

        # Cache de matriz trigonométrica para projeção instantânea O(1)
        self._cos_y = math.cos(self.yaw)
        self._sin_y = math.sin(self.yaw)
        self._cos_p = math.cos(self.pitch)
        self._sin_p = math.sin(self.pitch)
        self._last_render_time: float = 0.0

        # Controle de concorrência e arraste de alta performance
        self._is_dragging: bool = False
        self._is_rendering: bool = False
        self._pending_render: bool = False

        # Dados estruturais do grafo
        self.nodes: List[Dict[str, Any]] = []
        self.links: List[Dict[str, Any]] = []
        self.clusters: List[Dict[str, Any]] = []
        self.selected_node_id: Optional[str] = None
        self.projected_nodes: Dict[str, Tuple[float, float, float]] = {}

        # Geometria 3D pré-computada dos anéis do astrolábio e da grade celeste
        self._precomputed_rings = self._build_armillary_rings_geometry(steps=24)
        self._precomputed_grid = self._build_celestial_grid_geometry(steps=20)
        self._precomputed_ticks = self._build_astrolabe_ticks_geometry()

        # Fundo de poeira estelar (72 partículas cósmicas em espiral áurea com 3 magnitudes)
        self.starfield = self._generate_cosmic_dust(72)

        # Camada de desenho Canvas
        self.canvas = cv.Canvas(
            width=self.canvas_width,
            height=self.canvas_height,
            shapes=[],
        )

        # Detector de gestos para arrasto orbital e zoom
        self.gesture_detector = ft.GestureDetector(
            content=self.canvas,
            on_pan_start=self._handle_pan_start,
            on_pan_update=self._handle_pan_update,
            on_pan_end=self._handle_pan_end,
            on_scroll=self._handle_scroll,
            on_tap_up=self._handle_tap_up,
            expand=True,
        )

    def toggle_celestial_grid(self) -> bool:
        """Alterna a exibição da grade cartográfica celeste e re-renderiza."""
        self.show_celestial_grid = not self.show_celestial_grid
        self.render(high_detail=True)
        return self.show_celestial_grid

    def update_dimensions(self, width: float, height: float) -> None:
        """Ajusta as dimensões do canvas e recalcula o centro de projeção e anéis."""
        if width <= 0 or height <= 0:
            return
        if abs(self.canvas_width - width) < 1.0 and abs(self.canvas_height - height) < 1.0:
            return
        self.canvas_width = width
        self.canvas_height = height
        self._cx = width / 2.0
        self._cy = height / 2.0
        self.canvas.width = width
        self.canvas.height = height
        self.sphere_radius = min(width, height) * 0.36
        self._precomputed_rings = self._build_armillary_rings_geometry(steps=24)
        self._precomputed_grid = self._build_celestial_grid_geometry(steps=20)
        self._precomputed_ticks = self._build_astrolabe_ticks_geometry()
        self.starfield = self._generate_cosmic_dust(72)
        self._compute_3d_coordinates()
        self.render()

    def set_filter_mode(self, mode: str) -> None:
        """Define o filtro de nós ('all', 'works', 'fragments') e re-renderiza."""
        if mode not in {"all", "works", "fragments"}:
            mode = "all"
        if self.filter_mode == mode:
            return
        self.filter_mode = mode
        self._compute_3d_coordinates()
        self.render()

    def _update_rotation_matrix(self) -> None:
        """Pré-calcula funções trigonométricas uma única vez por quadro de renderização."""
        self._cos_y = math.cos(self.yaw)
        self._sin_y = math.sin(self.yaw)
        self._cos_p = math.cos(self.pitch)
        self._sin_p = math.sin(self.pitch)

    def _build_armillary_rings_geometry(self, steps: int = 24) -> List[Tuple[str, List[Tuple[float, float, float]]]]:
        """Gera e armazena em cache a geometria 3D estática dos anéis armilares fundamentais."""
        r = self.sphere_radius
        rings: List[Tuple[str, List[Tuple[float, float, float]]]] = []

        # 1. Anel Equatorial (Plano XZ, Y = 0)
        equator = [
            (r * math.cos(i * 2 * math.pi / steps), 0.0, r * math.sin(i * 2 * math.pi / steps))
            for i in range(steps + 1)
        ]
        rings.append(("equator", equator))

        # 2. Meridiano Principal (Plano XY, Z = 0)
        meridian = [
            (r * math.cos(i * 2 * math.pi / steps), r * math.sin(i * 2 * math.pi / steps), 0.0)
            for i in range(steps + 1)
        ]
        rings.append(("meridian", meridian))

        # 3. Coluro Solsticial (Plano YZ, X = 0)
        colure = [
            (0.0, r * math.cos(i * 2 * math.pi / steps), r * math.sin(i * 2 * math.pi / steps))
            for i in range(steps + 1)
        ]
        rings.append(("colure", colure))

        # 4. Eclíptica Zodiacal (Inclinada 23.4° em relação ao equador)
        ecliptic_tilt = 23.4 * (math.pi / 180.0)
        sin_tilt = math.sin(ecliptic_tilt)
        cos_tilt = math.cos(ecliptic_tilt)
        ecliptic = [
            (
                r * 1.02 * math.cos(i * 2 * math.pi / steps),
                r * 1.02 * math.sin(i * 2 * math.pi / steps) * sin_tilt,
                r * 1.02 * math.sin(i * 2 * math.pi / steps) * cos_tilt,
            )
            for i in range(steps + 1)
        ]
        rings.append(("ecliptic", ecliptic))

        return rings

    def _build_celestial_grid_geometry(self, steps: int = 20) -> List[Tuple[str, List[Tuple[float, float, float]]]]:
        """Gera a grade cartográfica celeste: paralelos de declinação e meridianos de ascensão reta."""
        r = self.sphere_radius * 0.99
        grid_lines: List[Tuple[str, List[Tuple[float, float, float]]]] = []

        # 1. Paralelos de Declinação (-60°, -30°, +30°, +60°)
        declinations = [-60.0, -30.0, 30.0, 60.0]
        for dec_deg in declinations:
            dec_rad = dec_deg * (math.pi / 180.0)
            r_parallel = r * math.cos(dec_rad)
            y_parallel = r * math.sin(dec_rad)
            parallel_pts = [
                (
                    r_parallel * math.cos(i * 2 * math.pi / steps),
                    y_parallel,
                    r_parallel * math.sin(i * 2 * math.pi / steps),
                )
                for i in range(steps + 1)
            ]
            grid_lines.append((f"parallel_{int(dec_deg)}", parallel_pts))

        # 2. Meridianos de Ascensão Reta (8 meridianos divididos a cada 45°)
        meridian_count = 8
        lat_steps = 14
        for m_idx in range(meridian_count):
            ra_angle = m_idx * (2 * math.pi / meridian_count)
            cos_ra = math.cos(ra_angle)
            sin_ra = math.sin(ra_angle)
            meridian_pts = []
            for j in range(lat_steps + 1):
                lat_rad = -math.pi / 2.0 + (j * math.pi / lat_steps)
                cos_lat = math.cos(lat_rad)
                sin_lat = math.sin(lat_rad)
                meridian_pts.append((
                    r * cos_lat * cos_ra,
                    r * sin_lat,
                    r * cos_lat * sin_ra,
                ))
            grid_lines.append((f"ra_meridian_{m_idx}", meridian_pts))

        return grid_lines

    def _build_astrolabe_ticks_geometry(self) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
        """Gera marcas astronômicas de graduação ao longo do Equador e da Eclíptica."""
        r = self.sphere_radius
        ticks: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []

        # Ticks no anel equatorial a cada 15 graus (24 divisões horárias astronômicas)
        for i in range(24):
            angle = i * (2 * math.pi / 24)
            ca = math.cos(angle)
            sa = math.sin(angle)
            p1 = (r * 0.985 * ca, 0.0, r * 0.985 * sa)
            p2 = (r * 1.025 * ca, 0.0, r * 1.025 * sa)
            ticks.append((p1, p2))

        # Ticks na Eclíptica (12 divisões zodiacais)
        ecliptic_tilt = 23.4 * (math.pi / 180.0)
        sin_tilt = math.sin(ecliptic_tilt)
        cos_tilt = math.cos(ecliptic_tilt)
        for i in range(12):
            angle = i * (2 * math.pi / 12)
            ca = math.cos(angle)
            sa = math.sin(angle)
            p1 = (
                r * 1.005 * ca,
                r * 1.005 * sa * sin_tilt,
                r * 1.005 * sa * cos_tilt,
            )
            p2 = (
                r * 1.045 * ca,
                r * 1.045 * sa * sin_tilt,
                r * 1.045 * sa * cos_tilt,
            )
            ticks.append((p1, p2))

        return ticks

    def _generate_cosmic_dust(self, count: int = 72) -> List[Tuple[float, float, float, float, float, int]]:
        """Gera partículas estelares de fundo na esfera exterior com 3 magnitudes estelares."""
        dust: List[Tuple[float, float, float, float, float, int]] = []
        golden_ratio = (1.0 + math.sqrt(5.0)) / 2.0
        r = self.sphere_radius * 1.40

        for i in range(count):
            theta = 2.0 * math.pi * i / golden_ratio
            phi = math.acos(max(-1.0, min(1.0, 1.0 - 2.0 * (i + 0.5) / count)))
            x = r * math.sin(phi) * math.cos(theta)
            y = r * math.cos(phi)
            z = r * math.sin(phi) * math.sin(theta)

            # Hierarquia de 3 magnitudes celestes
            if i < 14:
                magnitude = 1  # Estrela Principal / Guia
                brightness = 0.85
                base_radius = 2.2
            elif i < 38:
                magnitude = 2  # Estrela Média
                brightness = 0.58
                base_radius = 1.4
            else:
                magnitude = 3  # Poeira Estelar Fina
                brightness = 0.35
                base_radius = 0.85

            dust.append((x, y, z, brightness, base_radius, magnitude))
        return dust

    def set_data(
        self,
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]],
        clusters: List[Dict[str, Any]],
    ) -> None:
        """Configura os nós e arestas calculando posições tridimensionais celestes."""
        self.nodes = nodes
        self.links = links
        self.clusters = clusters

        self._compute_3d_coordinates()
        self.render()

    def _compute_3d_coordinates(self) -> None:
        """Posiciona as obras e fragmentos em constelações na esfera celeste 3D."""
        if not self.nodes:
            return

        cluster_map: Dict[int, List[Dict[str, Any]]] = {}
        for n in self.nodes:
            c_id = n.get("cluster_id") or 0
            cluster_map.setdefault(c_id, []).append(n)

        num_clusters = len(cluster_map)
        cluster_centers: Dict[int, Tuple[float, float, float]] = {}

        for idx, c_id in enumerate(cluster_map.keys()):
            theta = (idx / max(1, num_clusters)) * 2.0 * math.pi
            declination = ((idx % 3) - 1.0) * (math.pi / 5.0)  # Zonas celestes (-36°, 0°, +36°)
            r = self.sphere_radius * 0.85
            cx = r * math.cos(declination) * math.cos(theta)
            cy = r * math.sin(declination)
            cz = r * math.cos(declination) * math.sin(theta)
            cluster_centers[c_id] = (cx, cy, cz)

        for c_id, c_nodes in cluster_map.items():
            cc_x, cc_y, cc_z = cluster_centers[c_id]
            works = [n for n in c_nodes if n.get("type") == "work"]
            fragments = [n for n in c_nodes if n.get("type") != "work"]

            if self.filter_mode == "works":
                for w_idx, work in enumerate(works):
                    offset_angle = (w_idx / max(1, len(works))) * 2.0 * math.pi
                    dist = 25.0 + (w_idx * 35.0)
                    work["x3"] = cc_x + dist * math.cos(offset_angle)
                    work["y3"] = cc_y + (w_idx % 2 * 20.0 - 10.0)
                    work["z3"] = cc_z + dist * math.sin(offset_angle)
            elif self.filter_mode == "fragments":
                for f_idx, frag in enumerate(fragments):
                    angle = (f_idx / max(1, len(fragments))) * 2.0 * math.pi
                    tilt = math.sin(f_idx * 0.8) * 0.4
                    orbit_r = 30.0 + (f_idx % 5) * 32.0
                    frag["x3"] = cc_x + orbit_r * math.cos(angle)
                    frag["y3"] = cc_y + orbit_r * tilt
                    frag["z3"] = cc_z + orbit_r * math.sin(angle)
            else:
                # Obras atuam como estrelas principais da constelação (Alfa/Beta)
                for w_idx, work in enumerate(works):
                    offset_angle = (w_idx / max(1, len(works))) * 2.0 * math.pi
                    dist = 40.0 + (w_idx * 30.0)
                    work["x3"] = cc_x + dist * math.cos(offset_angle)
                    work["y3"] = cc_y + (w_idx % 2 * 20.0 - 10.0)
                    work["z3"] = cc_z + dist * math.sin(offset_angle)

                # Fragmentos orbitam como estrelas satélites da constelação
                for f_idx, frag in enumerate(fragments):
                    angle = (f_idx / max(1, len(fragments))) * 2.0 * math.pi
                    tilt = math.sin(f_idx * 0.8) * 0.4
                    orbit_r = 60.0 + (f_idx % 4) * 35.0
                    frag["x3"] = cc_x + orbit_r * math.cos(angle)
                    frag["y3"] = cc_y + orbit_r * tilt
                    frag["z3"] = cc_z + orbit_r * math.sin(angle)

    def _project_point(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Aplica rotação orbital 3D e projeção perspectiva cônica na tela de forma ultra-otimizada."""
        # Rotação Y (Yaw) usando trig pré-calculada
        x1 = x * self._cos_y + z * self._sin_y
        z1 = -x * self._sin_y + z * self._cos_y

        # Rotação X (Pitch)
        y2 = y * self._cos_p - z1 * self._sin_p
        z2 = y * self._sin_p + z1 * self._cos_p

        # Projeção de perspectiva
        depth = z2 + self.camera_distance
        if depth < 50.0:
            depth = 50.0

        factor = 520.0 / depth
        return self._cx + x1 * factor, self._cy + y2 * factor, z2

    def render(self, high_detail: bool = True) -> None:
        """Renderiza todas as camadas da Esfera Armilar e constelação no Canvas com máxima performance."""
        if self._is_rendering:
            self._pending_render = True
            return

        self._is_rendering = True
        try:
            self._update_rotation_matrix()

            is_dark = (self.current_theme_mode or "dark").lower() == "dark"

            # Cores centralizadas provenientes de src/configs/params.json (Zero grená)
            ring_color = self.config.colors.get("constellation_ring", "#C5A059" if is_dark else "#7A5C00")
            grid_color = self.config.colors.get("constellation_grid", "#A89260" if is_dark else "#8C733E")
            grid_tick_color = self.config.colors.get("constellation_grid_tick", "#C5A059" if is_dark else "#7A5C00")
            work_node_color = self.config.colors.get("constellation_node_work", "#E5C158" if is_dark else "#5C4600")
            frag_node_color = self.config.colors.get("constellation_node_fragment", "#7E9DB5" if is_dark else "#3D5A73")
            filament_color = self.config.colors.get("constellation_filament", "#C5A059" if is_dark else "#8C733E")
            star_dust_color = self.config.colors.get("star_dust", "#E2E1E8" if is_dark else "#86868F")
            text_color = self.config.colors.get("text", "#E2E1E8" if is_dark else "#1D1D21")

            shapes: list[cv.Shape] = []

            # 1. Poeira Estelar Sideral de Fundo com 3 magnitudes discretas
            dust_points = self.starfield if high_detail else self.starfield[:24]
            for x, y, z, bright, base_r, mag in dust_points:
                sx, sy, sz = self._project_point(x, y, z)
                depth_scale = 520.0 / max(80.0, sz + self.camera_distance)
                r_proj = max(0.6, base_r * depth_scale)

                # Estrela principal com leve halo no escuro
                if mag == 1 and is_dark and high_detail:
                    shapes.append(
                        cv.Circle(
                            x=sx,
                            y=sy,
                            radius=r_proj * 2.2,
                            paint=ft.Paint(color=f"{star_dust_color}30"),
                        )
                    )

                dust_alpha = int(max(0.15, min(0.85, bright)) * 255)
                alpha_hex = f"{dust_alpha:02X}"
                shapes.append(
                    cv.Circle(
                        x=sx,
                        y=sy,
                        radius=r_proj,
                        paint=ft.Paint(color=f"{star_dust_color}{alpha_hex}"),
                    )
                )

            # 2. Grade Cartográfica Celeste Posterior (Z < 0)
            if self.show_celestial_grid:
                self._render_celestial_grid(shapes, grid_color, draw_front=False, high_detail=high_detail)

            # 3. Anéis da Esfera Armilar — Metade Posterior (Z < 0)
            self._render_armillary_rings(shapes, ring_color, ring_color, draw_front=False, high_detail=high_detail)

            # Filtragem por camada celeste ('all', 'works', 'fragments')
            if self.filter_mode == "works":
                visible_nodes = [n for n in self.nodes if n.get("type") == "work"]
            elif self.filter_mode == "fragments":
                visible_nodes = [n for n in self.nodes if n.get("type") != "work"]
            else:
                visible_nodes = self.nodes

            visible_ids = {n["id"] for n in visible_nodes}

            # 4. Projeção de Nós Visíveis
            self.projected_nodes.clear()
            node_depths: List[Tuple[float, Dict[str, Any], float, float]] = []

            for node in visible_nodes:
                n_id = node["id"]
                x3 = node.get("x3", 0.0)
                y3 = node.get("y3", 0.0)
                z3 = node.get("z3", 0.0)
                sx, sy, sz = self._project_point(x3, y3, z3)
                self.projected_nodes[n_id] = (sx, sy, sz)
                node_depths.append((sz, node, sx, sy))

            # 5. Filamentos de Luz Constelares (Arestas entre nós visíveis)
            for link in self.links:
                s_id = link.get("source")
                t_id = link.get("target")
                if s_id not in visible_ids or t_id not in visible_ids:
                    continue
                if s_id not in self.projected_nodes or t_id not in self.projected_nodes:
                    continue

                weight = float(link.get("weight") or 0.5)
                is_connected_to_selection = self.selected_node_id and (
                    s_id == self.selected_node_id or t_id == self.selected_node_id
                )

                if not high_detail and not is_connected_to_selection and weight < 0.45:
                    continue

                sx1, sy1, sz1 = self.projected_nodes[s_id]
                sx2, sy2, sz2 = self.projected_nodes[t_id]

                avg_z = (sz1 + sz2) / 2.0
                depth_scale = 520.0 / max(100.0, avg_z + self.camera_distance)

                if is_connected_to_selection:
                    stroke_color = ring_color
                    stroke_width = max(1.5, 3.2 * depth_scale) * self.scale
                else:
                    stroke_color = filament_color
                    stroke_width = max(0.8, weight * 2.0 * depth_scale) * self.scale

                shapes.append(
                    cv.Line(
                        x1=sx1,
                        y1=sy1,
                        x2=sx2,
                        y2=sy2,
                        paint=ft.Paint(
                            color=stroke_color,
                            stroke_width=stroke_width,
                        ),
                    )
                )

            # 6. Ordenação de Nós por Profundidade (Painter's Algorithm)
            node_depths.sort(key=lambda item: item[0])

            for sz, node, sx, sy in node_depths:
                n_id = node["id"]
                node_type = node.get("type") or "fragment"
                is_selected = (n_id == self.selected_node_id)
                depth_scale = 520.0 / max(80.0, sz + self.camera_distance)

                if node_type == "work":
                    node_color = node.get("color") or work_node_color
                    corona_r = (22.0 if is_selected else 16.0) * depth_scale * self.scale
                    core_r = (8.0 if is_selected else 6.0) * depth_scale * self.scale

                    # Auréola de corona nobre
                    shapes.append(
                        cv.Circle(
                            x=sx,
                            y=sy,
                            radius=corona_r,
                            paint=ft.Paint(color=f"{node_color}30"),
                        )
                    )
                    # Núcleo estelar
                    shapes.append(
                        cv.Circle(
                            x=sx,
                            y=sy,
                            radius=core_r,
                            paint=ft.Paint(color=node_color),
                        )
                    )
                    # Rótulo de texto: Cormorant Garamond (Conteúdo Intelectual/Literário da Obra)
                    if high_detail or is_selected:
                        label_text = node.get("label") or node.get("title") or ""
                        if len(label_text) > 22:
                            label_text = label_text[:20] + "…"
                        shapes.append(
                            cv.Text(
                                x=sx + core_r + 4.0,
                                y=sy - 5.0,
                                value=label_text,
                                style=ft.TextStyle(
                                    size=max(8.0, 11.5 * depth_scale * self.scale),
                                    font_family=self.config.font_families.get("cormorant", "Cormorant Garamond"),
                                    weight=ft.FontWeight.W_700 if is_selected else ft.FontWeight.W_500,
                                    color=ring_color if is_selected else text_color,
                                ),
                            )
                        )
                else:
                    node_color = node.get("color") or frag_node_color
                    core_r = (5.5 if is_selected else 3.5) * depth_scale * self.scale

                    if is_selected:
                        shapes.append(
                            cv.Circle(
                                x=sx,
                                y=sy,
                                radius=core_r * 2.2,
                                paint=ft.Paint(color=f"{ring_color}45"),
                            )
                        )

                    shapes.append(
                        cv.Circle(
                            x=sx,
                            y=sy,
                            radius=core_r,
                            paint=ft.Paint(color=ring_color if is_selected else node_color),
                        )
                    )

            # 7. Grade Cartográfica Celeste Anterior (Z >= 0)
            if self.show_celestial_grid:
                self._render_celestial_grid(shapes, grid_color, draw_front=True, high_detail=high_detail)
                self._render_astrolabe_ticks(shapes, grid_tick_color, high_detail=high_detail)

            # 8. Anéis da Esfera Armilar — Metade Anterior (Z >= 0)
            self._render_armillary_rings(shapes, ring_color, ring_color, draw_front=True, high_detail=high_detail)

            self.canvas.shapes = shapes
            try:
                self.canvas.update()
            except Exception:
                pass
        finally:
            self._is_rendering = False

    def _render_armillary_rings(
        self,
        shapes: list[cv.Shape],
        color_back: str,
        color_front: str,
        draw_front: bool,
        high_detail: bool = True,
    ) -> None:
        """Desenha os anéis astronômicos clássicos da Esfera Armilar utilizando geometria em cache."""
        rings_to_draw = self._precomputed_rings if high_detail else [
            r for r in self._precomputed_rings if r[0] in ("equator", "ecliptic")
        ]
        step_stride = 1 if high_detail else 2

        for ring_name, pts in rings_to_draw:
            sub_pts = pts[::step_stride]
            if sub_pts[-1] != pts[-1]:
                sub_pts.append(pts[-1])
            proj = [self._project_point(p[0], p[1], p[2]) for p in sub_pts]
            stroke_base = 1.4 if ring_name == "ecliptic" else 1.1

            for i in range(len(proj) - 1):
                sx1, sy1, sz1 = proj[i]
                sx2, sy2, sz2 = proj[i + 1]

                avg_z = (sz1 + sz2) / 2.0
                is_front = avg_z >= 0.0

                if is_front == draw_front:
                    paint_color = color_front if is_front else color_back
                    stroke_w = (stroke_base if is_front else 0.7) * self.scale
                    shapes.append(
                        cv.Line(
                            x1=sx1,
                            y1=sy1,
                            x2=sx2,
                            y2=sy2,
                            paint=ft.Paint(
                                color=paint_color,
                                stroke_width=stroke_w,
                            ),
                        )
                    )

    def _render_celestial_grid(
        self,
        shapes: list[cv.Shape],
        color: str,
        draw_front: bool,
        high_detail: bool = True,
    ) -> None:
        """Desenha a malha cartográfica renascentista de coordenadas celestes (paralelos e meridianos)."""
        stride = 1 if high_detail else 2
        for line_name, pts in self._precomputed_grid:
            sub_pts = pts[::stride]
            if sub_pts[-1] != pts[-1]:
                sub_pts.append(pts[-1])
            proj = [self._project_point(p[0], p[1], p[2]) for p in sub_pts]

            for i in range(len(proj) - 1):
                sx1, sy1, sz1 = proj[i]
                sx2, sy2, sz2 = proj[i + 1]
                avg_z = (sz1 + sz2) / 2.0
                is_front = avg_z >= 0.0
                if is_front == draw_front:
                    stroke_w = (0.65 if is_front else 0.45) * self.scale
                    shapes.append(
                        cv.Line(
                            x1=sx1,
                            y1=sy1,
                            x2=sx2,
                            y2=sy2,
                            paint=ft.Paint(
                                color=color,
                                stroke_width=stroke_w,
                            ),
                        )
                    )

    def _render_astrolabe_ticks(
        self,
        shapes: list[cv.Shape],
        color: str,
        high_detail: bool = True,
    ) -> None:
        """Desenha as graduações astronômicas de astrolábio nos anéis da frente."""
        ticks_to_draw = self._precomputed_ticks if high_detail else self._precomputed_ticks[::2]
        for p1, p2 in ticks_to_draw:
            sx1, sy1, sz1 = self._project_point(p1[0], p1[1], p1[2])
            sx2, sy2, sz2 = self._project_point(p2[0], p2[1], p2[2])
            if (sz1 + sz2) / 2.0 >= 0.0:  # Apenas metade anterior visível
                shapes.append(
                    cv.Line(
                        x1=sx1,
                        y1=sy1,
                        x2=sx2,
                        y2=sy2,
                        paint=ft.Paint(
                            color=color,
                            stroke_width=0.9 * self.scale,
                        ),
                    )
                )

    def _handle_pan_start(self, _e: ft.DragStartEvent) -> None:
        """Sinaliza início de interação de arraste contínuo."""
        self._is_dragging = True

    def _handle_pan_end(self, _e: ft.DragEndEvent) -> None:
        """Ao soltar o mouse, renderiza o quadro final em qualidade total com todos os rótulos de texto."""
        self._is_dragging = False
        self.render(high_detail=True)

    def _handle_pan_update(self, e: ft.DragUpdateEvent) -> None:
        """Controla a rotação 360° orbital contínua com guarda de reentrância e taxa dinâmica."""
        self._is_dragging = True
        local_delta = getattr(e, "local_delta", None)
        if local_delta is not None:
            dx = getattr(local_delta, "x", 0.0) or 0.0
            dy = getattr(local_delta, "y", 0.0) or 0.0
        else:
            dx = getattr(e, "delta_x", 0.0) or 0.0
            dy = getattr(e, "delta_y", 0.0) or 0.0

        self.yaw += dx * 0.0075
        self.pitch += dy * 0.0075
        self.pitch = max(-math.pi / 2.2, min(math.pi / 2.2, self.pitch))

        if self._is_rendering:
            return

        now = time.perf_counter()
        if now - self._last_render_time < 0.028:
            return

        self._last_render_time = now
        self.render(high_detail=False)

    def _handle_scroll(self, e: ft.ScrollEvent) -> None:
        """Controla o zoom telescópico aproximando ou afastando a câmera da esfera."""
        delta = getattr(e, "scroll_delta_y", 0.0) or 0.0
        self.camera_distance += delta * 0.4
        self.camera_distance = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.camera_distance))
        self.render()

    def _handle_tap_up(self, e: ft.TapEvent) -> None:
        """Detecta seleção por clique na estrela mais próxima da linha de visada."""
        tap_x = 0.0
        tap_y = 0.0

        local_pos = getattr(e, "local_position", None)
        if local_pos is not None:
            tap_x = getattr(local_pos, "x", 0.0) or 0.0
            tap_y = getattr(local_pos, "y", 0.0) or 0.0
        else:
            tap_x = getattr(e, "local_x", 0.0) or 0.0
            tap_y = getattr(e, "local_y", 0.0) or 0.0

        best_node = None
        min_dist = 28.0 * self.scale

        for node_id, (sx, sy, sz) in self.projected_nodes.items():
            dist = math.hypot(tap_x - sx, tap_y - sy)
            if dist < min_dist:
                min_dist = dist
                best_node = next((n for n in self.nodes if n["id"] == node_id), None)

        if best_node:
            self.selected_node_id = best_node["id"]
            self.on_select_node(best_node)
            self.render()

    def reset_view(self) -> None:
        """Retorna a visão orbital da esfera para o ângulo clássico renascentista."""
        self.pitch = 0.38
        self.yaw = 0.65
        self.camera_distance = 680.0
        self.selected_node_id = None
        self.render()

    def select_node_id(self, node_id: Optional[str]) -> None:
        """Define o nó selecionado e atualiza a constelação."""
        self.selected_node_id = node_id
        self.render()

    def compose(self) -> ft.Control:
        """Retorna o controle Flet empacotado para inserção na interface."""
        return self.gesture_detector
