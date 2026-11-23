"""Peças de layout: cards, cabeçalhos, abas e filtros.

Extraído de ``src/views/ui_kit.py``; a fachada reexporta a API pública.
"""

import flet as ft
from collections.abc import Callable
from collections.abc import Sequence
from src.utils.types import ViewConfig
from src.utils.fa import fa_icon
from src.utils.control_safety import safe_update
from ._foundation import W500, W600, W700, alpha, s
from ._motion import MOTION_BASE, MOTION_FAST, motion
from ._typography import serif_text, ui_text
from ._buttons import icon_button


def badge(
    c: ViewConfig,
    label: str,
    icon_name: str | None = None,
    accent: bool = False,
    variant: str = "default",
) -> ft.Container:
    colors = c.colors
    is_accent = accent or variant in ("gold", "accent", "primary")
    fg = colors["gold"] if is_accent else colors["muted"]
    controls: list[ft.Control] = []
    if icon_name:
        controls.append(fa_icon(icon_name, size=s(10), color=fg, style="regular"))
    controls.append(ui_text(c, label, size=11, weight=W600, color=fg, tabular=True))
    box = ft.Container(
        content=ft.Row(controls, spacing=s(4), tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        height=s(20),
        padding=ft.Padding.symmetric(horizontal=s(7)),
        border_radius=ft.BorderRadius.all(s(4)),
        bgcolor=alpha(colors["gold"], 0.12) if is_accent else colors["bg"],
        border=ft.Border.all(1, alpha(colors["gold"], 0.12) if is_accent else colors["border_strong"]),
    )
    box.data = {"label": label, "variant": variant, "accent": is_accent}
    return box


def kbd(c: ViewConfig, label: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(label, size=s(10.5), color=c.colors["faint"], font_family=c.font_families["mono"]),
        padding=ft.Padding.symmetric(horizontal=s(4)),
        height=s(18),
        border=ft.Border(
            top=ft.BorderSide(1, c.colors["border_strong"]),
            left=ft.BorderSide(1, c.colors["border_strong"]),
            right=ft.BorderSide(1, c.colors["border_strong"]),
            bottom=ft.BorderSide(2, c.colors["border_strong"]),
        ),
        border_radius=ft.BorderRadius.all(s(4)),
    )


def divider(c: ViewConfig) -> ft.Container:
    return ft.Container(height=1, bgcolor=c.colors["border"])


def card(
    c: ViewConfig,
    controls: Sequence[ft.Control],
    expand: bool | int | None = None,
    danger: bool = False,
    interactive: bool = False,
    on_click: Callable | None = None,
    on_hover: Callable[[bool], None] | None = None,
    padding: ft.Padding | float | None = None,
    accent_left: bool = True,
) -> ft.Container:
    colors = c.colors
    normal_border = ft.Border.all(1, alpha(colors["danger"], 0.35) if danger else colors["border"])
    hover_border = (
        ft.Border(
            left=ft.BorderSide(s(3), colors["gold"]),
            top=ft.BorderSide(1, colors["border_strong"]),
            right=ft.BorderSide(1, colors["border_strong"]),
            bottom=ft.BorderSide(1, colors["border_strong"]),
        )
        if accent_left
        else ft.Border.all(1, colors["border_strong"])
    )
    col = ft.Column(list(controls), spacing=0, tight=True)
    body = ft.Container(content=col, padding=padding) if padding else col
    box = ft.Container(
        content=body,
        bgcolor=colors["surface"],
        border=normal_border,
        border_radius=ft.BorderRadius.all(s(8)),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        expand=expand,
        on_click=on_click,
        animate=motion(MOTION_BASE) if (interactive or on_click or on_hover) else None,
    )

    if interactive or on_click or on_hover:
        def _hover(e):
            hovering = e.data in (True, "true")
            box.bgcolor = colors["card_hover"] if hovering else colors["surface"]
            box.border = hover_border if hovering else normal_border
            if on_hover:
                on_hover(hovering)
            safe_update(box)

        box.on_hover = _hover

    return box


def interactive_card(
    c: ViewConfig,
    controls: Sequence[ft.Control],
    on_click: Callable | None = None,
    expand: bool | int | None = None,
    danger: bool = False,
    on_hover: Callable[[bool], None] | None = None,
    padding: ft.Padding | float | None = None,
    accent_left: bool = True,
) -> ft.Container:
    """Card interativo com realces visuais (borda dourada lateral de 3px, fundo card_hover e animação de 150ms)."""
    return card(
        c=c,
        controls=controls,
        expand=expand,
        danger=danger,
        interactive=True,
        on_click=on_click,
        on_hover=on_hover,
        padding=padding,
        accent_left=accent_left,
    )


def card_head(
    c: ViewConfig,
    title: str,
    trailing: ft.Control | None = None,
    count: int | None = None,
    serif: bool = True,
) -> ft.Container:
    title_text = (
        serif_text(c, title, size=17, weight=W700, color=c.colors["text"])
        if serif
        else ui_text(c, title, size=13, weight=W600)
    )
    left: list[ft.Control] = [title_text]
    if count is not None:
        left.append(ui_text(c, str(count), size=12, color=c.colors["faint"], tabular=True))
    head_box = ft.Container(
        content=ft.Row(
            controls=[ft.Row(left, spacing=s(8), tight=True)] + ([trailing] if trailing else []),
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        height=s(44),
        padding=ft.Padding.only(left=s(16), right=s(12)),
        border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
    )
    head_box.data = {"title": title_text}
    return head_box


def page_header(
    c: ViewConfig,
    title: str,
    description: str | None = None,
    actions: Sequence[ft.Control] = (),
    meta: Sequence[ft.Control] = (),
) -> ft.Container:
    """Cabeçalho padrão de todas as telas: H1 em Cormorant, descrição e ações."""
    left: list[ft.Control] = [
        ft.Text(
            title,
            size=s(30),
            weight=W700,
            color=c.colors["text"],
            font_family=c.font_families["cormorant"],
            style=ft.TextStyle(height=1.1),
        )
    ]
    if description:
        left.append(ui_text(c, description, size=13, color=c.colors["muted"], max_lines=2))
    if meta:
        left.append(ft.Container(ft.Row(list(meta), spacing=s(8), wrap=True), margin=ft.Margin.only(top=s(8))))
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Column(left, spacing=s(4), expand=True, tight=True),
                ft.Row(list(actions), spacing=s(8), tight=True),
            ],
            vertical_alignment=ft.CrossAxisAlignment.END,
            spacing=s(24),
        ),
        padding=ft.Padding.only(left=s(32), right=s(32), top=s(28), bottom=s(20)),
        bgcolor=c.colors.get("surface", c.colors["bg"]),
        border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
    )


def toolbar(c: ViewConfig, controls: Sequence[ft.Control], trailing: Sequence[ft.Control] = ()) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            controls=list(controls) + [ft.Container(expand=True)] + list(trailing),
            spacing=s(8),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.only(left=s(32), right=s(32), top=s(10), bottom=s(10)),
        height=s(54),
    )


def search_field(
    c: ViewConfig,
    hint: str,
    on_change: Callable | None = None,
    value: str = "",
    width: float | None = 280,
    expand: bool | int | None = None,
    autofocus: bool = False,
    on_submit: Callable | None = None,
) -> ft.TextField:
    colors = c.colors
    return ft.TextField(
        value=value,
        hint_text=hint,
        on_change=on_change,
        on_submit=on_submit,
        width=s(width) if width else None,
        expand=expand,
        autofocus=autofocus,
        height=s(34),
        dense=True,
        content_padding=ft.Padding.only(left=s(0), right=s(10), top=s(8), bottom=s(8)),
        prefix_icon=ft.Container(fa_icon("magnifying-glass", size=s(12), color=colors["faint"]), width=s(30), alignment=ft.Alignment.CENTER),
        text_size=s(16),
        text_style=ft.TextStyle(font_family=c.font_families["cormorant"], color=colors["text"], weight=W600, size=s(16)),
        hint_style=ft.TextStyle(font_family=c.font_families["cormorant"], color=colors["faint"], weight=W600, size=s(16)),
        bgcolor=colors["bg"],
        border_color=colors["border_strong"],
        focused_border_color=colors["gold"],
        border_width=1,
        focused_border_width=1,
        border_radius=ft.BorderRadius.all(s(6)),
        cursor_color=colors["gold"],
    )


def empty_state(
    c: ViewConfig,
    icon_name: str,
    title: str,
    body: str,
    action: ft.Control | None = None,
    width: float | None = 560,
) -> ft.Container:
    controls: list[ft.Control] = [
        fa_icon(icon_name, size=s(20), color=c.colors["faint"], style="regular"),
        ui_text(c, title, size=14, weight=W600, color=c.colors["text"]),
        ui_text(c, body, size=13, color=c.colors["muted"], max_lines=3),
    ]
    if action is not None:
        controls.append(ft.Container(action, margin=ft.Margin.only(top=s(6))))
    return ft.Container(
        content=ft.Column(controls, spacing=s(8), tight=True),
        padding=s(24),
        bgcolor=c.colors["surface"],
        border=ft.Border.all(1, c.colors["border"]),
        border_radius=ft.BorderRadius.all(s(8)),
        width=s(width) if width else None,
    )


def props(c: ViewConfig, rows: Sequence[tuple[str, ft.Control | str | None]], label_width: float = 104) -> ft.Column:
    """Lista de propriedades (rótulo à esquerda, valor à direita)."""
    out: list[ft.Control] = []
    for label, value in rows:
        if value in (None, ""):
            continue
        value_control = ui_text(c, str(value), size=13, max_lines=None, tabular=True, selectable=True) if isinstance(value, (str, int, float)) else value
        out.append(
            ft.Row(
                controls=[
                    ft.Container(ui_text(c, label, size=13, color=c.colors["faint"], max_lines=2), width=s(label_width), padding=ft.Padding.only(right=s(8))),
                    ft.Container(value_control, expand=True),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=0,
            )
        )
    return ft.Column(out, spacing=s(10), tight=True)


def segmented(
    c: ViewConfig,
    options: Sequence[tuple[str, str, int | None]],
    selected: str,
    on_select: Callable[[str], None],
) -> ft.Container:
    colors = c.colors
    buttons: list[ft.Control] = []
    for key, label, count in options:
        active = key == selected
        label_ctrl = ui_text(c, label, size=13, color=colors["text"] if active else colors["muted"])
        parts: list[ft.Control] = [label_ctrl]
        if count is not None:
            parts.append(ui_text(c, str(count), size=12, color=colors["faint"], tabular=True))
        option_box = ft.Container(
            content=ft.Row(parts, spacing=s(6), tight=True),
            height=s(26),
            padding=ft.Padding.symmetric(horizontal=s(10)),
            border_radius=ft.BorderRadius.all(s(4)),
            bgcolor=colors["surface"] if active else None,
            border=ft.Border.all(1, colors["border_strong"]) if active else None,
            alignment=ft.Alignment.CENTER,
            animate=motion(MOTION_BASE),
            on_click=lambda _e, k=key: on_select(k),
        )

        def _hover(e, box=option_box, text=label_ctrl, is_active=active):
            hovering = e.data in (True, "true")
            if is_active:
                return
            box.bgcolor = colors["card_hover"] if hovering else None
            text.color = colors["text"] if hovering else colors["muted"]
            safe_update(box)

        option_box.on_hover = _hover
        buttons.append(option_box)
    return ft.Container(
        content=ft.Row(buttons, spacing=s(2), tight=True),
        padding=s(2),
        bgcolor=colors["chrome"],
        border=ft.Border.all(1, colors["border"]),
        border_radius=ft.BorderRadius.all(s(6)),
    )


def chip_filter(
    c: ViewConfig,
    label: str,
    on_click: Callable | None = None,
    active_value: str | None = None,
    on_clear: Callable | None = None,
) -> ft.Control:
    """Filtro inativo (“+ Tipo”, borda tracejada) ou ativo (“Tipo: Valor ×”)."""
    colors = c.colors
    if active_value:
        return ft.Container(
            content=ft.Row(
                [
                    ui_text(c, f"{label}:", size=13, color=colors["text"]),
                    ui_text(c, active_value, size=13, weight=W600, color=colors["gold"]),
                    icon_button(c, "xmark", on_click=on_clear, tooltip=f"Remover filtro de {label.lower()}", size=22),
                ],
                spacing=s(6),
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s(32),
            padding=ft.Padding.only(left=s(10), right=s(4)),
            bgcolor=colors["surface"],
            border=ft.Border.all(1, colors["border_strong"]),
            border_radius=ft.BorderRadius.all(s(6)),
            animate=motion(MOTION_FAST),
        )
    trigger = ft.Container(
        content=ft.Row(
            [fa_icon("plus", size=s(11), color=colors["muted"]), ui_text(c, label, size=13, color=colors["muted"])],
            spacing=s(6),
            tight=True,
        ),
        height=s(32),
        padding=ft.Padding.symmetric(horizontal=s(10)),
        border=ft.Border.all(1, colors["border_strong"]),
        border_radius=ft.BorderRadius.all(s(6)),
        animate=motion(MOTION_FAST),
        on_click=on_click,
    )

    def _hover(e):
        hovering = e.data in (True, "true")
        trigger.bgcolor = colors["card_hover"] if hovering else None
        trigger.border = ft.Border.all(1, colors["gold"] if hovering else colors["border_strong"])
        safe_update(trigger)

    trigger.on_hover = _hover
    return trigger


def tabs(
    c: ViewConfig,
    items: Sequence[tuple[str, str, int | None]],
    selected: str,
    on_select: Callable[[str], None],
    padding_left: float = 32,
) -> ft.Container:
    colors = c.colors
    controls: list[ft.Control] = []
    for key, label, count in items:
        active = key == selected
        label_ctrl = ui_text(c, label, size=13, weight=W600 if active else W500, color=colors["text"] if active else colors["faint"])
        parts: list[ft.Control] = [label_ctrl]
        if count is not None:
            parts.append(
                ft.Container(
                    ui_text(c, str(count), size=12, color=colors["faint"], tabular=True),
                    bgcolor=colors["card_hover"],
                    border_radius=ft.BorderRadius.all(s(4)),
                    padding=ft.Padding.symmetric(horizontal=s(5)),
                )
            )
        tab_box = ft.Container(
            content=ft.Row(parts, spacing=s(6), tight=True),
            height=s(40),
            padding=ft.Padding.symmetric(horizontal=s(8)),
            border_radius=ft.BorderRadius.only(top_left=s(4), top_right=s(4)),
            alignment=ft.Alignment.CENTER,
            border=ft.Border.only(bottom=ft.BorderSide(2, colors["gold"] if active else "transparent")),
            animate=motion(MOTION_BASE),
            on_click=lambda _e, k=key: on_select(k),
        )

        def _hover(e, box=tab_box, text=label_ctrl, is_active=active):
            hovering = e.data in (True, "true")
            if is_active:
                return
            box.bgcolor = alpha(colors["gold"], 0.05) if hovering else None
            box.border = ft.Border.only(
                bottom=ft.BorderSide(2, alpha(colors["gold"], 0.45) if hovering else "transparent")
            )
            text.color = colors["text"] if hovering else colors["faint"]
            safe_update(box)

        tab_box.on_hover = _hover
        controls.append(tab_box)
    return ft.Container(
        content=ft.Row(controls, spacing=s(24)),
        padding=ft.Padding.only(left=s(padding_left), right=s(padding_left)),
        border=ft.Border.only(bottom=ft.BorderSide(1, colors["border"])),
    )


def hover_surface(
    c: ViewConfig,
    content: ft.Control,
    on_click: Callable | None = None,
    selected: bool | Callable[[], bool] = False,
    padding: ft.Padding | float | None = None,
    height: float | None = None,
    radius: float | ft.BorderRadius = 6,
    base: str | None = None,
    on_hover: Callable[[bool], None] | None = None,
    border: ft.Border | None = None,
    hover_border: ft.Border | None = None,
    accent_left: bool = False,
) -> ft.Container:
    colors = c.colors
    is_selected = selected if callable(selected) else (lambda: selected)
    base_bg = colors["selected"] if is_selected() else base
    normal_border = border
    if accent_left and hover_border is None:
        hover_border = ft.Border(
            left=ft.BorderSide(s(3), colors["gold"]),
            top=ft.BorderSide(1, colors["border_strong"]),
            right=ft.BorderSide(1, colors["border_strong"]),
            bottom=ft.BorderSide(1, colors["border_strong"]),
        )
    if isinstance(radius, ft.BorderRadius):
        b_radius = radius
    elif radius:
        b_radius = ft.BorderRadius.all(s(radius))
    else:
        b_radius = None

    box = ft.Container(
        content=content,
        on_click=on_click,
        padding=padding,
        height=height,
        bgcolor=base_bg,
        border=normal_border,
        border_radius=b_radius,
        animate=motion(MOTION_FAST),
    )

    def _hover(e):
        hovering = e.data in (True, "true")
        if not is_selected():
            box.bgcolor = colors["card_hover"] if hovering else base
            if hover_border is not None:
                box.border = hover_border if hovering else normal_border
            if on_hover:
                on_hover(hovering)
            safe_update(box)

    box.on_hover = _hover
    return box
