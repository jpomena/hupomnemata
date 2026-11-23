"""Campos de formulário, rótulos e estados de erro.

Extraído de ``src/views/ui_kit.py``; a fachada reexporta a API pública.
"""

import flet as ft
from collections.abc import Callable
from collections.abc import Sequence
from src.utils.types import ViewConfig
from src.utils.fa import fa_icon
from ._foundation import UI_TRACKING, W500, W600, s
from ._typography import ui_text


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
