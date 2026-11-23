"""Toasts, diálogos e modais.

Extraído de ``src/views/ui_kit.py``; a fachada reexporta a API pública.
"""

import flet as ft
from collections.abc import Callable
from collections.abc import Sequence
from src.utils.types import ViewConfig
from src.utils.fa import fa_icon
from src.utils.control_safety import safe_execute
from src.utils.control_safety import safe_update
from ._foundation import W600, s
from ._typography import ui_text


def toast(
    page: ft.Page,
    c: ViewConfig,
    message: str,
    icon_name: str = "circle-check",
    on_undo: Callable | None = None,
) -> None:
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
        action=(
            ft.SnackBarAction(
                label="Desfazer",
                text_color=colors["gold"],
                on_click=lambda _e: on_undo(),
            )
            if on_undo
            else None
        ),
        behavior=ft.SnackBarBehavior.FLOATING,
        width=s(420),
        shape=ft.RoundedRectangleBorder(radius=s(8)),
    )
    if page:
        page.show_dialog(snack)
        safe_update(page)


def open_dialog(page: ft.Page | None, dialog_control: ft.Control) -> None:
    """Abre um diálogo ou modal na página e garante atualização síncrona do display."""
    if not page:
        return
    safe_execute('abrir diálogo', page.show_dialog, dialog_control)
    safe_update(page)


def close_dialog(page: ft.Page | None) -> None:
    """Fecha o diálogo aberto no topo da pilha (pop_dialog) e garante atualização segura da página."""
    if not page:
        return
    safe_execute('fechar diálogo', page.pop_dialog)
    safe_update(page)


def dialog(
    c: ViewConfig,
    title: str,
    controls: Sequence[ft.Control],
    actions: Sequence[ft.Control],
    width: float = 520,
    subtitle: str | None = None,
    page: ft.Page | None = None,
    on_dismiss: Callable | None = None,
    dismissible: bool = False,
) -> ft.AlertDialog:
    """Diálogo modal padrão do redesign: superfície, raio 10, título em Montserrat 15/600."""
    head: list[ft.Control] = [ui_text(c, title, size=15, weight=W600)]
    if subtitle:
        head.append(ui_text(c, subtitle, size=12, color=c.colors["faint"], max_lines=2))

    def _handle_dismiss(e):
        if on_dismiss:
            safe_execute('dismiss do diálogo', on_dismiss, e)
        p = getattr(e, "page", None) or page
        if p:
            safe_update(p)

    dlg = ft.AlertDialog(
        modal=not dismissible,
        bgcolor=c.colors["surface"],
        title=ft.Column(head, spacing=s(4), tight=True),
        title_padding=ft.Padding.only(left=s(20), right=s(20), top=s(18), bottom=s(4)),
        content=ft.Column(
            list(controls),
            tight=True,
            width=s(width),
            spacing=s(14),
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        content_padding=ft.Padding.only(left=s(20), right=s(20), top=s(12), bottom=s(8)),
        actions=list(actions),
        actions_padding=ft.Padding.only(left=s(20), right=s(20), top=s(8), bottom=s(18)),
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=s(10)),
        on_dismiss=_handle_dismiss,
    )
    if page:
        open_dialog(page, dlg)
    return dlg


modal = dialog
