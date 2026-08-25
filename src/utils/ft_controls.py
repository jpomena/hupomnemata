import flet as ft
from src.configs.settings import COLORS, FONTS


PHI = (1 + 5**0.5) / 2


class ControlsUtils:

    @staticmethod
    def create_sidebar_menu(
        label_ref: str,
        icon_data: ft.IconData,
        scale: float
    ) -> ft.Container:

        icon = ft.Icon(
            icon_data,
            size=16 * scale,
            color=COLORS["gold"],
        )

        label = ft.Text(
            label_ref,
            size=13 * scale,
            color=COLORS["text"],
            font_family=FONTS["montserrat"],
        )

        row_content = ft.Row(
            controls=[
                ft.Row(
                    controls=[icon, label],
                    spacing=10,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        btn_container = ft.Container(
            content=row_content,
            padding=12,
            bgcolor=COLORS["surface"],
            animate=ft.Animation(
                150,
                ft.AnimationCurve.EASE_OUT
            ),
            border_radius=ft.BorderRadius(
                top_left=0,
                bottom_left=0,
                top_right=4,
                bottom_right=4,
            ),
        )

        def handle_hover(e: ft.Event[ft.Container]):
            if e.data:
                btn_container.bgcolor = COLORS["card_hover"]
                btn_container.border = ft.Border(
                    left=ft.BorderSide(4, COLORS["text"]),
                    top=ft.BorderSide(1, COLORS["text"]),
                    right=ft.BorderSide(1, COLORS["text"]),
                    bottom=ft.BorderSide(1, COLORS["text"])
                )
                icon.color = COLORS["text"]
            else:
                btn_container.bgcolor = COLORS["surface"]
                btn_container.border = None
                icon.color = COLORS["gold"]

            btn_container.update()

        btn_container.on_hover = handle_hover

        return btn_container

    @staticmethod
    def create_main_view_card(
        icon_data: ft.IconData,
        label_str: str,
        description_str: str,
        scale: float
    ) -> ft.Container:

        icon = ft.Icon(
            icon_data,
            size=64 * scale,
            color=COLORS["gold"],
        )

        label = ft.Text(
            label_str,
            size=20 * scale,
            text_align=ft.TextAlign.CENTER,
            font_family=FONTS["cormorant"],
            weight=ft.FontWeight.W_800,
            color=COLORS["text"],
            style=ft.TextStyle(letter_spacing=2),
        )

        description = ft.Text(
            description_str,
            size=11 * scale,
            overflow=ft.TextOverflow.ELLIPSIS,
            font_family=FONTS["montserrat"],
            max_lines=2,
            color=COLORS["muted"],
            weight=ft.FontWeight.W_500,
        )

        card_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[icon],
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True,
                ),
                ft.Column(
                    controls=[label, description],
                    spacing=4,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=12,
            expand=True,
        )

        btn_container = ft.Container(
            content=card_content,
            padding=12,
            bgcolor=COLORS["surface"],
            height=175 * PHI,
            border=ft.Border.all(
                1,
                COLORS["border"],
            ),
            border_radius=ft.BorderRadius.all(6),
            animate=ft.Animation(
                150,
                ft.AnimationCurve.EASE_OUT,
            ),
        )

        def handle_hover(e: ft.Event[ft.Container]):
            if e.data:
                btn_container.bgcolor = COLORS["card_hover"]
                btn_container.border = ft.Border(
                    left=ft.BorderSide(1, COLORS["text"]),
                    top=ft.BorderSide(1, COLORS["text"]),
                    right=ft.BorderSide(1, COLORS["text"]),
                    bottom=ft.BorderSide(4, COLORS["text"])
                )
                icon.color = COLORS["text"]
            else:
                btn_container.bgcolor = COLORS["surface"]
                btn_container.border = ft.Border.all(
                    1,
                    COLORS["border"],
                )
                icon.color = COLORS["gold"]

            btn_container.update()

        btn_container.on_hover = handle_hover

        return btn_container
