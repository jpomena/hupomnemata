"""Paleta de busca ⌘K: obras, fragmentos e ações."""

from collections.abc import Callable

import flet as ft

from src.utils.fa import fa_icon
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.ui_kit import s

Action = tuple[str, str, str | None, Callable[[], None]]


class CommandPalette:
    """Diálogo leve com busca incremental e navegação por teclado."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        search: Callable[[str], dict],
        on_open_work: Callable[[int], None],
        on_open_fragments: Callable[[str], None],
        actions: list[Action],
    ) -> None:
        self.page = page
        self.config = config
        self.search = search
        self.on_open_work = on_open_work
        self.on_open_fragments = on_open_fragments
        self.actions = actions
        self.items: list[tuple[str, str, str | None, Callable[[], None]]] = []
        self.index = 0
        self.is_open = False
        self.dialog: ft.AlertDialog | None = None
        self.results = ft.Column(spacing=s(1), tight=True, scroll=ft.ScrollMode.AUTO)

    # ── dados ──────────────────────────────────────────────

    def _collect(self, query: str) -> list[tuple[str | None, list]]:
        query = query.strip()
        found = self.search(query) if query else self.search("")
        groups: list[tuple[str | None, list]] = []
        works = found.get("works", [])[: 6 if query else 4]
        if works:
            groups.append(("Obras", [(icon, title, sub, (lambda wid=wid: self.on_open_work(wid))) for wid, title, sub, icon in works]))
        fragments = found.get("fragments", [])[:4] if query else []
        if fragments:
            groups.append(("Fragmentos", [("quote-left", excerpt, work, (lambda q=query: self.on_open_fragments(q))) for _fid, excerpt, work in fragments]))
        lowered = query.lower()
        actions = [(ic, label, hint, run) for ic, label, hint, run in self.actions if not lowered or lowered in label.lower()]
        if actions:
            groups.append(("Ações", actions))
        return groups

    # ── render ─────────────────────────────────────────────

    def _row(self, position: int, icon_name: str, title: str, sub: str | None) -> ft.Container:
        c = self.config
        selected = position == self.index
        controls: list[ft.Control] = [
            fa_icon(icon_name, size=s(12), color=c.colors["gold"] if selected else c.colors["faint"]),
            ui.ui_text(c, title.replace("\n", " "), size=13, weight=ui.W500, expand=True),
        ]
        if sub:
            controls.append(ft.Container(ui.ui_text(c, sub, size=12, color=c.colors["faint"]), width=s(200), alignment=ft.Alignment.CENTER_RIGHT))
        return ft.Container(
            content=ft.Row(controls, spacing=s(10), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=s(36),
            padding=ft.Padding.symmetric(horizontal=s(8)),
            border_radius=ft.BorderRadius.all(s(6)),
            bgcolor=c.colors["selected"] if selected else None,
            on_click=lambda _e, p=position: self._run(p),
        )

    def _render(self, query: str = "") -> None:
        c = self.config
        self.items = []
        controls: list[ft.Control] = []
        for group, entries in self._collect(query):
            controls.append(ft.Container(ui.ui_text(c, group, size=12, weight=ui.W600, color=c.colors["faint"]), padding=ft.Padding.only(left=s(8), top=s(8), bottom=s(4))))
            for icon_name, title, sub, run in entries:
                controls.append(self._row(len(self.items), icon_name, title, sub))
                self.items.append((icon_name, title, sub, run))
        if not self.items:
            controls.append(ft.Container(ui.ui_text(c, f"Nada encontrado para “{query}”.", size=13, color=c.colors["faint"]), padding=s(12)))
        self.index = min(self.index, max(len(self.items) - 1, 0))
        self.results.controls = controls

    def _run(self, position: int) -> None:
        if not 0 <= position < len(self.items):
            return
        run = self.items[position][3]
        self.close()
        run()

    def open(self) -> None:
        c = self.config
        self.query = ui.search_field(c, "Buscar obras, fragmentos e ações", on_change=self._on_change, width=None, expand=True, autofocus=True, on_submit=lambda _e: self._run(self.index))
        self.query.border_color = "transparent"
        self.query.focused_border_color = "transparent"
        self.query.height = s(48)
        self.query.bgcolor = c.colors["surface"]
        self._render()
        footer = ft.Container(
            ft.Row(
                [
                    ft.Row([ui.kbd(c, "↑"), ui.kbd(c, "↓"), ui.ui_text(c, "navegar", size=12, color=c.colors["faint"])], spacing=s(4), tight=True),
                    ft.Row([ui.kbd(c, "↵"), ui.ui_text(c, "abrir", size=12, color=c.colors["faint"])], spacing=s(4), tight=True),
                    ft.Row([ui.kbd(c, "esc"), ui.ui_text(c, "fechar", size=12, color=c.colors["faint"])], spacing=s(4), tight=True),
                ],
                spacing=s(16),
            ),
            padding=ft.Padding.symmetric(horizontal=s(16), vertical=s(8)),
            bgcolor=c.colors["chrome"],
            border=ft.Border.only(top=ft.BorderSide(1, c.colors["border"])),
        )
        body = ft.Container(
            width=s(620),
            content=ft.Column(
                [
                    ft.Container(self.query, padding=ft.Padding.symmetric(horizontal=s(8)), border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"]))),
                    ft.Container(self.results, padding=s(6), height=s(380)),
                    footer,
                ],
                spacing=0,
                tight=True,
            ),
        )
        self.dialog = ft.AlertDialog(
            content=body,
            content_padding=0,
            bgcolor=c.colors["surface"],
            shape=ft.RoundedRectangleBorder(radius=s(10)),
            alignment=ft.Alignment.TOP_CENTER,
            inset_padding=ft.Padding.only(top=s(110)),
            barrier_color=ft.Colors.with_opacity(0.6, c.colors["black"]),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            on_dismiss=lambda _e: setattr(self, "is_open", False),
        )
        self.is_open = True
        self.page.show_dialog(self.dialog)

    def close(self) -> None:
        self.is_open = False
        if self.dialog is not None:
            try:
                self.page.pop_dialog()
            except Exception:
                pass

    def _on_change(self, event) -> None:
        self.index = 0
        self._render(event.control.value or "")
        self.results.update()

    def handle_key(self, key: str) -> bool:
        if key in ("Arrow Down", "Arrow Up"):
            if not self.items:
                return True
            step = 1 if key == "Arrow Down" else -1
            self.index = max(0, min(len(self.items) - 1, self.index + step))
            self._render(self.query.value or "")
            self.results.update()
            return True
        if key == "Escape":
            self.close()
            return True
        return False
