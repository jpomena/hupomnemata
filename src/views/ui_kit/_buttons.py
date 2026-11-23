"""Botões, botões de ícone e links de ação.

Extraído de ``src/views/ui_kit.py``; a fachada reexporta a API pública.
"""

import flet as ft
from collections.abc import Callable
from src.utils.types import ViewConfig
from src.utils.fa import fa_icon
from src.utils.control_safety import safe_update, set_control_prop
from ._foundation import W500, W600, alpha, s
from ._motion import MOTION_FAST, MOTION_INSTANT, fade, motion
from ._typography import ui_text


def button(
    c: ViewConfig,
    label: str,
    on_click: Callable | None = None,
    icon_name: str | None = None,
    variant: str = "default",
    small: bool = False,
    disabled: bool = False,
    tooltip: str | None = None,
    icon_style: str = "solid",
    expand: bool | int | None = None,
) -> ft.Container:
    """Botão padrão. Variantes: default, primary, ghost, danger."""
    colors = c.colors
    palette = {
        "default": (colors["surface"], colors["border_strong"], colors["text"], colors["card_hover"], colors["faint"]),
        "primary": (colors["gold"], colors["gold"], colors["on_gold"], colors["gold_hover"], colors["gold_hover"]),
        "ghost": (None, None, colors["muted"], colors["card_hover"], None),
        "danger": (colors["surface"], colors["border_strong"], colors["danger"], alpha(colors["danger"], 0.10), colors["danger"]),
    }[variant]
    bg, border, fg, hover_bg, hover_border = palette
    height = s(28 if small else 32)
    text = ui_text(
        c, label, size=12 if small else 13,
        weight=W600 if variant == "primary" else W500,
        color=fg,
    )
    row_controls: list[ft.Control] = []
    if icon_name:
        row_controls.append(fa_icon(icon_name, size=s(12 if small else 13), color=fg, style=icon_style))
    row_controls.append(text)
    box = ft.Container(
        content=ft.Row(
            controls=row_controls,
            spacing=s(6),
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        height=height,
        padding=ft.Padding.symmetric(horizontal=s(8 if small else 12)),
        bgcolor=bg,
        border=ft.Border.all(1, border) if border else None,
        border_radius=ft.BorderRadius.all(s(6)),
        alignment=ft.Alignment.CENTER if expand else None,
        tooltip=tooltip,
        expand=expand,
        opacity=0.5 if disabled else 1.0,
        animate=motion(MOTION_INSTANT),
        on_click=None if disabled else on_click,
    )
    box.data = {"label": text, "variant": variant}

    def _hover(e):
        if disabled:
            return
        hovering = e.data in (True, "true")
        set_control_prop(
            box,
            'bgcolor',
            hover_bg if hovering else bg,
        )
        if hover_border and border:
            set_control_prop(
                box,
                'border',
                ft.Border.all(1, hover_border if hovering else border),
            )
        safe_update(box)

    box.on_hover = _hover
    return box


def flash_button(button_box: ft.Container, label: str, revert_to: str, page: ft.Page | None = None) -> None:
    """Troca o rótulo do botão por um aviso curto (ex.: “Copiada”)."""
    data = getattr(button_box, "data", None) or {}
    text = data.get("label")
    if text is None:
        return
    set_control_prop(text, 'value', label)
    try:
        text.update()
    except Exception:
        return

    async def _revert():
        import asyncio
        await asyncio.sleep(1.5)
        set_control_prop(text, 'value', revert_to)
        safe_update(text)

    if page is not None and hasattr(page, "run_task"):
        page.run_task(_revert)


def icon_button(
    c: ViewConfig,
    icon_name: str,
    on_click: Callable | None = None,
    tooltip: str | None = None,
    boxed: bool = False,
    size: float = 28,
    color: str | None = None,
    style: str = "solid",
    disabled: bool = False,
    hover_color: str | None = None,
    small: bool = False,
) -> ft.Container:
    colors = c.colors
    btn_size = 22 if small else size
    glyph_size = 11 if small else 13
    glyph = fa_icon(icon_name, size=s(glyph_size), color=color or colors["faint"], style=style)
    glyph.animate_scale = motion(MOTION_FAST)
    box = ft.Container(
        content=glyph,
        width=s(btn_size),
        height=s(btn_size),
        alignment=ft.Alignment.CENTER,
        border_radius=ft.BorderRadius.all(s(6)),
        border=ft.Border.all(1, colors["border_strong"]) if boxed else None,
        tooltip=tooltip,
        opacity=0.35 if disabled else 1.0,
        animate=motion(MOTION_FAST),
        animate_opacity=fade(MOTION_FAST),
        on_click=None if disabled else on_click,
    )

    def _hover(e):
        if disabled:
            return
        hovering = e.data in (True, "true")
        set_control_prop(
            box,
            'bgcolor',
            colors['card_hover'] if hovering else None,
        )
        if boxed:
            set_control_prop(
                box,
                'border',
                ft.Border.all(
                    1,
                    colors['gold']
                    if hovering
                    else colors['border_strong'],
                ),
            )
        set_control_prop(
            glyph,
            'color',
            (hover_color or colors['gold'])
            if hovering
            else (color or colors['faint']),
        )
        set_control_prop(
            glyph,
            'scale',
            1.08 if hovering else 1.0,
        )
        safe_update(box)

    box.on_hover = _hover
    return box


def link_button(c: ViewConfig, label: str, on_click: Callable | None = None, trailing_icon: str | None = "chevron-right") -> ft.Container:
    text = ui_text(c, label, size=13, color=c.colors["muted"])
    controls: list[ft.Control] = [text]
    glyph = None
    if trailing_icon:
        glyph = fa_icon(trailing_icon, size=s(10), color=c.colors["muted"])
        glyph.animate_offset = motion(MOTION_FAST)
        controls.append(glyph)
    box = ft.Container(
        content=ft.Row(controls, spacing=s(4), tight=True),
        on_click=on_click,
        animate=motion(MOTION_FAST),
    )

    def _hover(e):
        hovering = e.data in (True, "true")
        set_control_prop(
            text,
            'color',
            c.colors['gold'] if hovering else c.colors['muted'],
        )
        if glyph is not None:
            set_control_prop(glyph, 'color', text.color)
            set_control_prop(
                glyph,
                'offset',
                ft.Offset(0.18, 0) if hovering else ft.Offset(0, 0),
            )
        # O link não tem bgcolor própria; a atribuição idempotente apenas
        # desfaz o congelamento antes do update.
        set_control_prop(box, 'bgcolor', None)
        safe_update(box)

    box.on_hover = _hover
    return box
