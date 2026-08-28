"""Fabricas de controles Flet compartilhados pela interface."""

import flet as ft
from collections.abc import Callable

from .types import ViewConfig


class ControlsUtils:
    """Cria controles reutilizaveis com a configuracao recebida."""

    @staticmethod
    def create_sidebar_menu(
        label_ref: str,
        icon_data: ft.IconData,
        scale: float,
        config: ViewConfig,
        on_navigate: Callable[[str], None]
    ) -> ft.Container:
        """Cria um item de menu com estado visual de hover."""
        icon = ft.Icon(
            icon_data,
            size=config.font_sizes["montserrat_medium"] * scale,
            color=config.colors["gold"],
        )
        label = ft.Text(
            value=label_ref,
            size=config.font_sizes["cormorant_medium"] * scale,
            color=config.colors["text"],
            font_family=config.font_families["cormorant"],
            weight=config.font_weights["cormorant_semibold"],
        )
        row_content = ft.Row(
            controls=[
                ft.Row(
                    controls=[icon, label],
                    spacing=config.ui["control_gap"],
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        btn_container = ft.Container(
            content=row_content,
            padding=config.ui["card_padding"],
            bgcolor=config.colors["surface"],
            on_click=lambda e: on_navigate(f"{label_ref}"),
            animate=ft.Animation(
                int(config.ui["animation_ms"]),
                ft.AnimationCurve.EASE_OUT,
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
                btn_container.bgcolor = config.colors["card_hover"]
                btn_container.border = ft.Border(
                    left=ft.BorderSide(4, config.colors["text"]),
                    top=ft.BorderSide(1, config.colors["text"]),
                    right=ft.BorderSide(1, config.colors["text"]),
                    bottom=ft.BorderSide(1, config.colors["text"]),
                )
                icon.color = config.colors["text"]
            else:
                btn_container.bgcolor = config.colors["surface"]
                btn_container.border = None
                icon.color = config.colors["gold"]
            btn_container.update()

        btn_container.on_hover = handle_hover
        return btn_container

    @staticmethod
    def create_main_view_card(
        icon_data: ft.IconData,
        label_str: str,
        description_str: str,
        scale: float,
        config: ViewConfig,
        on_click: Callable | None = None,
    ) -> ft.Container:
        """Cria um cartao de atalho da visao principal."""
        icon = ft.Icon(
            icon_data,
            size=config.icon_sizes["icon_large"] * scale,
            color=config.colors["gold"],
        )
        label = ft.Text(
            value=label_str,
            size=config.font_sizes["cormorant_large"] * scale,
            text_align=ft.TextAlign.CENTER,
            font_family=config.font_families["cormorant"],
            weight=config.font_weights["cormorant_semibold"],
            color=config.colors["text"],
            style=ft.TextStyle(letter_spacing=2),
        )
        description = ft.Text(
            value=description_str,
            size=config.font_sizes["montserrat_micro"] * scale,
            overflow=ft.TextOverflow.ELLIPSIS,
            font_family=config.font_families["montserrat"],
            max_lines=2,
            color=config.colors["muted"],
            weight=config.font_weights["montserrat_semibold"],
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
                    spacing=config.ui["modal_gap"] - 6,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=config.ui["modal_gap"],
            expand=True,
        )
        btn_container = ft.Container(
            content=card_content,
            padding=config.ui["card_padding"],
            bgcolor=config.colors["surface"],
            height=config.ui["card_height"],
            border=ft.Border.all(1, config.colors["border"]),
            border_radius=ft.BorderRadius.all(config.ui["card_radius"]),
            animate=ft.Animation(
                int(config.ui["animation_ms"]),
                ft.AnimationCurve.EASE_OUT,
            ),
        )

        def handle_hover(e: ft.Event[ft.Container]):
            if e.data:
                btn_container.bgcolor = config.colors["card_hover"]
                btn_container.border = ft.Border(
                    left=ft.BorderSide(1, config.colors["text"]),
                    top=ft.BorderSide(1, config.colors["text"]),
                    right=ft.BorderSide(1, config.colors["text"]),
                    bottom=ft.BorderSide(8, config.colors["text"]),
                )
                icon.color = config.colors["text"]
            else:
                btn_container.bgcolor = config.colors["surface"]
                btn_container.border = ft.Border.all(
                    1,
                    config.colors["border"],
                )
                icon.color = config.colors["gold"]
            btn_container.update()

        btn_container.on_hover = handle_hover
        btn_container.on_click = on_click
        return btn_container
