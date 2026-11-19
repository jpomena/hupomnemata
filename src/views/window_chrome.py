"""Chrome da janela: barra de titulo, controles, historico e breadcrumb."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import flet as ft

from src.utils.fa import fa_icon
from src.utils.fa import glyph as fa_glyph
from src.views import ui_kit as ui
from src.views.sidebar import SidebarData
from src.views.ui_kit import MOTION_FAST, motion, s

if TYPE_CHECKING:
    from src.views.core_composer import CoreComposer


class WindowChromeComposer:
    """Compoe o chrome da janela em nome de um ``CoreComposer``."""

    def __init__(self, composer: "CoreComposer"):
        self.composer = composer

    def window_control_button(
        self,
        icon_name: str,
        on_click: Callable[..., object] | None,
        tooltip: str | None = None,
        danger: bool = False,
    ) -> ft.Container:
        c = self.composer.config
        glyph = fa_icon(icon_name, size=s(12), color=c.colors["faint"], style="regular" if icon_name in {"square", "clone"} else "solid")
        box = ft.Container(
            content=glyph,
            width=s(46),
            height=s(c.ui.get("titlebar_height", 40)),
            alignment=ft.Alignment.CENTER,
            tooltip=tooltip,
            animate=motion(MOTION_FAST),
            animate_opacity=motion(MOTION_FAST),
            on_click=on_click,
        )

        def _hover(e):
            hovering = e.data in (True, "true")
            box.bgcolor = (c.colors["danger"] if danger else c.colors["card_hover"]) if hovering else None
            glyph.color = (c.colors["on_gold"] if danger else c.colors["text"]) if hovering else c.colors["faint"]
            box.update()

        box.on_hover = _hover
        box.data = glyph
        return box

    def compose_title_bar(self) -> ft.WindowDragArea:
        composer = self.composer
        c = composer.config

        def minimize_window(_):
            composer.page.window.minimized = True
            composer.page.update()

        def toggle_maximize_window(_):
            if composer.on_toggle_maximize is not None:
                composer.on_toggle_maximize()
            else:
                composer.page.window.maximized = not composer.page.window.maximized
                composer.page.update()

        async def close_window(_):
            await composer.page.window.close()

        is_maximized = bool(
            getattr(getattr(composer.page, "window", None), "maximized", False)
        )
        composer.maximize_button = self.window_control_button(
            "clone" if is_maximized else "square",
            toggle_maximize_window,
            "Restaurar" if is_maximized else "Maximizar",
        )
        brand_text = ft.Text(
            value=c.texts["app"]["name_normalized"],
            size=s(24),
            color=c.colors["text"],
            font_family=c.font_families["greek"],
            style=ft.TextStyle(letter_spacing=1.2),
            text_align=ft.TextAlign.CENTER,
            no_wrap=True,
        )
        brand = ft.Container(
            content=brand_text,
            width=s(c.ui["sidebar_width"]),
            alignment=ft.Alignment.CENTER,
            border=ft.Border.only(right=ft.BorderSide(1, c.colors["border"])),
            on_click=lambda _e: composer.on_navigate("dashboard"),
            animate=motion(MOTION_FAST),
        )

        def _on_hover_brand(e):
            hovering = e.data in (True, "true")
            brand_text.color = c.colors["gold"] if hovering else c.colors["text"]
            try:
                brand.update()
            except (RuntimeError, AttributeError):
                pass

        brand.on_hover = _on_hover_brand
        composer.back_button = ui.icon_button(
            c, "arrow-left", on_click=lambda _e: composer.on_history(-1) if composer.on_history else None,
            tooltip="Voltar (⌘[)", disabled=not composer.can_go_back,
        )
        composer.forward_button = ui.icon_button(
            c, "arrow-right", on_click=lambda _e: composer.on_history(1) if composer.on_history else None,
            tooltip="Avançar (⌘])", disabled=not composer.can_go_forward,
        )
        composer.history_host = ft.Container(
            ft.Row([composer.back_button, composer.forward_button], spacing=s(2), tight=True),
            padding=ft.Padding.only(left=s(12), right=s(8)),
        )
        composer.crumbs_host = ft.Row(self.crumb_controls(), spacing=s(2), expand=True, tight=True)
        controls = ft.Row(
            [
                self.window_control_button("minus", minimize_window, "Minimizar"),
                composer.maximize_button,
                self.window_control_button("xmark", close_window, "Fechar", danger=True),
            ],
            spacing=0,
            tight=True,
        )
        return ft.WindowDragArea(
            content=ft.Container(
                content=ft.Row(
                    [brand, composer.history_host, composer.crumbs_host, controls],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=c.colors["chrome"],
                border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
                height=s(c.ui.get("titlebar_height", 40)),
            )
        )

    def crumb_parts(self) -> list[tuple[str, str | None]]:
        dest = self.composer.current_destination
        labels = {"dashboard": "Início"}
        if dest.startswith("compilacao:"):
            name = self.compilation_name(int(dest.split(":", 1)[1])) or "Compilação"
            return [("Compilações", "Compilações"), (name, None)]
        return [(labels.get(dest, dest), None)]

    def crumb_controls(self) -> list[ft.Control]:
        composer = self.composer
        c = composer.config
        parts = self.crumb_parts()
        out: list[ft.Control] = []
        for index, (label, target) in enumerate(parts):
            last = index == len(parts) - 1
            text = ui.ui_text(c, label, size=13, weight=ui.W500, color=c.colors["text"] if last else c.colors["faint"])
            if target and not last:
                out.append(ui.hover_surface(c, text, on_click=lambda _e, t=target: composer.on_navigate(t), padding=ft.Padding.symmetric(horizontal=s(6), vertical=s(3)), radius=4))
                out.append(fa_icon("chevron-right", size=s(9), color=c.colors["faint"]))
            else:
                out.append(ft.Container(text, padding=ft.Padding.symmetric(horizontal=s(6))))
        return out

    def compilation_name(self, compilation_id: int) -> str | None:
        get_sidebar_data = self.composer.get_sidebar_data
        data = get_sidebar_data() if get_sidebar_data else SidebarData()
        return next((name for cid, name in data.compilations if cid == compilation_id), None)

    def set_history_state(self, can_back: bool, can_forward: bool) -> None:
        composer = self.composer
        composer.can_go_back = can_back
        composer.can_go_forward = can_forward
        host = getattr(composer, "history_host", None)
        if host is None:
            return
        composer.back_button = ui.icon_button(composer.config, "arrow-left", on_click=lambda _e: composer.on_history(-1) if composer.on_history else None, tooltip="Voltar (⌘[)", disabled=not can_back)
        composer.forward_button = ui.icon_button(composer.config, "arrow-right", on_click=lambda _e: composer.on_history(1) if composer.on_history else None, tooltip="Avançar (⌘])", disabled=not can_forward)
        host.content = ft.Row([composer.back_button, composer.forward_button], spacing=s(2), tight=True)
        try:
            host.update()
        except (RuntimeError, AttributeError):
            pass

    def refresh_crumbs(self) -> None:
        """Reconstroi o breadcrumb a partir da navegacao atual."""
        host = getattr(self.composer, "crumbs_host", None)
        if host is None:
            return
        host.controls = self.crumb_controls()
        try:
            host.update()
        except (RuntimeError, AttributeError):
            pass

    def update_window_state(self, is_maximized: bool) -> None:
        """Atualiza o icone de maximizar/restaurar sem recriar a UI."""
        button = getattr(self.composer, "maximize_button", None)
        if button is None:
            return
        glyph = button.data
        if glyph is not None:
            char, family = fa_glyph("clone" if is_maximized else "square", "regular")
            glyph.value = char
            glyph.font_family = family
        button.tooltip = "Restaurar" if is_maximized else "Maximizar"
        try:
            button.update()
        except (RuntimeError, AttributeError):
            pass
