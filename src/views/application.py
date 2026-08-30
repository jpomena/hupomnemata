"""Composer da tela principal da aplicacao."""

import flet as ft
from src.repositories import AuthorSearchResult

from collections.abc import Awaitable, Callable
from src.views.dashboard import DashboardComposer
from src.views.works import WorksComposer
from src.views.sidebar import SidebarComposer
from src.utils.types import ViewConfig
from src.utils.types import ViewReference
from src.views.work_insert_modal import WorkInsertModalComposer
from src.views.general_popups import MultipleAuthors
from src.views.work_details_popup import WorkDetailsPopup


class ApplicationComposer:
    """Compoe a estrutura visual principal da aplicacao."""

    def __init__(
        self,
        page: ft.Page,
        scale: float,
        config: ViewConfig,
        on_navigate: Callable[[str], None],
        on_work_click: Callable,
        on_copy_reference: Callable[[ViewReference], Awaitable[None]],
        on_delete_work: Callable,
        on_create_parent_work: Callable[
            [Callable[[int, str], None]], None
        ],
    ):
        self.page = page
        self.scale = scale
        self.config = config
        self.on_navigate = on_navigate
        self.on_work_click = on_work_click
        self.on_copy_reference = on_copy_reference
        self.on_delete_work = on_delete_work
        self.on_create_parent_work = on_create_parent_work

    def _window_control_button(
        self,
        icon: ft.IconData | ft.Control | None,
        on_click: Callable[..., object] | None,
        color: str,
    ) -> ft.IconButton:
        return ft.IconButton(
            icon=icon,
            icon_color=color,
            icon_size=16,
            on_click=on_click,
            style=ft.ButtonStyle(
                shape=ft.CircleBorder(),
                padding=4,
            ),
        )

    def _compose_custom_title_bar(self) -> ft.WindowDragArea:
        def minimize_window(_):
            self.page.window.minimized = True
            self.page.update()

        def toggle_maximize_window(_):
            self.page.window.maximized = not self.page.window.maximized
            self.page.update()

        async def close_window(_):
            await self.page.window.close()

        title_controls: list[ft.Control] = [
            ft.Text(
                value=self.config.texts["app"]["name"],
                size=self.config.font_sizes["montserrat_medium"],
                weight=self.config.font_weights["montserrat_semibold"],
                color=self.config.colors["gold"],
                font_family=self.config.font_families["montserrat"],
            ),
        ]
        toolbar_controls: list[ft.Control] = [
            self._window_control_button(
                icon=ft.Icons.REMOVE,
                on_click=minimize_window,
                color=self.config.colors["text"],
            ),
            self._window_control_button(
                icon=ft.Icons.CROP_SQUARE,
                on_click=toggle_maximize_window,
                color=self.config.colors["text"],
            ),
            self._window_control_button(
                icon=ft.Icons.CLOSE,
                on_click=close_window,
                color=self.config.colors["text"],
            ),
        ]

        row_content = ft.Row(
            controls=title_controls + [
                ft.Row(
                    controls=toolbar_controls,
                    spacing=4,
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.WindowDragArea(
            content=ft.Container(
                content=row_content,
                bgcolor=self.config.colors["surface"],
                padding=ft.Padding.only(
                    left=16, right=12, top=8, bottom=8
                ),
                border=ft.Border.only(
                    bottom=ft.BorderSide(1, self.config.colors["border"])
                ),
                height=52,
            )
        )

    def compose_main(self) -> ft.Column:
        """Monta a barra lateral e o dashboard em uma linha principal."""
        self.content = (
            ft.AnimatedSwitcher(
                transition=ft.AnimatedSwitcherTransition.FADE,
                duration=500,
                switch_in_curve=ft.AnimationCurve.EASE_IN,
                switch_out_curve=ft.AnimationCurve.EASE_OUT,
                expand=True,
                content=ft.Container(
                    content=DashboardComposer(
                        scale=self.scale,
                        config=self.config,
                        on_navigate=self.on_navigate
                    ).compose(),
                    expand=True,
                )
            )
        )

        return ft.Column(
            controls=[
                self._compose_custom_title_bar(),
                ft.Row(
                    controls=[
                        SidebarComposer(
                            scale=self.scale,
                            config=self.config,
                            on_navigate=self.on_navigate
                        ).compose(),
                        self.content,
                    ],
                    expand=True,
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            ],
            expand=True,
            spacing=0,
        )

    def show_view(self, destination: str, works=None):
        views = {
            "dashboard": self._compose_dashboard,
            "Acervo": lambda: self._compose_works(works),
            "Fragmentos": self._compose_dashboard
        }
        view_factory = views.get(destination)
        if not view_factory:
            return

        self.content.content = view_factory()
        self.content.update()

    def _compose_dashboard(self) -> ft.Control:
        return DashboardComposer(
            scale=self.scale,
            config=self.config,
            on_navigate=self.on_navigate,
        ).compose()

    def _compose_works(self, works) -> ft.Control:
        return WorksComposer(
            scale=self.scale,
            config=self.config,
            works=works or [],
            on_navigate=self.on_navigate,
            on_work_click=self.on_work_click,
            on_copy_reference=self.on_copy_reference,
            on_delete_work=self.on_delete_work,
        ).compose()

    @staticmethod
    def compose_work_details_popup(
        resource, config: ViewConfig, on_close: Callable[[], None]
    ) -> ft.AlertDialog:
        return WorkDetailsPopup(resource, config, on_close).compose()

    @staticmethod
    def compose_work_insert_modal(
        page: ft.Page,
        config: ViewConfig,
        on_save: Callable[[dict[str, object]], bool],
        search_authors: (
            Callable[[str], list[AuthorSearchResult]] | None
        ) = None,
        search_works: Callable[[str], list[tuple[int, str]]] | None = None,
        on_create_parent_work: Callable[
            [Callable[[int, str], None], str | None], None
        ] | None = None,
        initial_work_type: str | None = None,
        parent_mode: bool = False,
    ) -> ft.AlertDialog:
        return WorkInsertModalComposer(
            page=page,
            config=config,
            on_save=on_save,
            search_authors=search_authors,
            search_works=search_works,
            on_create_parent_work=on_create_parent_work,
            initial_work_type=initial_work_type,
            parent_mode=parent_mode,
        ).compose()

    @staticmethod
    def compose_multiple_authors_modal(
        authors,
        on_select: Callable[[int], None],
        on_create_new: Callable[[], None],
        on_cancel: Callable[[], None],
        config: ViewConfig
    ) -> ft.AlertDialog:
        return MultipleAuthors().compose(
            authors=authors,
            on_select=on_select,
            on_create_new=on_create_new,
            on_cancel=on_cancel,
            config=config
        )
