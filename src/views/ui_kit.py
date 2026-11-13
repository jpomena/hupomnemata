"""Componentes visuais compartilhados do redesign (v2).

Todas as telas usam estas peças para manter a mesma estrutura: cabeçalho de
página, barra de ferramentas, cards, botões, badges, abas e estados vazios.
As regras de cor, tipografia e espaço estão em ``design/DESIGN.md``.

Os tamanhos passam por ``s()``, que aplica a escala da interface escolhida em
Configurações (``set_scale`` é chamado pelo ``CoreComposer``).
"""

from collections.abc import Callable, Sequence

import flet as ft

from src.utils.fa import fa_icon
from src.utils.types import ViewConfig

_SCALE = 1.0

W400 = ft.FontWeight.W_400
W500 = ft.FontWeight.W_500
W600 = ft.FontWeight.W_600
W700 = ft.FontWeight.W_700

UI_TRACKING = -0.08


def set_scale(scale: float) -> None:
    global _SCALE
    _SCALE = max(0.6, min(float(scale or 1.0), 1.6))


def s(value: float) -> float:
    """Aplica a escala da interface a um tamanho em pixels."""
    return round(value * _SCALE, 2)


def alpha(color: str, opacity: float) -> str:
    return ft.Colors.with_opacity(opacity, color)


# ── tipografia ─────────────────────────────────────────────


def ui_text(
    c: ViewConfig,
    value: str,
    size: float = 13,
    weight: ft.FontWeight = W500,
    color: str | None = None,
    max_lines: int | None = 1,
    expand: bool | int | None = None,
    selectable: bool = False,
    italic: bool = False,
    tabular: bool = False,
    align: ft.TextAlign | None = None,
) -> ft.Text:
    """Texto de interface em Montserrat."""
    del tabular  # Flet 0.86 não expõe font features; Montserrat já tem algarismos alinhados
    return ft.Text(
        value=value,
        size=s(size),
        weight=weight,
        color=color or c.colors["text"],
        font_family=c.font_families["montserrat"],
        max_lines=max_lines,
        overflow=ft.TextOverflow.ELLIPSIS if max_lines else None,
        no_wrap=max_lines == 1,
        expand=expand,
        selectable=selectable,
        italic=italic,
        text_align=align,
        style=ft.TextStyle(letter_spacing=UI_TRACKING),
    )


def serif_text(
    c: ViewConfig,
    value: str,
    size: float = 18,
    weight: ft.FontWeight = W600,
    color: str | None = None,
    max_lines: int | None = None,
    italic: bool = False,
    selectable: bool = False,
    height: float | None = 1.5,
    expand: bool | int | None = None,
    align: ft.TextAlign | None = None,
    no_wrap: bool | None = None,
) -> ft.Text:
    """Texto de leitura em Cormorant (citações, sínteses, títulos)."""
    return ft.Text(
        value=value,
        size=s(size),
        weight=weight,
        color=color or c.colors["text"],
        font_family=c.font_families["cormorant"],
        max_lines=max_lines,
        overflow=ft.TextOverflow.ELLIPSIS if max_lines else None,
        no_wrap=(max_lines == 1) if no_wrap is None else no_wrap,
        expand=expand,
        text_align=align,
        italic=italic,
        selectable=selectable,
        style=ft.TextStyle(height=height),
    )


def label_text(c: ViewConfig, value: str, color: str | None = None) -> ft.Text:
    """Rótulo de seção: Montserrat 12/600, sem caixa alta."""
    return ui_text(c, value, size=12, weight=W600, color=color or c.colors["muted"])


def meta_text(c: ViewConfig, value: str, max_lines: int | None = 1) -> ft.Text:
    return ui_text(c, value, size=12, weight=W500, color=c.colors["faint"], max_lines=max_lines, tabular=True)


def icon(c: ViewConfig, name: str, size: float = 14, color: str | None = None, style: str = "solid") -> ft.Text:
    return fa_icon(name, size=s(size), color=color or c.colors["faint"], style=style)


# ── botões ─────────────────────────────────────────────────


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
        animate=ft.Animation(100, ft.AnimationCurve.EASE_OUT),
        on_click=None if disabled else on_click,
    )
    box.data = {"label": text, "variant": variant}

    def _hover(e):
        if disabled:
            return
        hovering = e.data in (True, "true")
        box.bgcolor = hover_bg if hovering else bg
        if hover_border and border:
            box.border = ft.Border.all(1, hover_border if hovering else border)
        box.update()

    box.on_hover = _hover
    return box


def flash_button(button_box: ft.Container, label: str, revert_to: str, page: ft.Page | None = None) -> None:
    """Troca o rótulo do botão por um aviso curto (ex.: “Copiada”)."""
    data = getattr(button_box, "data", None) or {}
    text = data.get("label")
    if text is None:
        return
    text.value = label
    try:
        text.update()
    except Exception:
        return

    async def _revert():
        import asyncio
        await asyncio.sleep(1.5)
        text.value = revert_to
        try:
            text.update()
        except Exception:
            pass

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
    box = ft.Container(
        content=glyph,
        width=s(btn_size),
        height=s(btn_size),
        alignment=ft.Alignment.CENTER,
        border_radius=ft.BorderRadius.all(s(6)),
        border=ft.Border.all(1, colors["border_strong"]) if boxed else None,
        tooltip=tooltip,
        opacity=0.35 if disabled else 1.0,
        animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
        on_click=None if disabled else on_click,
    )

    def _hover(e):
        if disabled:
            return
        hovering = e.data in (True, "true")
        box.bgcolor = colors["card_hover"] if hovering else None
        if boxed:
            box.border = ft.Border.all(1, colors["gold"] if hovering else colors["border_strong"])
        glyph.color = (hover_color or colors["gold"]) if hovering else (color or colors["faint"])
        try:
            box.update()
        except Exception:
            pass

    box.on_hover = _hover
    return box


def link_button(c: ViewConfig, label: str, on_click: Callable | None = None, trailing_icon: str | None = "chevron-right") -> ft.Container:
    text = ui_text(c, label, size=13, color=c.colors["muted"])
    controls: list[ft.Control] = [text]
    glyph = None
    if trailing_icon:
        glyph = fa_icon(trailing_icon, size=s(10), color=c.colors["muted"])
        controls.append(glyph)
    box = ft.Container(content=ft.Row(controls, spacing=s(4), tight=True), on_click=on_click)

    def _hover(e):
        hovering = e.data in (True, "true")
        text.color = c.colors["gold"] if hovering else c.colors["muted"]
        if glyph is not None:
            glyph.color = text.color
        box.update()

    box.on_hover = _hover
    return box


# ── peças de layout ────────────────────────────────────────


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
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT) if (interactive or on_click or on_hover) else None,
    )

    if interactive or on_click or on_hover:
        def _hover(e):
            hovering = e.data in (True, "true")
            box.bgcolor = colors["card_hover"] if hovering else colors["surface"]
            box.border = hover_border if hovering else normal_border
            if on_hover:
                on_hover(hovering)
            try:
                box.update()
            except Exception:
                pass

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
) -> ft.Container:
    controls: list[ft.Control] = [
        fa_icon(icon_name, size=s(18), color=c.colors["faint"], style="regular"),
        ui_text(c, title, size=13, weight=W600),
        ui_text(c, body, size=13, color=c.colors["muted"], max_lines=3),
    ]
    if action is not None:
        controls.append(ft.Container(action, margin=ft.Margin.only(top=s(4))))
    return ft.Container(
        content=ft.Column(controls, spacing=s(8), tight=True),
        padding=s(24),
        bgcolor=c.colors["surface"],
        border=ft.Border.all(1, c.colors["border"]),
        border_radius=ft.BorderRadius.all(s(8)),
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
        parts: list[ft.Control] = [ui_text(c, label, size=13, color=colors["text"] if active else colors["muted"])]
        if count is not None:
            parts.append(ui_text(c, str(count), size=12, color=colors["faint"], tabular=True))
        buttons.append(
            ft.Container(
                content=ft.Row(parts, spacing=s(6), tight=True),
                height=s(26),
                padding=ft.Padding.symmetric(horizontal=s(10)),
                border_radius=ft.BorderRadius.all(s(4)),
                bgcolor=colors["surface"] if active else None,
                border=ft.Border.all(1, colors["border_strong"]) if active else None,
                alignment=ft.Alignment.CENTER,
                on_click=lambda _e, k=key: on_select(k),
            )
        )
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
        )
    return ft.Container(
        content=ft.Row(
            [fa_icon("plus", size=s(11), color=colors["muted"]), ui_text(c, label, size=13, color=colors["muted"])],
            spacing=s(6),
            tight=True,
        ),
        height=s(32),
        padding=ft.Padding.symmetric(horizontal=s(10)),
        border=ft.Border.all(1, colors["border_strong"]),
        border_radius=ft.BorderRadius.all(s(6)),
        on_click=on_click,
    )


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
        parts: list[ft.Control] = [ui_text(c, label, size=13, weight=W600 if active else W500, color=colors["text"] if active else colors["faint"])]
        if count is not None:
            parts.append(
                ft.Container(
                    ui_text(c, str(count), size=12, color=colors["faint"], tabular=True),
                    bgcolor=colors["card_hover"],
                    border_radius=ft.BorderRadius.all(s(4)),
                    padding=ft.Padding.symmetric(horizontal=s(5)),
                )
            )
        controls.append(
            ft.Container(
                content=ft.Row(parts, spacing=s(6), tight=True),
                height=s(40),
                alignment=ft.Alignment.CENTER,
                border=ft.Border.only(bottom=ft.BorderSide(2, colors["gold"] if active else "transparent")),
                on_click=lambda _e, k=key: on_select(k),
            )
        )
    return ft.Container(
        content=ft.Row(controls, spacing=s(24)),
        padding=ft.Padding.only(left=s(padding_left), right=s(padding_left)),
        border=ft.Border.only(bottom=ft.BorderSide(1, colors["border"])),
    )


def hover_surface(
    c: ViewConfig,
    content: ft.Control,
    on_click: Callable | None = None,
    selected: bool = False,
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
    base_bg = colors["selected"] if selected else base
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
        animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
    )

    def _hover(e):
        hovering = e.data in (True, "true")
        if not selected:
            box.bgcolor = colors["card_hover"] if hovering else base
            if hover_border is not None:
                box.border = hover_border if hovering else normal_border
            if on_hover:
                on_hover(hovering)
            try:
                box.update()
            except Exception:
                pass

    box.on_hover = _hover
    return box


def toast(page: ft.Page, c: ViewConfig, message: str, icon_name: str = "circle-check", on_undo: Callable | None = None) -> None:
    """Aviso curto no canto. Com ``on_undo`` vira aviso de desfazer (6 s)."""
    colors = c.colors
    snack = ft.SnackBar(
        content=ft.Row(
            [
                fa_icon(icon_name, size=s(13), color=colors["bg"], style="regular"),
                ui_text(c, message, size=13, color=colors["bg"], max_lines=2, expand=True),
            ],
            spacing=s(10),
        ),
        bgcolor=colors["text"],
        duration=6000 if on_undo else 3000,
        action=ft.SnackBarAction(label="Desfazer", text_color=colors["gold"], on_click=lambda _e: on_undo()) if on_undo else None,
        behavior=ft.SnackBarBehavior.FLOATING,
        width=s(420),
        shape=ft.RoundedRectangleBorder(radius=s(8)),
    )
    page.show_dialog(snack)


# ── formulário ─────────────────────────────────────────────
# Rótulo 12/600 acima do campo, campo de 32 px com borda de 1 px
# (``border_strong``), foco dourado e erro com borda ``danger`` e mensagem
# abaixo. Sem espaçamento de letras.


def input_field(
    c: ViewConfig,
    value: str = "",
    hint: str | None = None,
    on_change: Callable | None = None,
    multiline: bool = False,
    min_lines: int = 1,
    max_lines: int | None = None,
    keyboard_type: ft.KeyboardType | None = None,
    input_filter: ft.InputFilter | None = None,
    expand: bool | int | None = True,
    width: float | None = None,
    on_submit: Callable | None = None,
    prefix_icon: str | None = None,
    autofocus: bool = False,
    text_align: ft.TextAlign | None = None,
) -> ft.TextField:
    """Campo de texto do padrão v2 (sem rótulo flutuante; use ``form_field``)."""
    colors = c.colors
    resolved_align = (
        text_align
        if text_align is not None
        else (ft.TextAlign.JUSTIFY if multiline else ft.TextAlign.START)
    )
    text_style = ft.TextStyle(
        font_family=c.font_families["cormorant"],
        color=colors["text"],
        weight=W600,
        size=s(17),
        height=1.4 if multiline else None,
    )
    hint_style = ft.TextStyle(
        font_family=c.font_families["cormorant"],
        color=colors.get("faint", colors["muted"]),
        weight=W600,
        size=s(17),
        letter_spacing=UI_TRACKING,
    )
    prefix = None
    if prefix_icon:
        prefix = ft.Container(
            fa_icon(prefix_icon, size=s(12), color=colors.get("faint", colors["muted"])),
            padding=ft.Padding.only(left=s(6), right=s(6)),
        )
    return ft.TextField(
        value=value,
        hint_text=hint,
        on_change=on_change,
        on_submit=on_submit,
        multiline=multiline,
        min_lines=min_lines if multiline else None,
        max_lines=max_lines if multiline else 1,
        keyboard_type=keyboard_type,
        input_filter=input_filter,
        expand=expand,
        width=s(width) if width else None,
        height=None if multiline else s(36),
        autofocus=autofocus,
        dense=True,
        prefix=prefix,
        content_padding=ft.Padding.only(
            left=s(4 if prefix else 10), right=s(10), top=s(8), bottom=s(8)
        ),
        text_size=s(17),
        text_style=text_style,
        hint_style=hint_style,
        bgcolor=colors["bg"],
        border_color=colors.get("border_strong", colors["border"]),
        focused_border_color=colors["gold"],
        border_width=1,
        focused_border_width=1,
        border_radius=ft.BorderRadius.all(s(6)),
        cursor_color=colors["gold"],
        text_align=resolved_align,
    )


def dropdown_field(
    c: ViewConfig,
    options: Sequence[str | tuple[str, str]],
    value: str | None = None,
    on_select: Callable | None = None,
    expand: bool | int | None = None,
    width: float | None = None,
) -> ft.Dropdown:
    """Menu de seleção do padrão v2. ``options`` aceita textos ou ``(chave, texto)``."""
    colors = c.colors
    text_style = ft.TextStyle(
        font_family=c.font_families["cormorant"],
        color=colors["text"],
        weight=W600,
        size=s(16),
    )
    built: list[ft.DropdownOption] = []
    for option in options:
        key, text = option if isinstance(option, tuple) else (option, option)
        built.append(
            ft.DropdownOption(
                key=key,
                text=text,
                content=ft.Text(
                    text,
                    size=s(16),
                    weight=W600,
                    color=colors["text"],
                    font_family=c.font_families["cormorant"],
                ),
            )
        )
    return ft.Dropdown(
        value=value,
        options=built,
        on_select=on_select,
        expand=expand,
        width=s(width) if width else None,
        expanded_insets=None if width else ft.Padding.all(0),
        dense=True,
        text_size=s(16),
        text_style=text_style,
        content_padding=ft.Padding.only(left=s(10), right=s(6), top=s(6), bottom=s(6)),
        bgcolor=colors["surface"],
        fill_color=colors["bg"],
        filled=True,
        border_color=colors.get("border_strong", colors["border"]),
        focused_border_color=colors["gold"],
        border_width=1,
        focused_border_width=1,
        border_radius=ft.BorderRadius.all(s(6)),
        trailing_icon=fa_icon("chevron-down", size=s(10), color=colors.get("faint", colors["muted"])),
        selected_trailing_icon=fa_icon("chevron-up", size=s(10), color=colors.get("faint", colors["muted"])),
    )


def checkbox(
    c: ViewConfig,
    label: str,
    value: bool = False,
    on_change: Callable | None = None,
) -> ft.Checkbox:
    """Checkbox de 16 px: borda neutra, marcado em dourado."""
    colors = c.colors
    return ft.Checkbox(
        label=label,
        value=value,
        on_change=on_change,
        label_position=ft.LabelPosition.RIGHT,
        label_style=ft.TextStyle(
            size=s(13),
            weight=W500,
            color=colors["text"],
            font_family=c.font_families["montserrat"],
        ),
        fill_color={
            ft.ControlState.SELECTED: colors["gold"],
            ft.ControlState.DEFAULT: colors["bg"],
        },
        check_color=colors.get("on_gold", colors["bg"]),
        border_side={
            ft.ControlState.SELECTED: ft.BorderSide(1, colors["gold"]),
            ft.ControlState.HOVERED: ft.BorderSide(1, colors["muted"]),
            ft.ControlState.DEFAULT: ft.BorderSide(1, colors.get("faint", colors["muted"])),
        },
        shape=ft.RoundedRectangleBorder(radius=s(4)),
        splash_radius=0,
        visual_density=ft.VisualDensity.COMPACT,
    )


def field_label(c: ViewConfig, label: str, required: bool = False) -> ft.Text:
    """Rótulo de campo (12/600) com asterisco dourado quando obrigatório."""
    colors = c.colors
    spans = [ft.TextSpan(" *", style=ft.TextStyle(color=colors["gold"], weight=W600))] if required else []
    return ft.Text(
        label,
        spans=spans,
        size=s(12),
        weight=W600,
        color=colors["muted"],
        font_family=c.font_families["montserrat"],
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )


def form_field(
    c: ViewConfig,
    label: str | None,
    control: ft.Control,
    required: bool = False,
    help_text: str | None = None,
    expand: bool | int | None = True,
    error_target: ft.Control | None = None,
) -> ft.Column:
    """Rótulo acima, controle e linha de ajuda ou erro abaixo.

    O controle não deve ter ``expand`` (aqui ele seria vertical); a largura vem
    do ``STRETCH``. ``expand`` do próprio ``form_field`` vale para a ``Row``
    que o contém. ``data`` guarda ``control``, ``error_target`` (o campo que ganha a borda de
    erro), ``message`` e ``help`` para ``set_field_error``.
    """
    colors = c.colors
    message_icon = fa_icon("circle-exclamation", size=s(11), color=colors["danger"])
    message_icon.visible = False
    message_text = ui_text(
        c, help_text or "", size=12, color=colors.get("faint", colors["muted"]), max_lines=3
    )
    message = ft.Row(
        [message_icon, ft.Container(message_text, expand=True)],
        spacing=s(4),
        visible=bool(help_text),
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
    controls: list[ft.Control] = []
    if label:
        controls.append(field_label(c, label, required))
    controls.extend([control, message])
    wrapper = ft.Column(
        controls,
        spacing=s(6),
        expand=expand,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    wrapper.data = {
        "control": control,
        "error_target": error_target or control,
        "message": message,
        "message_icon": message_icon,
        "message_text": message_text,
        "help": help_text,
        "error": None,
    }
    return wrapper


def set_field_error(c: ViewConfig, wrapper: ft.Control, message: str | None) -> None:
    """Liga ou desliga o estado de erro de um ``form_field`` (sem ``update``)."""
    data = getattr(wrapper, "data", None)
    if not isinstance(data, dict):
        return
    colors = c.colors
    data["error"] = message
    target = data.get("error_target")
    normal_border = colors.get("border_strong", colors["border"])
    if target is not None and hasattr(target, "border_color"):
        target.border_color = colors["danger"] if message else normal_border
        if hasattr(target, "focused_border_color"):
            target.focused_border_color = colors["danger"] if message else colors["gold"]
    text = data["message_text"]
    help_text = data.get("help")
    text.value = message or help_text or ""
    text.color = colors["danger"] if message else colors.get("faint", colors["muted"])
    data["message_icon"].visible = bool(message)
    data["message"].visible = bool(message or help_text)
