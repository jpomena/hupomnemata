from collections.abc import Callable
from typing import TYPE_CHECKING, cast
from src.utils.types import ViewConfig
import flet as ft

if TYPE_CHECKING:
    from src.domains import Author


class MultipleAuthors:
    def __init__(self) -> None:
        pass

    def compose(
        self,
        authors: list['Author'],
        on_select: Callable[[int], None],
        on_create_new: Callable[[], None],
        on_cancel: Callable[[], None],
        config: ViewConfig
    ) -> ft.AlertDialog:
        TEXT_STYLE = {
                "font_family": config.font_families["montserrat"],
                "size": 16,
                "color": config.colors['text']
            }

        def close_modal() -> None:
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

        authors_btns: list[ft.Control] = [
            cast(
                ft.Control,
                ft.TextButton(
                    content=ft.Text(
                        f'{author.given_names} {author.last_name}',
                        **TEXT_STYLE
                    ),
                    on_click=lambda event, author_id=author.id: choose_author(
                        author_id
                    ),
                ),
            )
            for author in authors
        ]
        content_controls: list[ft.Control] = [
            cast(
                ft.Control,
                ft.Text(
                    'Encontramos autores com nome semelhante. Selecione um '
                    'cadastro existente ou confirme a criação de um novo '
                    'autor.',
                    **TEXT_STYLE
                ),
            ),
            cast(ft.Control, ft.Column(controls=authors_btns, tight=True)),
        ]
        self.modal = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                'Possível autor já cadastrado', **TEXT_STYLE,
                align=ft.Alignment.CENTER
            ),
            bgcolor=config.colors['bg'],
            content=ft.Column(
                controls=content_controls,
                tight=True,
                height=300,
                width=300*1.618
            ),
            actions=[
                ft.TextButton(
                    content=ft.Text('Cancelar', **TEXT_STYLE),
                    on_click=lambda event: cancel()
                ),
                ft.ElevatedButton(
                    content=ft.Text('Cadastrar novo autor', **TEXT_STYLE),
                    on_click=lambda event: create_new()
                ),
            ],
        )
        return self.modal
