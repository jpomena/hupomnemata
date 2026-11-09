"""Pop-ups gerais do cadastro (v2)."""

from collections.abc import Callable
from typing import TYPE_CHECKING

import flet as ft

from src.utils.types import ViewConfig
from src.views import ui_kit as ui

if TYPE_CHECKING:
    from src.domains import Author


def _author_name(author: 'Author') -> str:
    if getattr(author, 'corporation', False):
        return author.given_names
    return f'{author.given_names} {author.last_name}'.strip()


class MultipleAuthorsPopup:
    """Pergunta se o autor digitado já existe no acervo antes de criar outro."""

    def __init__(self) -> None:
        self.modal: ft.AlertDialog | None = None

    def compose(
        self,
        authors: list['Author'],
        on_select: Callable[[int], None],
        on_create_new: Callable[[], None],
        on_cancel: Callable[[], None],
        config: ViewConfig
    ) -> ft.AlertDialog:
        c = config
        faint = c.colors.get('faint', c.colors['muted'])

        def close_modal() -> None:
            if self.modal is None:
                return
            self.modal.open = False
            self.modal.update()

        def choose_author(author_id: int) -> None:
            close_modal()
            on_select(author_id)

        def create_new() -> None:
            close_modal()
            on_create_new()

        def cancel() -> None:
            close_modal()
            on_cancel()

        def author_row(author: 'Author') -> ft.Control:
            initials = getattr(author, 'given_names_initials', '') or ''
            detail = (
                'Instituição'
                if getattr(author, 'corporation', False)
                else f'{author.last_name.upper()}, {initials}'.rstrip(', ')
            )
            return ui.hover_surface(
                c,
                ft.Row(
                    [
                        ui.fa_icon(
                            'building-columns'
                            if getattr(author, 'corporation', False)
                            else 'user',
                            size=ui.s(13),
                            color=faint,
                            style='regular',
                        ),
                        ft.Column(
                            [
                                ui.ui_text(c, _author_name(author), size=13, weight=ui.W600),
                                ui.ui_text(c, detail, size=12, color=faint),
                            ],
                            spacing=ui.s(1),
                            tight=True,
                            expand=True,
                        ),
                        ui.ui_text(c, 'Usar este', size=12, color=c.colors['muted']),
                    ],
                    spacing=ui.s(12),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=lambda event, author_id=author.id: choose_author(
                    author_id
                ),
                padding=ft.Padding.symmetric(horizontal=ui.s(10), vertical=ui.s(8)),
            )

        author_list = ft.Container(
            content=ft.Column(
                [author_row(author) for author in authors],
                spacing=ui.s(2),
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=ui.s(4),
            border=ft.Border.all(1, c.colors['border']),
            border_radius=ft.BorderRadius.all(ui.s(8)),
            bgcolor=c.colors['bg'],
        )

        self.modal = ft.AlertDialog(
            modal=True,
            title=ui.ui_text(c, 'Possível autor já cadastrado', size=15, weight=ui.W600),
            bgcolor=c.colors['surface'],
            shape=ft.RoundedRectangleBorder(radius=ui.s(10)),
            title_padding=ft.Padding.only(
                left=ui.s(24), right=ui.s(24), top=ui.s(20), bottom=ui.s(4)
            ),
            content_padding=ft.Padding.only(
                left=ui.s(24), right=ui.s(24), top=ui.s(12), bottom=ui.s(8)
            ),
            actions_padding=ft.Padding.only(
                left=ui.s(24), right=ui.s(16), top=ui.s(8), bottom=ui.s(16)
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ui.ui_text(
                            c,
                            'Encontramos autores com nome semelhante. Escolha um '
                            'cadastro existente para não duplicar o autor, ou '
                            'cadastre um novo.',
                            size=13,
                            color=c.colors['muted'],
                            max_lines=4,
                        ),
                        author_list,
                    ],
                    tight=True,
                    spacing=ui.s(16),
                    width=ui.s(460),
                ),
                animate_size=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            ),
            actions=[
                ui.button(
                    c, 'Cancelar', on_click=lambda event: cancel(), variant='ghost'
                ),
                ui.button(
                    c,
                    'Cadastrar novo autor',
                    on_click=lambda event: create_new(),
                    icon_name='user-plus',
                ),
            ],
        )
        return self.modal
