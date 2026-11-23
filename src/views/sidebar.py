"""Composer da barra lateral de navegação (redesign v2)."""

from collections.abc import Callable
from dataclasses import dataclass, field

import flet as ft

from src.utils.fa import fa_icon
from src.utils.fa import glyph as fa_glyph
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.ui_kit import MOTION_FAST, MOTION_SLOW, motion, s
from src.utils.control_safety import safe_update


@dataclass
class SidebarData:
    """Contagens e projetos mostrados na barra lateral."""

    works: int | None = None
    fragments: int | None = None
    compilations: list[tuple[int, str]] = field(default_factory=list)


# (destino, ícone, rótulo, chave da contagem)
MAIN_ITEMS = [
    ("dashboard", "house", "Início", None),
    ("Acervo", "book", "Acervo", "works"),
    ("Fragmentos", "quote-left", "Fragmentos", "fragments"),
]
EXPLORE_ITEMS = [
    ("Estruturas de Saber", "diagram-project", "Estruturas de Saber"),
    ("Nous", "brain", "Nous"),
]


class SidebarComposer:
    """Compõe busca, navegação agrupada e rodapé com status e tema."""

    def __init__(
        self,
        scale: float,
        config: ViewConfig,
        on_navigate: Callable[[str], None],
        current: str = "dashboard",
        data: SidebarData | None = None,
        on_search: Callable[[], None] | None = None,
        on_new_work: Callable[[], None] | None = None,
        on_new_compilation: Callable[[], None] | None = None,
        on_toggle_theme: Callable[[], None] | None = None,
        compilations_expanded: bool = True,
        on_toggle_compilations: Callable[[bool], None] | None = None,
    ) -> None:
        self.scale = scale
        self.config = config
        self.on_navigate = on_navigate
        self.current = current
        self.data = data or SidebarData()
        self.on_search = on_search
        self.on_new_work = on_new_work
        self.on_new_compilation = on_new_compilation
        self.on_toggle_theme = on_toggle_theme
        self.compilations_expanded = compilations_expanded
        if self.current.startswith("compilacao:"):
            self.compilations_expanded = True
        self.on_toggle_compilations = on_toggle_compilations
        self._items: dict[str, dict] = {}
        self._project_signature: tuple[tuple[int, str], ...] = ()

    def _toggle_compilations(self) -> None:
        self.compilations_expanded = not self.compilations_expanded
        self._rebuild_projects()
        self._sync_chevron()
        if self.on_toggle_compilations is not None:
            self.on_toggle_compilations(self.compilations_expanded)

    def _rebuild_projects(self) -> None:
        switcher = getattr(self, "_projects_switcher", None)
        if switcher is None:
            return
        for key in [item for item in self._items if item.startswith("compilacao:")]:
            self._items.pop(key, None)
        switcher.content = self._projects_content()
        self._project_signature = tuple(self.data.compilations)
        safe_update(switcher)

    # ── peças ──────────────────────────────────────────────

    def _item(
        self,
        destination: str,
        icon_name: str | None,
        label: str,
        count: int | None = None,
        leading: ft.Control | None = None,
        indent: float = 0,
        trailing: ft.Control | None = None,
        count_key: str | None = None,
    ) -> ft.Container:
        c = self.config
        active = self.current == destination
        state = {"active": active}
        glyph = leading or fa_icon(
            icon_name or "circle",
            size=s(13),
            color=c.colors["gold"] if active else c.colors["faint"],
        )
        if isinstance(glyph, ft.Container):
            glyph.animate = motion(MOTION_FAST)
        glyph_box = ft.Container(
            glyph,
            width=s(18),
            alignment=ft.Alignment.CENTER,
            animate_scale=motion(MOTION_FAST),
        )
        label_text = ui.serif_text(
            c, label, size=16 if indent > 0 else 17,
            weight=ui.W700 if active else ui.W600,
            color=c.colors["text"] if active else c.colors["muted"],
            max_lines=1,
            no_wrap=True,
            expand=True,
        )
        label_text.tooltip = label
        controls: list[ft.Control] = [
            glyph_box,
            label_text,
        ]
        count_ctrl = None
        if count is not None:
            count_ctrl = ui.ui_text(c, str(count), size=12, color=c.colors["faint"], tabular=True)
            controls.append(count_ctrl)
        if trailing is not None:
            controls.append(trailing)

        active_border = ft.Border(
            left=ft.BorderSide(s(3), c.colors["gold"]),
            top=ft.BorderSide(1, c.colors["border_strong"]),
            right=ft.BorderSide(1, c.colors["border_strong"]),
            bottom=ft.BorderSide(1, c.colors["border_strong"]),
        )
        hover_border = ft.Border(
            left=ft.BorderSide(s(3), c.colors["gold"]),
            top=ft.BorderSide(1, c.colors["border_strong"]),
            right=ft.BorderSide(1, c.colors["border_strong"]),
            bottom=ft.BorderSide(1, c.colors["border_strong"]),
        )
        item_radius = ft.BorderRadius.only(
            top_left=0,
            bottom_left=0,
            top_right=s(6),
            bottom_right=s(6),
        )

        def _on_hover_item(hovering: bool) -> None:
            if not state["active"]:
                if isinstance(glyph, ft.Text):
                    glyph.color = c.colors["gold"] if hovering else c.colors["faint"]
                elif isinstance(glyph, ft.Container) and hasattr(glyph, "bgcolor"):
                    glyph.border = ft.Border.all(1.5, c.colors["gold"]) if hovering else ft.Border.all(1.5, c.colors["faint"])
                    glyph.bgcolor = c.colors["gold"] if hovering else None
                glyph_box.scale = 1.12 if hovering else 1.0
                label_text.color = c.colors["gold"] if hovering else c.colors["muted"]
                if count_ctrl is not None:
                    count_ctrl.color = c.colors["gold"] if hovering else c.colors["faint"]

        item = ui.hover_surface(
            c,
            ft.Row(controls, spacing=s(8 if indent > 0 else 10), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            on_click=lambda _e: self.on_navigate(destination),
            selected=lambda: state["active"],
            padding=ft.Padding.only(left=s(8 + indent), right=s(6 if trailing else 8)),
            height=s(32 if indent > 0 else 34),
            radius=item_radius,
            border=active_border if active else None,
            hover_border=hover_border,
            on_hover=_on_hover_item,
        )
        item.data = destination
        self._items[destination] = {
            "box": item,
            "glyph": glyph,
            "label": label_text,
            "count": count_ctrl,
            "count_key": count_key,
            "state": state,
            "active_border": active_border,
        }
        return item

    def _group_head(self, label: str, action: ft.Control | None = None) -> ft.Container:
        c = self.config
        return ft.Container(
            content=ft.Row(
                [ui.ui_text(c, label, size=12, weight=ui.W600, color=c.colors["faint"])] + ([action] if action else []),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s(26),
            padding=ft.Padding.only(left=s(8), right=s(2)),
        )

    def _compose_top(self) -> ft.Container:
        c = self.config
        search_icon = fa_icon("magnifying-glass", size=s(12), color=c.colors["faint"])
        search_label = ui.serif_text(c, "Buscar no gabinete...", size=15.5, weight=ui.W600, color=c.colors["faint"], max_lines=1, no_wrap=True, expand=True)

        def _on_hover_search(hovering: bool) -> None:
            search_icon.color = c.colors["gold"] if hovering else c.colors["faint"]
            search_label.color = c.colors["text"] if hovering else c.colors["faint"]
            search.border = ft.Border.all(1, c.colors["gold"] if hovering else c.colors["border_strong"])

        search = ui.hover_surface(
            c,
            ft.Row(
                [
                    search_icon,
                    search_label,
                    ui.kbd(c, "⌘K"),
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda _e: self.on_search() if self.on_search else None,
            padding=ft.Padding.only(left=s(8), right=s(6)),
            height=s(34),
            base=c.colors["bg"],
            on_hover=_on_hover_search,
        )
        search.border = ft.Border.all(1, c.colors["border_strong"])
        search.expand = True
        return ft.Container(
            content=ft.Row(controls=[search], spacing=s(8)),
            padding=ft.Padding.only(left=s(12), right=s(12), top=s(12), bottom=s(8)),
        )

    def _projects_content(self) -> ft.Control:
        """Lista de cadernos, montada à parte para animar o recolhimento."""
        c = self.config
        if not self.compilations_expanded or not self.data.compilations:
            return ft.Container(height=0)
        controls: list[ft.Control] = []
        for comp_id, name in self.data.compilations:
            destination = f"compilacao:{comp_id}"
            active = self.current == destination
            dot = ft.Container(
                width=s(8), height=s(8),
                border_radius=ft.BorderRadius.all(s(2)),
                border=ft.Border.all(1.5, c.colors["gold"] if active else c.colors["faint"]),
                bgcolor=c.colors["gold"] if active else None,
            )
            controls.append(self._item(destination, None, name, leading=dot, indent=14))
        return ft.Column(controls, spacing=s(1), tight=True)

    def _sync_chevron(self) -> None:
        """Troca o glifo do chevron sem recriar a barra lateral."""
        button = getattr(self, "_chevron_btn", None)
        if button is None:
            return
        glyph = button.content
        char, family = fa_glyph("chevron-down" if self.compilations_expanded else "chevron-right", "solid")
        glyph.value = char
        glyph.font_family = family
        button.tooltip = "Recolher cadernos" if self.compilations_expanded else "Expandir cadernos"
        safe_update(button)

    def update_state(self, current: str, data: SidebarData | None = None) -> None:
        """Atualiza item ativo e contadores sem reconstruir a barra lateral."""
        previous_expanded = self.compilations_expanded
        self.current = current
        if current.startswith("compilacao:"):
            self.compilations_expanded = True
        if data is not None:
            self.data = data
        for destination, ref in list(self._items.items()):
            self._paint_item(destination, ref)
        if previous_expanded != self.compilations_expanded:
            self._rebuild_projects()
        else:
            self._sync_projects()
        self._sync_chevron()

    def _paint_item(self, destination: str, ref: dict) -> None:
        c = self.config
        active = self.current == destination
        ref["state"]["active"] = active
        ref["label"].weight = ui.W700 if active else ui.W600
        ref["label"].color = c.colors["text"] if active else c.colors["muted"]
        ref["box"].bgcolor = c.colors["selected"] if active else None
        ref["box"].border = ref["active_border"] if active else None
        glyph = ref["glyph"]
        if isinstance(glyph, ft.Text):
            glyph.color = c.colors["gold"] if active else c.colors["faint"]
        elif isinstance(glyph, ft.Container):
            glyph.border = ft.Border.all(1.5, c.colors["gold"] if active else c.colors["faint"])
            glyph.bgcolor = c.colors["gold"] if active else None
        count = ref["count"]
        key = ref["count_key"]
        if count is not None and key:
            value = len(self.data.compilations) if key == "compilations" else getattr(self.data, key, None)
            if value is not None:
                count.value = str(value)
        safe_update(ref["box"])

    def _sync_projects(self) -> None:
        signature = tuple(self.data.compilations)
        switcher = getattr(self, "_projects_switcher", None)
        if switcher is None:
            self._project_signature = signature
            return
        if signature != self._project_signature:
            for key in [item for item in self._items if item.startswith("compilacao:")]:
                self._items.pop(key, None)
            self._project_signature = signature
            switcher.content = self._projects_content()
            safe_update(switcher)
        else:
            for destination, ref in list(self._items.items()):
                if destination.startswith("compilacao:"):
                    self._paint_item(destination, ref)

    def _compose_navigation(self) -> ft.Container:
        c = self.config
        counts = {"works": self.data.works, "fragments": self.data.fragments}
        main = [self._item(dest, ic, label, counts.get(key) if key else None, count_key=key) for dest, ic, label, key in MAIN_ITEMS]

        add_comp = ui.icon_button(
            c, "plus",
            on_click=lambda _e: self.on_new_compilation() if self.on_new_compilation else self.on_navigate("Compilações"),
            tooltip="Nova compilação", size=22,
        )

        chevron_btn = ui.icon_button(
            c,
            "chevron-down" if self.compilations_expanded else "chevron-right",
            size=22,
            tooltip="Recolher cadernos" if self.compilations_expanded else "Expandir cadernos",
            on_click=lambda _e: self._toggle_compilations(),
        )

        self._chevron_btn = chevron_btn
        root_comp = self._item(
            "Compilações",
            "folder-open",
            "Todas as compilações",
            len(self.data.compilations),
            trailing=chevron_btn,
            count_key="compilations",
        )

        self._projects_switcher = ft.AnimatedSwitcher(
            content=self._projects_content(),
            duration=MOTION_SLOW,
            reverse_duration=MOTION_FAST,
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
            transition=ft.AnimatedSwitcherTransition.FADE,
        )
        self._project_signature = tuple(self.data.compilations)

        compilations_section: list[ft.Control] = [
            self._group_head("Compilações", add_comp),
            root_comp,
            self._projects_switcher,
        ]

        explore = [self._item(dest, ic, label) for dest, ic, label in EXPLORE_ITEMS]

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Column(main, spacing=s(1), tight=True),
                    ft.Column(compilations_section, spacing=s(1), tight=True),
                    ft.Column([self._group_head("Explorar"), *explore], spacing=s(1), tight=True),
                ],
                spacing=s(16),
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=ft.Padding.only(left=s(12), right=s(12), top=s(4), bottom=s(12)),
            expand=True,
        )

    def _compose_footer(self) -> ft.Container:
        c = self.config
        status = ft.Row(
            [
                ft.Container(width=s(6), height=s(6), border_radius=ft.BorderRadius.all(s(3)), bgcolor=c.colors["ok"]),
                ui.ui_text(c, "Banco local", size=12, color=c.colors["faint"]),
            ],
            spacing=s(8),
            tight=True,
        )
        theme = ui.icon_button(
            c, "circle-half-stroke",
            on_click=lambda _e: self.on_toggle_theme() if self.on_toggle_theme else None,
            tooltip="Alternar tema", size=26,
        )
        return ft.Container(
            content=ft.Column(
                [
                    self._item("Configurações", "gear", "Configurações"),
                    ft.Container(
                        ft.Row([status, theme], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        height=s(30),
                        padding=ft.Padding.only(left=s(8), right=s(2)),
                    ),
                ],
                spacing=s(2),
                tight=True,
            ),
            padding=ft.Padding.only(left=s(12), right=s(12), top=s(8), bottom=s(12)),
            border=ft.Border.only(top=ft.BorderSide(1, c.colors["border"])),
        )

    def compose(self) -> ft.Container:
        """Monta a barra lateral completa."""
        self._items = {}
        return ft.Container(
            width=s(self.config.ui["sidebar_width"]),
            bgcolor=self.config.colors["chrome"],
            border=ft.Border.only(right=ft.BorderSide(1, self.config.colors["border"])),
            content=ft.Column(
                controls=[
                    self._compose_top(),
                    self._compose_navigation(),
                    self._compose_footer(),
                ],
                spacing=0,
                expand=True,
            ),
        )
