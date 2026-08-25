import flet as ft


class FtUtils:

    @staticmethod
    def add_menu_button(
        text: str,
        font: str,
        on_click=None
    ) -> ft.Container:

        def handle_hover(e):
            e.control.bgcolor = '#C5A059' if e.data == 'true' else None
            e.control.update()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        text,
                        size=14,
                        text_align=ft.TextAlign.LEFT,
                        color='#C1C1C2',
                        font_family=font,
                    )
                ],
                height=50,
            ),
            border=ft.Border(bottom=ft.BorderSide(1, '#232328')),
            padding=ft.Padding.only(left=30),
            height=50,
            on_click=on_click,
            ink=True,
            on_hover=handle_hover
        )
