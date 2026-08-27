"""Composer da tela principal da aplicacao."""

import flet as ft

from collections.abc import Callable
from src.views.dashboard import DashboardComposer
from src.views.sidebar import SidebarComposer
from src.views.view_config import ViewConfig
from src.views.work_insert_modal import WorkInsertModalComposer
from src.views.general_popups import MultipleAuthors


class ApplicationComposer:
    """Compoe a estrutura visual principal da aplicacao."""

    def __init__(
        self,
        scale: float,
        config: ViewConfig,
        on_insert_work: Callable[[], None],
    ):
        self.scale = scale
        self.config = config
        self.on_insert_work = on_insert_work

    def compose_main(self) -> ft.Row:
        """Monta a barra lateral e o dashboard em uma linha principal."""
        return ft.Row(
            controls=[
                SidebarComposer(self.scale, self.config).compose(),
                DashboardComposer(
                    self.scale, self.config, self.on_insert_work
                ).compose(),
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    @staticmethod
    def compose_work_insert_modal(
        page: ft.Page,
        config: ViewConfig,
        on_save: Callable[[dict[str, object]], bool]
    ) -> ft.AlertDialog:
        return WorkInsertModalComposer(
            page=page,
            config=config,
            on_save=on_save,
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
