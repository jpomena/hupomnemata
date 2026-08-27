"""Composer da tela principal da aplicacao."""

import flet as ft

from collections.abc import Callable
from src.views.dashboard import DashboardComposer
from src.views.works import WorksComposer
from src.views.sidebar import SidebarComposer
from src.utils.types import ViewConfig
from src.views.work_insert_modal import WorkInsertModalComposer
from src.views.general_popups import MultipleAuthors
from src.views.work_details_popup import WorkDetailsPopup


class ApplicationComposer:
    """Compoe a estrutura visual principal da aplicacao."""

    def __init__(
        self,
        scale: float,
        config: ViewConfig,
        on_navigate: Callable[[str], None],
        on_work_click: Callable,
    ):
        self.scale = scale
        self.config = config
        self.on_navigate = on_navigate
        self.on_work_click = on_work_click

    def compose_main(self) -> ft.Row:
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

        return ft.Row(
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
        )

    def show_view(self, destination: str, works=None):
        views = {
            "dashboard": self._compose_dashboard,
            "Obras & Livros": lambda: self._compose_works(works),
            "Cadernos & Excertos": self._compose_dashboard
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
        search_authors: Callable[[str], list[str]] | None = None,
    ) -> ft.AlertDialog:
        return WorkInsertModalComposer(
            page=page,
            config=config,
            on_save=on_save,
            search_authors=search_authors,
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
