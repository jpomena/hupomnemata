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

        # Geometria 3D pré-computada dos anéis do astrolábio e da grade celeste (alta curvatura contínua 96/72 passos)
        self._precomputed_rings = self._build_armillary_rings_geometry(steps=96)
        self._precomputed_grid = self._build_celestial_grid_geometry(steps=72)
        self._precomputed_ticks = self._build_astrolabe_ticks_geometry()

        # Tipografia canônica do aplicativo (Cormorant Garamond para títulos de obras, Montserrat para UI)
        self.font_family = self.config.font_families.get("cormorant", "Cormorant Garamond")
        self.font_family_ui = self.config.font_families.get("montserrat", "Montserrat")

        # Tapeçaria Cósmica Estelar: firmamento tridimensional com Via Láctea, estrelas espectrais e nebulosas
        self.starfield = self._generate_cosmic_dust(72)
        self.milky_way_stream = self._generate_milky_way_stream(160)
        self.nebulae = self._generate_nebulae()

        # Camada de desenho Canvas
        self.canvas = cv.Canvas(
            width=self.canvas_width,
            height=self.canvas_height,
            shapes=[],
        )

        # Detector de gestos para arrasto orbital e zoom com taxa travada a 60 FPS
        self.gesture_detector = ft.GestureDetector(
            content=self.canvas,
            mouse_cursor=ft.MouseCursor.GRAB,
            drag_interval=12,
            on_pan_start=self._handle_pan_start,
            on_pan_update=self._handle_pan_update,
            on_pan_end=self._handle_pan_end,
            on_pan_cancel=self._handle_pan_cancel,
            on_scroll=self._handle_scroll,
            on_tap_up=self._handle_tap_up,
            expand=True,
            left=0,
            top=0,
            right=0,
            bottom=0,
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
        self._precomputed_rings = self._build_armillary_rings_geometry(steps=96)
        self._precomputed_grid = self._build_celestial_grid_geometry(steps=72)
        self._precomputed_ticks = self._build_astrolabe_ticks_geometry()
        self.starfield = self._generate_cosmic_dust(72)
        self.milky_way_stream = self._generate_milky_way_stream(160)
        self.nebulae = self._generate_nebulae()
        self._compute_3d_coordinates()
        self.render()

    def set_font_family(self, family_key: str) -> None:
        """Permite alternar entre as fontes canônicas do app: Cormorant Garamond e Montserrat."""
        if family_key.lower().startswith("montserrat"):
            self.font_family = self.config.font_families.get("montserrat", "Montserrat")
        else:
            self.font_family = self.config.font_families.get("cormorant", "Cormorant Garamond")
        self.render(high_detail=True)

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

    def _build_armillary_rings_geometry(self, steps: int = 96) -> List[Tuple[str, List[Tuple[float, float, float]]]]:
        """Gera e armazena em cache a geometria 3D estática dos anéis armilares fundamentais com 96 passos circulares."""
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

    def _build_celestial_grid_geometry(self, steps: int = 72) -> List[Tuple[str, List[Tuple[float, float, float]]]]:
        """Gera a grade cartográfica celeste: paralelos de declinação e meridianos de ascensão reta com 72 passos."""
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
        lat_steps = 36
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
        """Gera partículas estelares do firmamento com 3 magnitudes e distribuição harmônica em Fibonacci."""
        dust: List[Tuple[float, float, float, float, float, int]] = []
        golden_ratio = (1.0 + math.sqrt(5.0)) / 2.0
        r = self.sphere_radius * 1.42

        for i in range(count):
            # Variação radial sutil de profundidade na abóboda
            r_layer = r * (0.95 + ((i * 19) % 17) * 0.012)
            theta = 2.0 * math.pi * i / golden_ratio
            phi = math.acos(max(-1.0, min(1.0, 1.0 - 2.0 * (i + 0.5) / count)))
            x = r_layer * math.sin(phi) * math.cos(theta)
            y = r_layer * math.cos(phi)
            z = r_layer * math.sin(phi) * math.sin(theta)

            # Hierarquia de 3 magnitudes celestes com diâmetros e intensidades estelares
            if i < 14:
                magnitude = 1  # Estrela Principal / Guia Majestosa com cruz de difração
                brightness = 0.95
                base_radius = 2.4
            elif i < 38:
                magnitude = 2  # Estrela Média
                brightness = 0.65
                base_radius = 1.5
            else:
                magnitude = 3  # Poeira Estelar Fina
                brightness = 0.38
                base_radius = 0.90

            dust.append((x, y, z, brightness, base_radius, magnitude))
        return dust

    def _generate_milky_way_stream(self, count: int = 160) -> List[Tuple[float, float, float]]:
        """Gera o rio de poeira cósmica da Via Láctea em plano galáctico inclinado a 58°."""
        milky_way: List[Tuple[float, float, float]] = []
        r = self.sphere_radius * 1.46
        tilt = 58.0 * (math.pi / 180.0)
        sin_t = math.sin(tilt)
        cos_t = math.cos(tilt)

        for i in range(count):
            angle = 2.0 * math.pi * (i / count)
            # Dispersão pseudo-randômica harmônica (determinística)
            disp_rad = ((i * 17) % 23 - 11.0) * 0.016 * r
            disp_lat = ((i * 13) % 19 - 9.5) * 0.022 * r
            rad = r + disp_rad
            ca = math.cos(angle)
            sa = math.sin(angle)
            x = rad * ca
            y = rad * sa * sin_t + disp_lat
            z = rad * sa * cos_t
            milky_way.append((x, y, z))
        return milky_way

    def _generate_nebulae(self) -> List[Tuple[float, float, float, float, str, str]]:
        """Gera centros nebulares cósmicos com névoa translúcida sutil."""
        r = self.sphere_radius * 1.35
        # 4 nós nebulares nos setores cardeais siderais
        return [
            # (x, y, z, base_radius, color_dark, color_light)
            (r * 0.65, -r * 0.45, r * 0.40, 68.0, "#10254010", "#A0C5E818"),   # Nebulosa Ciano-Índigo
            (-r * 0.55, r * 0.55, -r * 0.45, 58.0, "#36220E10", "#E5D0A018"),  # Nebulosa Âmbar Primordial
            (r * 0.35, r * 0.65, -r * 0.55, 52.0, "#28123610", "#D5B8E818"),   # Nebulosa Púrpura Sideral
            (-r * 0.65, -r * 0.35, r * 0.45, 62.0, "#0E283010", "#A0D8D018"),  # Nebulosa Esmeralda Abissal
        ]

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
        """Posiciona as obras em constelações distribuídas no volume celeste 3D com estratificação radial por centralidade."""
        if not self.nodes:
            return

        cluster_map: Dict[int, List[Dict[str, Any]]] = {}
        for n in self.nodes:
            c_id = n.get("cluster_id") or 0
            cluster_map.setdefault(c_id, []).append(n)

        num_clusters = len(cluster_map)
        target_r = self.sphere_radius * 0.85

        # 0. Cálculo da centralidade conceitual de cada nó
        # Nós mais centrais (com maior peso de afinidades e fragmentos) ocupam camadas orbitais internas/núcleo
        node_link_weight: Dict[str, float] = {n["id"]: 0.0 for n in self.nodes}
        for link in self.links:
            s_id = str(link.get("source"))
            t_id = str(link.get("target"))
            w = float(link.get("weight") or 0.5)
            if s_id in node_link_weight:
                node_link_weight[s_id] += w
            if t_id in node_link_weight:
                node_link_weight[t_id] += w

        max_w = max(node_link_weight.values()) if node_link_weight and max(node_link_weight.values()) > 0 else 1.0

        for n in self.nodes:
            n_id = n["id"]
            w_score = node_link_weight.get(n_id, 0.0) / max_w
            f_count = float(n.get("fragment_count") or 0)
            f_score = min(1.0, f_count / 8.0)
            # Centralidade: 0.0 (periférico na casca celeste) a 1.0 (núcleo interior do astrolábio)
            centrality = 0.65 * w_score + 0.35 * f_score
            n["_centrality"] = centrality
            # Estratificação radial: nós nucleares a ~0.35*target_r até nós de borda a ~0.88*target_r
            n["_target_radius"] = target_r * (0.88 - 0.53 * centrality)

        # 1. Distribuição harmônica das direções das constelações pela esfera celeste (espiral dourada / Fibonacci)
        cluster_directions: Dict[int, Tuple[float, float, float]] = {}
        for idx, c_id in enumerate(cluster_map.keys()):
            phi = math.acos(1.0 - 2.0 * (idx + 0.5) / max(1, num_clusters))
            theta = math.pi * (1.0 + 5.0**0.5) * idx
            ux = math.sin(phi) * math.cos(theta)
            uy = math.cos(phi)
            uz = math.sin(phi) * math.sin(theta)
            cluster_directions[c_id] = (ux, uy, uz)

        # 2. Posicionamento tridimensional inicial no setor angular e estrato radial de cada constelação
        for c_id, c_nodes in cluster_map.items():
            ux, uy, uz = cluster_directions[c_id]
            norm_u = math.sqrt(ux**2 + uy**2 + uz**2) or 1.0
            ux, uy, uz = ux / norm_u, uy / norm_u, uz / norm_u

            # Vetores tangentes ortonormais
            if abs(uy) < 0.9:
                t1x, t1y, t1z = -uz, 0.0, ux
            else:
                t1x, t1y, t1z = 0.0, -uz, uy
            t1_norm = math.hypot(t1x, t1y, t1z) or 1.0
            t1x, t1y, t1z = t1x / t1_norm, t1y / t1_norm, t1z / t1_norm

            t2x = uy * t1z - uz * t1y
            t2y = uz * t1x - ux * t1z
            t2z = ux * t1y - uy * t1x

            m = len(c_nodes)
            for i, work in enumerate(c_nodes):
                r_node = work.get("_target_radius", target_r * 0.75)
                offset_angle = (i / max(1, m)) * 2.0 * math.pi
                spread = (16.0 + (i % 3) * 12.0) * (r_node / target_r)
                work["x3"] = ux * r_node + spread * (math.cos(offset_angle) * t1x + math.sin(offset_angle) * t2x)
                work["y3"] = uy * r_node + spread * (math.cos(offset_angle) * t1y + math.sin(offset_angle) * t2y)
                work["z3"] = uz * r_node + spread * (math.cos(offset_angle) * t1z + math.sin(offset_angle) * t2z)

        # 3. Campo de forças com ancoragem nos estratos radiais, repulsão estelar e afinidade semântica
        node_map = {n["id"]: n for n in self.nodes}

        for _ in range(30):
            # A. Ancoragem gravitacional na constelação e estrato radial
            for n in self.nodes:
                c_id = n.get("cluster_id") or 0
                ux, uy, uz = cluster_directions[c_id]
                r_target = n.get("_target_radius", target_r)
                anchor_x = ux * r_target
                anchor_y = uy * r_target
                anchor_z = uz * r_target
                n["x3"] += (anchor_x - n["x3"]) * 0.15
                n["y3"] += (anchor_y - n["y3"]) * 0.15
                n["z3"] += (anchor_z - n["z3"]) * 0.15

            # B. Repulsão anti-colisão entre nós
            for i in range(len(self.nodes)):
                n1 = self.nodes[i]
                for j in range(i + 1, len(self.nodes)):
                    n2 = self.nodes[j]
                    dx = n1["x3"] - n2["x3"]
                    dy = n1["y3"] - n2["y3"]
                    dz = n1["z3"] - n2["z3"]
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if 0.0 < dist < 38.0:
                        rep_force = (38.0 - dist) / dist * 0.35
                        n1["x3"] += dx * rep_force
                        n1["y3"] += dy * rep_force
                        n1["z3"] += dz * rep_force
                        n2["x3"] -= dx * rep_force
                        n2["y3"] -= dy * rep_force
                        n2["z3"] -= dz * rep_force

            # C. Atração por afinidade semântica
            for link in self.links:
                s_id = link.get("source")
                t_id = link.get("target")
                s = node_map.get(s_id)
                t = node_map.get(t_id)
                if s and t:
                    weight = float(link.get("weight") or 0.5)
                    dx = t["x3"] - s["x3"]
                    dy = t["y3"] - s["y3"]
                    dz = t["z3"] - s["z3"]
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if s.get("cluster_id") == t.get("cluster_id"):
                        if dist > 28.0:
                            att_force = (dist - 28.0) / dist * 0.08 * weight
                            s["x3"] += dx * att_force
                            s["y3"] += dy * att_force
                            s["z3"] += dz * att_force
                            t["x3"] -= dx * att_force
                            t["y3"] -= dy * att_force
                            t["z3"] -= dz * att_force
                    else:
                        if dist > 70.0:
                            att_force = 0.005 * weight
                            s["x3"] += dx * att_force
                            s["y3"] += dy * att_force
                            s["z3"] += dz * att_force
                            t["x3"] -= dx * att_force
                            t["y3"] -= dy * att_force
                            t["z3"] -= dz * att_force

            # D. Projeção nas conchas esféricas proporcionais à centralidade (profundidade tridimensional)
            for n in self.nodes:
                curr_r = math.sqrt(n["x3"] ** 2 + n["y3"] ** 2 + n["z3"] ** 2)
                if curr_r > 0.0:
                    r_target = n.get("_target_radius", target_r * 0.75)
                    scale_factor = r_target / curr_r
                    n["x3"] *= scale_factor
                    n["y3"] *= scale_factor
                    n["z3"] *= scale_factor

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

            # 0. Nebulosas Cósmicas Etéreas de Fundo Profundo
            if high_detail:
                for nx, ny, nz, n_radius, n_col_dark, n_col_light in self.nebulae:
                    nsx, nsy, nsz = self._project_point(nx, ny, nz)
                    n_depth_scale = 520.0 / max(80.0, nsz + self.camera_distance)
                    shapes.append(
                        cv.Circle(
                            x=nsx,
                            y=nsy,
                            radius=n_radius * n_depth_scale * self.scale,
                            paint=ft.Paint(color=n_col_dark if is_dark else n_col_light),
                        )
                    )

            # 1. Rio Estelar da Via Láctea (Tapeçaria de Micro-poeira Cósmica via cv.Points)
            mw_pts = self.milky_way_stream if high_detail else self.milky_way_stream[::3]
            proj_mw = [self._project_point(x, y, z) for x, y, z in mw_pts]
            mw_2d_points = [(p[0], p[1]) for p in proj_mw]
            mw_color = "#A8C8F035" if is_dark else "#50688035"
            shapes.append(
                cv.Points(
                    points=mw_2d_points,
                    point_mode=cv.PointMode.POINTS,
                    paint=ft.Paint(
                        color=mw_color,
                        stroke_width=1.3 * self.scale,
                    ),
                )
            )

            # 2. Firmamento Estelar Multicromático (Classes Espectrais: Azul, Âmbar, Coral, Prata)
            dust_points = self.starfield if high_detail else self.starfield[:28]
            spectral_colors_dark = ["#B5D8FF", "#FFE296", "#FFB8A5", "#F0F2FA"]
            spectral_colors_light = ["#2A4A6E", "#8A6818", "#7A3E2D", "#585A66"]
            spec_palette = spectral_colors_dark if is_dark else spectral_colors_light

            for idx, (x, y, z, bright, base_r, mag) in enumerate(dust_points):
                sx, sy, sz = self._project_point(x, y, z)
                depth_scale = 520.0 / max(80.0, sz + self.camera_distance)
                r_proj = max(0.65, base_r * depth_scale)
                star_color = spec_palette[idx % 4]

                if mag == 1:
                    # Estrela-Guia Majestosa: Halo difuso + Cruz de difração telescópica óptica
                    shapes.append(
                        cv.Circle(
                            x=sx,
                            y=sy,
                            radius=r_proj * 2.8,
                            paint=ft.Paint(color=f"{star_color}25"),
                        )
                    )
                    shapes.append(
                        cv.Circle(
                            x=sx,
                            y=sy,
                            radius=r_proj,
                            paint=ft.Paint(color=star_color),
                        )
                    )
                    if high_detail:
                        spike_len = (r_proj + 3.2) * self.scale
                        shapes.append(
                            cv.Line(
                                x1=sx - spike_len,
                                y1=sy,
                                x2=sx + spike_len,
                                y2=sy,
                                paint=ft.Paint(color=f"{star_color}80", stroke_width=0.8 * self.scale),
                            )
                        )
                        shapes.append(
                            cv.Line(
                                x1=sx,
                                y1=sy - spike_len,
                                x2=sx,
                                y2=sy + spike_len,
                                paint=ft.Paint(color=f"{star_color}80", stroke_width=0.8 * self.scale),
                            )
                        )
                else:
                    dust_alpha = int(max(0.20, min(0.90, bright)) * 255)
                    alpha_hex = f"{dust_alpha:02X}"
                    shapes.append(
                        cv.Circle(
                            x=sx,
                            y=sy,
                            radius=r_proj,
                            paint=ft.Paint(color=f"{star_color[:7]}{alpha_hex}"),
                        )
                    )

            # 2. Grade Cartográfica Celeste Posterior (Z < 0)
            if self.show_celestial_grid:
                self._render_celestial_grid(shapes, grid_color, draw_front=False, high_detail=high_detail)

            # 3. Anéis da Esfera Armilar — Metade Posterior (Z < 0)
            self._render_armillary_rings(shapes, ring_color, ring_color, draw_front=False, high_detail=high_detail)

            # Filtragem por camada celeste / constelação
            if self.filter_mode.startswith("cluster_"):
                try:
                    target_c_id = int(self.filter_mode.split("_")[1])
                    visible_nodes = [n for n in self.nodes if n.get("cluster_id") == target_c_id]
                except Exception:
                    visible_nodes = self.nodes
            elif self.filter_mode == "works":
                visible_nodes = [n for n in self.nodes if n.get("type") == "work"]
            elif self.filter_mode == "fragments":
                visible_nodes = [n for n in self.nodes if n.get("type") != "work"]
            else:
                visible_nodes = self.nodes

            visible_ids = {n["id"] for n in visible_nodes} | {str(n["id"]) for n in visible_nodes}

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
                self.projected_nodes[str(n_id)] = (sx, sy, sz)
                node_depths.append((sz, node, sx, sy))

            # Identificação dos nós conexos imediatos à seleção ativa
            connected_node_ids: Set[str] = set()
            sel_id_str: Optional[str] = None
            if self.selected_node_id:
                sel_id_str = str(self.selected_node_id)
                connected_node_ids.add(sel_id_str)
                for link in self.links:
                    s_id = str(link.get("source", ""))
                    t_id = str(link.get("target", ""))
                    if s_id == sel_id_str and (t_id in visible_ids):
                        connected_node_ids.add(t_id)
                    elif t_id == sel_id_str and (s_id in visible_ids):
                        connected_node_ids.add(s_id)

            # 5. Filamentos de Luz Constelares (Renderizados EXCLUSIVAMENTE sob seleção ativa)
            if self.selected_node_id and sel_id_str:
                for link in self.links:
                    s_id = str(link.get("source", ""))
                    t_id = str(link.get("target", ""))
                    if s_id not in visible_ids or t_id not in visible_ids:
                        continue
                    if s_id not in self.projected_nodes or t_id not in self.projected_nodes:
                        continue

                    # Conecta apenas a obra selecionada aos seus vizinhos imediatos
                    if s_id != sel_id_str and t_id != sel_id_str:
                        continue

                    weight = float(link.get("weight") or 0.5)
                    sx1, sy1, sz1 = self.projected_nodes[s_id]
                    sx2, sy2, sz2 = self.projected_nodes[t_id]

                    avg_z = (sz1 + sz2) / 2.0
                    depth_scale = 520.0 / max(100.0, avg_z + self.camera_distance)

                    stroke_color = ring_color
                    stroke_width = max(1.6, 3.4 * depth_scale) * self.scale

                    shapes.append(
                        cv.Line(
                            x1=sx1,
                            y1=sy1,
                            x2=sx2,
                            y2=sy2,
                            data="filament",
                            paint=ft.Paint(
                                color=stroke_color,
                                stroke_width=stroke_width,
                            ),
                        )
                    )

            # 6. Ordenação de Nós por Profundidade (Painter's Algorithm)
            node_depths.sort(key=lambda item: item[0])

            has_selection = bool(self.selected_node_id and sel_id_str)

            for sz, node, sx, sy in node_depths:
                n_id_str = str(node["id"])
                node_type = node.get("type") or "fragment"
                is_selected = has_selection and (n_id_str == sel_id_str)
                is_connected = has_selection and (n_id_str in connected_node_ids)
                is_dimmed = has_selection and not is_connected
                depth_scale = 520.0 / max(80.0, sz + self.camera_distance)

                if node_type == "work":
                    node_color = node.get("color") or work_node_color

                    if is_dimmed:
                        # Nó desvinculado da seleção: Translúcido e discreto, eliminando poluição visual
                        core_r = 5.0 * depth_scale * self.scale
                        dimmed_color = (
                            f"{node_color[:7]}20"
                            if node_color.startswith("#") and len(node_color) >= 7
                            else ft.Colors.with_opacity(0.12, node_color)
                        )
                        shapes.append(
                            cv.Circle(
                                x=sx,
                                y=sy,
                                radius=core_r,
                                data="node_dimmed",
                                paint=ft.Paint(color=dimmed_color),
                            )
                        )
                        # Sem corona e sem rótulo para eliminar ruído visual periférico
                    else:
                        corona_r = (26.0 if is_selected else (20.0 if is_connected else 18.0)) * depth_scale * self.scale
                        core_r = (10.0 if is_selected else (8.0 if is_connected else 7.5)) * depth_scale * self.scale

                        # Auréola de corona nobre
                        corona_color = (
                            f"{ring_color}45"
                            if is_selected
                            else (f"{node_color}35" if is_connected else f"{node_color}30")
                        )
                        shapes.append(
                            cv.Circle(
                                x=sx,
                                y=sy,
                                radius=corona_r,
                                paint=ft.Paint(color=corona_color),
                            )
                        )
                        # Núcleo estelar
                        shapes.append(
                            cv.Circle(
                                x=sx,
                                y=sy,
                                radius=core_r,
                                data="node_core",
                                paint=ft.Paint(color=ring_color if is_selected else node_color),
                            )
                        )
                        # Rótulo de texto: Cormorant Garamond com peso W_700/W_800 para nobreza e fidelidade ao app
                        # Exibido em alta fidelidade, na seleção direta OU para todas as obras conexas ativas
                        if high_detail or is_selected or is_connected:
                            label_text = node.get("label") or node.get("title") or ""
                            if len(label_text) > 28:
                                label_text = label_text[:26] + "…"
                            shapes.append(
                                cv.Text(
                                    x=sx + core_r + 5.0,
                                    y=sy - 8.0,
                                    value=label_text,
                                    style=ft.TextStyle(
                                        size=max(14.0, 17.5 * depth_scale * self.scale),
                                        font_family=self.font_family,
                                        weight=ft.FontWeight.W_800 if is_selected else ft.FontWeight.W_700,
                                        color=ring_color if is_selected else text_color,
                                    ),
                                )
                            )
                else:
                    node_color = node.get("color") or frag_node_color
                    if is_dimmed:
                        core_r = 3.0 * depth_scale * self.scale
                        dimmed_color = (
                            f"{node_color[:7]}18"
                            if node_color.startswith("#") and len(node_color) >= 7
                            else ft.Colors.with_opacity(0.10, node_color)
                        )
                        shapes.append(
                            cv.Circle(
                                x=sx,
                                y=sy,
                                radius=core_r,
                                data="node_dimmed",
                                paint=ft.Paint(color=dimmed_color),
                            )
                        )
                    else:
                        core_r = (7.0 if is_selected else (5.5 if is_connected else 4.5)) * depth_scale * self.scale
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
                                data="node_core",
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
            if self._pending_render:
                self._pending_render = False
                self.render(high_detail=True)

    def _render_armillary_rings(
        self,
        shapes: list[cv.Shape],
        color_back: str,
        color_front: str,
        draw_front: bool,
        high_detail: bool = True,
    ) -> None:
        """Desenha os anéis astronômicos clássicos da Esfera Armilar utilizando geometria contínua em Path (60 FPS suave)."""
        rings_to_draw = self._precomputed_rings if high_detail else [
            r for r in self._precomputed_rings if r[0] in ("equator", "ecliptic", "meridian")
        ]
        paint_color = color_front if draw_front else color_back
        stride = 1 if high_detail else 2

        for ring_name, pts in rings_to_draw:
            sub_pts = pts[::stride]
            if sub_pts[-1] != pts[-1]:
                sub_pts.append(pts[-1])
            proj = [self._project_point(p[0], p[1], p[2]) for p in sub_pts]
            stroke_base = 1.5 if ring_name == "ecliptic" else 1.2
            stroke_w = (stroke_base if draw_front else 0.75) * self.scale

            elements: list[cv.Path.PathElement] = []
            drawing = False
            for i in range(len(proj) - 1):
                sx1, sy1, sz1 = proj[i]
                sx2, sy2, sz2 = proj[i + 1]
                avg_z = (sz1 + sz2) * 0.5
                is_front = avg_z >= 0.0

                if is_front == draw_front:
                    if not drawing:
                        elements.append(cv.Path.MoveTo(sx1, sy1))
                        drawing = True
                    elements.append(cv.Path.LineTo(sx2, sy2))
                else:
                    drawing = False

            if elements:
                shapes.append(
                    cv.Path(
                        elements=elements,
                        paint=ft.Paint(
                            color=paint_color,
                            stroke_width=stroke_w,
                            style=ft.PaintingStyle.STROKE,
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
        """Desenha a malha cartográfica renascentista de coordenadas celestes com alta curvatura contínua via Path batched."""
        elements: list[cv.Path.PathElement] = []
        stride = 1 if high_detail else 2

        for _line_name, pts in self._precomputed_grid:
            sub_pts = pts[::stride]
            if sub_pts[-1] != pts[-1]:
                sub_pts.append(pts[-1])
            proj = [self._project_point(p[0], p[1], p[2]) for p in sub_pts]

            drawing = False
            for i in range(len(proj) - 1):
                sx1, sy1, sz1 = proj[i]
                sx2, sy2, sz2 = proj[i + 1]
                avg_z = (sz1 + sz2) * 0.5
                is_front = avg_z >= 0.0

                if is_front == draw_front:
                    if not drawing:
                        elements.append(cv.Path.MoveTo(sx1, sy1))
                        drawing = True
                    elements.append(cv.Path.LineTo(sx2, sy2))
                else:
                    drawing = False

        if elements:
            shapes.append(
                cv.Path(
                    elements=elements,
                    paint=ft.Paint(
                        color=color,
                        stroke_width=(0.65 if draw_front else 0.45) * self.scale,
                        style=ft.PaintingStyle.STROKE,
                    ),
                )
            )

    def _render_astrolabe_ticks(
        self,
        shapes: list[cv.Shape],
        color: str,
        high_detail: bool = True,
    ) -> None:
        """Desenha as graduações astronômicas de astrolábio nos anéis da frente utilizando um único Path batched."""
        ticks_to_draw = self._precomputed_ticks if high_detail else self._precomputed_ticks[::2]
        elements: list[cv.Path.PathElement] = []

        for p1, p2 in ticks_to_draw:
            sx1, sy1, sz1 = self._project_point(p1[0], p1[1], p1[2])
            sx2, sy2, sz2 = self._project_point(p2[0], p2[1], p2[2])
            if (sz1 + sz2) * 0.5 >= 0.0:  # Apenas metade anterior visível
                elements.append(cv.Path.MoveTo(sx1, sy1))
                elements.append(cv.Path.LineTo(sx2, sy2))

        if elements:
            shapes.append(
                cv.Path(
                    elements=elements,
                    paint=ft.Paint(
                        color=color,
                        stroke_width=0.9 * self.scale,
                        style=ft.PaintingStyle.STROKE,
                    ),
                )
            )

    def _handle_pan_start(self, _e: ft.DragStartEvent) -> None:
        """Sinaliza início de interação de arraste contínuo."""
        self._is_dragging = True
        self.gesture_detector.mouse_cursor = ft.MouseCursor.GRABBING
        try:
            self.gesture_detector.update()
        except Exception:
            pass

    def _handle_pan_end(self, _e: ft.DragEndEvent) -> None:
        """Ao soltar o mouse, renderiza o quadro final em qualidade total com todos os rótulos de texto."""
        self._is_dragging = False
        self.gesture_detector.mouse_cursor = ft.MouseCursor.GRAB
        try:
            self.gesture_detector.update()
        except Exception:
            pass
        self.render(high_detail=True)

    def _handle_pan_cancel(self, _e: ft.ControlEvent) -> None:
        """Trata o cancelamento do gesto de arraste orbital."""
        self._is_dragging = False
        self.gesture_detector.mouse_cursor = ft.MouseCursor.GRAB
        try:
            self.gesture_detector.update()
        except Exception:
            pass
        self.render(high_detail=True)

    def _handle_pan_update(self, e: ft.DragUpdateEvent) -> None:
        """Controla a rotação 360° orbital contínua com taxa dinâmica travada a 60 FPS."""
        self._is_dragging = True
        local_delta = getattr(e, "local_delta", None)
        global_delta = getattr(e, "global_delta", None)
        if local_delta is not None and getattr(local_delta, "x", None) is not None:
            dx = getattr(local_delta, "x", 0.0) or 0.0
            dy = getattr(local_delta, "y", 0.0) or 0.0
        elif global_delta is not None and getattr(global_delta, "x", None) is not None:
            dx = getattr(global_delta, "x", 0.0) or 0.0
            dy = getattr(global_delta, "y", 0.0) or 0.0
        else:
            dx = getattr(e, "delta_x", 0.0) or 0.0
            dy = getattr(e, "delta_y", 0.0) or 0.0

        self.yaw += dx * 0.0075
        self.pitch += dy * 0.0075
        self.pitch = max(-math.pi / 2.2, min(math.pi / 2.2, self.pitch))

        if self._is_rendering:
            return

        now = time.perf_counter()
        # Trava para fluidez a 60 FPS (16.6 ms)
        if now - self._last_render_time < 0.016:
            return

        self._last_render_time = now
        self.render(high_detail=False)

    def _handle_scroll(self, e: ft.ScrollEvent) -> None:
        """Controla o zoom telescópico aproximando ou afastando a câmera da esfera."""
        scroll_delta = getattr(e, "scroll_delta", None)
        if scroll_delta is not None and getattr(scroll_delta, "y", None) is not None:
            delta = getattr(scroll_delta, "y", 0.0) or 0.0
        else:
            delta = getattr(e, "scroll_delta_y", 0.0) or 0.0

        if delta != 0.0:
            self.camera_distance += delta * 0.45
            self.camera_distance = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.camera_distance))
            self.render(high_detail=True)

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

    def zoom_in(self, amount: float = 65.0) -> None:
        """Aproxima a câmera orbital da constelação (Zoom In)."""
        self.camera_distance = max(self.ZOOM_MIN, self.camera_distance - amount)
        self.render(high_detail=True)

    def zoom_out(self, amount: float = 65.0) -> None:
        """Afasta a câmera orbital da constelação (Zoom Out)."""
        self.camera_distance = min(self.ZOOM_MAX, self.camera_distance + amount)
        self.render(high_detail=True)

    def reset_view(self) -> None:
        """Retorna a visão orbital da esfera para o ângulo clássico renascentista e zoom inicial."""
        self.pitch = 0.38
        self.yaw = 0.65
        self.camera_distance = 680.0
        self.selected_node_id = None
        self.render(high_detail=True)

    def select_node_id(self, node_id: Optional[str]) -> None:
        """Define o nó selecionado e atualiza a constelação."""
        self.selected_node_id = node_id
        self.render()

    def compose(self) -> ft.Control:
        """Retorna o controle Flet empacotado para inserção na interface."""
        return self.gesture_detector
