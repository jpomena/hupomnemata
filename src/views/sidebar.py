"""Composer da barra lateral de navegação (redesign v2)."""

from collections.abc import Callable
from dataclasses import dataclass, field

import flet as ft

from src.utils.fa import fa_icon
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.ui_kit import s


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

    # ── peças ──────────────────────────────────────────────

    def _item(
        self,
        destination: str,
        icon_name: str | None,
        label: str,
        count: int | None = None,
        leading: ft.Control | None = None,
    ) -> ft.Container:
        c = self.config
        active = self.current == destination
        glyph = leading or fa_icon(
            icon_name or "circle",
            size=s(13),
            color=c.colors["gold"] if active else c.colors["faint"],
        )
        label_text = ui.ui_text(
            c, label, size=13,
            weight=ui.W600 if active else ui.W500,
            color=c.colors["text"] if active else c.colors["muted"],
            expand=True,
        )
        controls: list[ft.Control] = [
            ft.Container(glyph, width=s(18), alignment=ft.Alignment.CENTER),
            label_text,
        ]
        if count is not None:
            controls.append(ui.ui_text(c, str(count), size=12, color=c.colors["faint"], tabular=True))

        def _on_hover_item(hovering: bool) -> None:
            if not active:
                if isinstance(glyph, ft.Text):
                    glyph.color = c.colors["gold"] if hovering else c.colors["faint"]
                elif isinstance(glyph, ft.Container) and hasattr(glyph, "bgcolor"):
                    glyph.border = ft.Border.all(1.5, c.colors["gold"]) if hovering else ft.Border.all(1.5, c.colors["faint"])
                    glyph.bgcolor = c.colors["gold"] if hovering else None
                label_text.color = c.colors["text"] if hovering else c.colors["muted"]

        item = ui.hover_surface(
            c,
            ft.Row(controls, spacing=s(10), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            on_click=lambda _e: self.on_navigate(destination),
            selected=active,
            padding=ft.Padding.symmetric(horizontal=s(8)),
            height=s(30),
            on_hover=_on_hover_item,
        )
        item.data = destination
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
        search_label = ui.ui_text(c, "Buscar", size=13, color=c.colors["faint"], expand=True)

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
            height=s(32),
            base=c.colors["bg"],
            on_hover=_on_hover_search,
        )
        search.border = ft.Border.all(1, c.colors["border_strong"])
        search.expand = True
        new_work = ui.icon_button(
            c, "plus",
            on_click=lambda _e: self.on_new_work() if self.on_new_work else self.on_navigate("work_insert"),
            tooltip="Nova obra (⌘N)", boxed=True, size=32,
        )
        return ft.Container(
            content=ft.Row([search, new_work], spacing=s(8)),
            padding=ft.Padding.only(left=s(12), right=s(12), top=s(12), bottom=s(8)),
        )

    def _compose_navigation(self) -> ft.Container:
        c = self.config
        counts = {"works": self.data.works, "fragments": self.data.fragments}
        main = [self._item(dest, ic, label, counts.get(key) if key else None) for dest, ic, label, key in MAIN_ITEMS]

        add_comp = ui.icon_button(
            c, "plus",
            on_click=lambda _e: self.on_new_compilation() if self.on_new_compilation else self.on_navigate("Compilações"),
            tooltip="Nova compilação", size=22,
        )
        projects = []
        for comp_id, name in self.data.compilations:
            destination = f"compilacao:{comp_id}"
            active = self.current == destination
            dot = ft.Container(
                width=s(8), height=s(8),
                border_radius=ft.BorderRadius.all(s(2)),
                border=ft.Border.all(1.5, c.colors["gold"] if active else c.colors["faint"]),
                bgcolor=c.colors["gold"] if active else None,
            )
            projects.append(self._item(destination, None, name, leading=dot))
        projects.append(self._item("Compilações", "folder-open", "Todas as compilações", len(self.data.compilations)))

        explore = [self._item(dest, ic, label) for dest, ic, label in EXPLORE_ITEMS]

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Column(main, spacing=s(1), tight=True),
                    ft.Column([self._group_head("Compilações", add_comp), *projects], spacing=s(1), tight=True),
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
