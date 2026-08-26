import flet as ft
from src.configs.settings import COLORS


def create_book_modal(page: ft.Page) -> ft.AlertDialog:
    """
    Cria e retorna o modal de inserção de obras compatível com Flet moderno.
    Utiliza estritamente o dicionário COLORS do projeto e separa estilos
    compatíveis.
    """

    base_input_style = {
        "border_color": COLORS["border"],
        "focused_border_color": COLORS["gold"],
        "cursor_color": COLORS["gold"],
        "color": COLORS["text"],
        "label_style": ft.TextStyle(color=COLORS["muted"]),
        "border_radius": 4,
        "content_padding": 12,
        "bgcolor": COLORS["surface"]
    }

    dropdown_style = {
        "border_color": COLORS["border"],
        "focused_border_color": COLORS["gold"],
        "color": COLORS["text"],
        "label_style": ft.TextStyle(color=COLORS["muted"]),
        "border_radius": 4,
        "content_padding": 12,
        "bgcolor": COLORS["surface"]
    }

    input_title = ft.TextField(
        label="Título da Obra *",
        autofocus=True, expand=True,
        **base_input_style
    )
    input_author = ft.TextField(
        label="Autor(es) / Organizador(es) *",
        expand=True, **base_input_style
    )

    input_year = ft.TextField(
        label="Ano", width=100,
        keyboard_type=ft.KeyboardType.NUMBER, **base_input_style
    )
    input_publisher = ft.TextField(
        label="Editora", expand=True, **base_input_style
    )

    input_isbn = ft.TextField(
        label="ISBN / DOI", expand=True, **base_input_style
    )
    input_type = ft.Dropdown(
        label="Tipo",
        width=150,
        options=[
            ft.dropdown.Option("Livro"),
            ft.dropdown.Option("Artigo"),
            ft.dropdown.Option("Tese/Dissertação"),
            ft.dropdown.Option("Outro")
        ],
        **dropdown_style
    )

    form_content = ft.Column(
        controls=[
            ft.Text(
                "Cadastrar Nova Obra", size=22,
                weight=ft.FontWeight.W_500, color=COLORS["text"]
            ),
            ft.Divider(color=COLORS["border"], height=20),
            ft.Row([input_title]),
            ft.Row([input_author, input_type], spacing=15),
            ft.Row([input_year, input_publisher], spacing=15),
            ft.Row([input_isbn]),
        ],
        width=550,
        tight=True,
        spacing=10
    )

    def close_modal(e):
        modal_insert_book.open = False
        page.update()

    def save_book(e):
        if not input_title.value or not input_author.value:
            snack_bar = ft.SnackBar(
                content=ft.Text(
                    "Os campos Título e Autor são obrigatórios!",
                    color=COLORS["surface"],
                ),
                bgcolor=COLORS["text"],
            )

            page.overlay.append(snack_bar)
            snack_bar.open = True
            page.update()
            return

        # Limpar os campos após salvar
        input_title.value = ""
        input_author.value = ""
        input_year.value = ""
        input_publisher.value = ""
        input_isbn.value = ""
        input_type.value = None

        modal_insert_book.open = False

        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(
                    "Obra adicionada ao acervo com sucesso!",
                    color=COLORS["surface"],
                ),
                bgcolor=COLORS["gold"],
            )
        )

    modal_insert_book = ft.AlertDialog(
        modal=False,
        bgcolor=COLORS["surface"],
        shape=ft.RoundedRectangleBorder(radius=8),
        content_padding=24,
        content=form_content,
        actions=[
            ft.TextButton(
                "Cancelar",
                on_click=close_modal,
                style=ft.ButtonStyle(color=COLORS["muted"])
            ),
            ft.ElevatedButton(
                "Salvar Acervo",
                on_click=save_book,
                bgcolor=COLORS["gold"],
                color=COLORS["surface"],
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4))
            ),
        ],
        actions_padding=ft.Padding.only(right=24, bottom=24, top=10),
    )

    return modal_insert_book
