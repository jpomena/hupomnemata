"""Utilitários compartilhados pelas telas de Compilações (lista e página).

Os estilos vêm de ``src/views/ui_kit.py``. Aqui ficam só as peças que as
telas de compilação repetem: campos de formulário com rótulo acima, diálogo
padrão, menu ``⋯``, caixa com largura máxima e formatação de datas.
"""

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import TypeVar

import flet as ft

from src.utils.fa import fa_icon
from src.utils.types import ViewConfig, ViewReference
from src.views import ui_kit as ui
from src.views.ui_kit import s

EventControl = TypeVar('EventControl', bound=ft.Control)

MONTHS = (
    'jan', 'fev', 'mar', 'abr', 'mai', 'jun',
    'jul', 'ago', 'set', 'out', 'nov', 'dez',
)

# Item de menu: (ícone, rótulo, ação, perigo). ``None`` vira divisória.
MenuItem = tuple[str, str, Callable[[], object], bool] | None


def _control_list(*controls: ft.Control) -> list[ft.Control]:
    """Converte argumentos variáveis de controles em uma lista mutável."""
    return list(controls)


def plural(count: int, singular: str, plural_form: str) -> str:
    return f'{count} {singular if count == 1 else plural_form}'


def fmt_date(value: object) -> str:
    """Data curta (“9 nov 2026”). O SQLite grava em UTC; mostramos no fuso local."""
    if value is None or value == '':
        return ''
    moment: datetime | None
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace(' ', 'T'))
        except ValueError:
            return str(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone()
    return f'{moment.day} {MONTHS[moment.month - 1]} {moment.year}'


def reference_plain(reference: ViewReference | None) -> str:
    if reference is None:
        return ''
    return ''.join(part.content for part in reference.parts).strip()


def reference_text(c: ViewConfig, reference: ViewReference, size: float = 12) -> ft.Text:
    """Referência ABNT com negrito e itálico preservados."""
    spans: list[ft.TextSpan] = []
    for part in reference.parts:
        style = getattr(part.style, 'value', part.style)
        spans.append(
            ft.TextSpan(
                part.content,
                style=ft.TextStyle(
                    weight=ui.W600 if style == 'bold' else None,
                    italic=style == 'italic',
                    color=c.colors['text'] if style == 'bold' else None,
                ),
            )
        )
    return ft.Text(
        spans=spans,
        size=s(size),
        color=c.colors['muted'],
        font_family=c.font_families['montserrat'],
        selectable=True,
        style=ft.TextStyle(height=1.6, letter_spacing=ui.UI_TRACKING),
    )


def text_input(
    c: ViewConfig,
    value: str = '',
    hint: str | None = None,
    multiline: bool = False,
    min_lines: int = 3,
    max_lines: int = 6,
    max_length: int | None = None,
    autofocus: bool = False,
    on_submit: Callable | None = None,
    text_align: ft.TextAlign | None = None,
) -> ft.TextField:
    """Campo de texto do kit: fundo do canvas, borda de 1 px, foco dourado."""
    colors = c.colors
    resolved_align = (
        text_align
        if text_align is not None
        else (ft.TextAlign.JUSTIFY if multiline else ft.TextAlign.START)
    )
    return ft.TextField(
        value=value,
        hint_text=hint,
        multiline=multiline,
        min_lines=min_lines if multiline else None,
        max_lines=max_lines if multiline else None,
        max_length=max_length,
        autofocus=autofocus,
        on_submit=on_submit,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=s(10), vertical=s(10)),
        text_size=s(13),
        text_style=ft.TextStyle(font_family=c.font_families['montserrat'], color=colors['text'], weight=ui.W500),
        hint_style=ft.TextStyle(font_family=c.font_families['montserrat'], color=colors['faint'], weight=ui.W500),
        counter_style=ft.TextStyle(font_family=c.font_families['montserrat'], color=colors['faint'], size=s(11)),
        color=colors['text'],
        bgcolor=colors['bg'],
        filled=True,
        fill_color=colors['bg'],
        border_color=colors['border_strong'],
        focused_border_color=colors['gold'],
        border_width=1,
        focused_border_width=1,
        border_radius=ft.BorderRadius.all(s(6)),
        cursor_color=colors['gold'],
        text_align=resolved_align,
    )


def form_field(c: ViewConfig, label: str, control: ft.Control, hint: str | None = None) -> ft.Column:
    """Rótulo acima do campo, como pede o DESIGN.md."""
    controls: list[ft.Control] = [ui.ui_text(c, label, size=12, weight=ui.W600, color=c.colors['muted']), control]
    if hint:
        controls.append(ui.meta_text(c, hint, max_lines=2))
    return ft.Column(controls, spacing=s(6), tight=True)


def dropdown_option(c: ViewConfig, key: str, label: str) -> ft.DropdownOption:
    return ft.DropdownOption(
        key=key,
        text=label,
        content=ui.ui_text(c, label, size=13, color=c.colors['text']),
    )


def select_input(
    c: ViewConfig,
    value: str | None,
    options: Sequence[tuple[str, str]],
    on_select: Callable | None = None,
    disabled: bool = False,
    width: float | None = None,
) -> ft.Dropdown:
    colors = c.colors
    return ft.Dropdown(
        value=value,
        options=[dropdown_option(c, key, label) for key, label in options],
        on_select=on_select,
        disabled=disabled,
        width=s(width) if width else None,
        dense=True,
        text_size=s(13),
        text_style=ft.TextStyle(font_family=c.font_families['montserrat'], color=colors['text'], size=s(13), weight=ui.W500),
        label_style=ft.TextStyle(font_family=c.font_families['montserrat'], color=colors['muted'], size=s(12), weight=ui.W600),
        content_padding=ft.Padding.symmetric(horizontal=s(10), vertical=s(6)),
        color=colors['text'],
        bgcolor=colors['surface'],
        fill_color=colors['bg'],
        filled=True,
        border_color=colors['border_strong'],
        focused_border_color=colors['gold'],
        border_width=1,
        border_radius=ft.BorderRadius.all(s(6)),
    )


def dialog(
    c: ViewConfig,
    title: str,
    controls: Sequence[ft.Control],
    actions: Sequence[ft.Control],
    width: float = 520,
    subtitle: str | None = None,
) -> ft.AlertDialog:
    """Diálogo padrão do redesign: superfície, raio 10, título em Montserrat 15/600."""
    head: list[ft.Control] = [ui.ui_text(c, title, size=15, weight=ui.W600)]
    if subtitle:
        head.append(ui.ui_text(c, subtitle, size=12, color=c.colors['faint'], max_lines=2))
    return ft.AlertDialog(
        modal=True,
        bgcolor=c.colors['surface'],
        title=ft.Column(head, spacing=s(4), tight=True),
        title_padding=ft.Padding.only(left=s(20), right=s(20), top=s(18), bottom=s(4)),
        content=ft.Column(list(controls), tight=True, width=s(width), spacing=s(14)),
        content_padding=ft.Padding.only(left=s(20), right=s(20), top=s(12), bottom=s(8)),
        actions=list(actions),
        actions_padding=ft.Padding.only(left=s(20), right=s(20), top=s(8), bottom=s(18)),
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=s(10)),
    )


def more_menu(
    c: ViewConfig,
    items: Sequence[MenuItem],
    tooltip: str = 'Mais ações',
    boxed: bool = False,
    size: float = 28,
) -> ft.PopupMenuButton:
    """Botão ``⋯`` com menu suspenso."""
    menu_items: list[ft.PopupMenuItem] = []
    for item in items:
        if item is None:
            menu_items.append(ft.PopupMenuItem())
            continue
        icon_name, label, action, danger = item
        color = c.colors['danger'] if danger else c.colors['text']
        menu_items.append(
            ft.PopupMenuItem(
                content=ft.Row(
                    [
                        fa_icon(icon_name, size=s(12), color=c.colors['danger'] if danger else c.colors['faint'], style='regular'),
                        ui.ui_text(c, label, size=13, color=color),
                    ],
                    spacing=s(10),
                    tight=True,
                ),
                height=s(32),
                on_click=lambda _e, run=action: run(),
                data=label,
            )
        )
    return ft.PopupMenuButton(
        content=ui.icon_button(c, 'ellipsis', tooltip=None, boxed=boxed, size=size),
        items=menu_items,
        tooltip=tooltip,
        bgcolor=c.colors['surface'],
        elevation=6,
        menu_padding=ft.Padding.symmetric(vertical=s(4)),
        shape=ft.RoundedRectangleBorder(radius=s(8)),
        menu_position=ft.PopupMenuPosition.UNDER,
    )


def menu_labels(menu: ft.PopupMenuButton) -> list[str]:
    return [item.data for item in menu.items if item.data]


def run_menu_item(menu: ft.PopupMenuButton, label: str) -> None:
    """Dispara um item do menu pelo rótulo (usado nos testes e atalhos)."""
    item = next(item for item in menu.items if item.data == label)
    if callable(item.on_click):
        try:
            item.on_click(None)  # type: ignore
        except TypeError:
            item.on_click()  # type: ignore


def max_width_box(c: ViewConfig, content: ft.Control, max_width: float, gutter: float = 0) -> ft.Container:
    """Centraliza ``content`` com largura máxima, encolhendo em janelas estreitas."""
    inner = ft.Container(content=content, width=s(max_width))
    host = ft.Container(
        content=ft.Row([inner], alignment=ft.MainAxisAlignment.CENTER),
    )

    def _resize(event) -> None:
        width = getattr(event, 'width', None)
        if not width:
            return
        target = max(s(320), min(s(max_width), width - s(gutter)))
        if abs((inner.width or 0) - target) < 1:
            return
        inner.width = target
        try:
            inner.update()
        except Exception:
            pass

    host.on_size_change = _resize
    return host
