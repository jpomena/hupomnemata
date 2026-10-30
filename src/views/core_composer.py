"""Composer da tela principal da aplicacao."""

import flet as ft
from src.domains import BibliographicResource
from src.contracts import (
    AuthorReference,
    AuthorSearchResult,
    CompilationPayload,
    CompilationRecord,
    FragmentRecord,
)

from collections.abc import Awaitable, Callable
from src.views.dashboard import DashboardComposer
from src.views.works import WorksComposer
from src.views.fragments import FragmentsComposer
from src.views.compilations import CompilationsComposer
from src.views.sidebar import SidebarComposer
from src.views.settings import SettingsComposer
from src.views.knowledge import KnowledgeComposer
from src.views.nous_composer import NousComposer
from src.services.nous_service import NousAIService
from src.utils.types import ViewConfig
from src.utils.types import ViewReference
from src.views.work_insert_modal import WorkInsertModalComposer
from src.views.general_popups import MultipleAuthorsPopup
from src.views.work_details_popup import WorkDetailsPopup


class CoreComposer:
    """Compoe a estrutura visual principal da aplicacao."""

    def __init__(
        self,
        page: ft.Page,
        scale: float,
        config: ViewConfig,
        on_navigate: Callable[[str], None],
        on_work_click: Callable,
        on_edit_work: Callable,
        on_format_reference: Callable[
            [BibliographicResource], ViewReference | None
        ],
        on_copy_reference: Callable[[ViewReference], Awaitable[None]],
        on_delete_work: Callable,
        on_create_parent_work: Callable[
            [Callable[[int, str], None]], None
        ],
        on_fragment_save: Callable[
            [int | None, dict[str, object]], bool
        ],
        on_fragment_delete: Callable[[int], None],
        search_fragment_works: Callable[[str], list[tuple[int, str]]],
        search_compilation_works: Callable[
            [str], list[tuple[int, str]]
        ],
        refresh_compilations: Callable[[], list[CompilationRecord]],
        on_compilation_create: Callable[[CompilationPayload], int | None],
        on_compilation_update: Callable[
            [int, CompilationPayload], bool
        ],
        on_compilation_delete: Callable[[int], bool],
        on_compilation_add_work: Callable[[int, int], bool],
        on_compilation_remove_work: Callable[[int, int], bool],
        on_compilation_reorder_works: Callable[[int, list[int]], bool],
        on_compilation_fragment_membership: Callable[
            [int, int, bool], bool
        ],
        on_compilation_fragment_note: Callable[
            [int, int, str | None], bool
        ],
        on_compilation_section_create: Callable[
            [int, str, str | None], int | None
        ],
        on_compilation_section_update: Callable[
            [int, int, str, str | None], bool
        ],
        on_compilation_section_delete: Callable[[int, int], bool],
        on_compilation_section_reorder: Callable[[int, list[int]], bool],
        on_compilation_fragment_assign_section: Callable[
            [int, int, int | None], bool
        ],
        on_compilation_section_reorder_fragments: Callable[
            [int, int, list[int]], bool
        ],
        on_compilation_copy_caderno: Callable[[str], Awaitable[None]],
        on_compilation_create_work: Callable[[int], None],
        on_compilation_edit_work: Callable[[int, int], None],
        on_compilation_create_fragment: Callable[[int, int], None],
        on_compilation_edit_fragment: Callable[
            [int, FragmentRecord], None
        ],
        get_knowledge_graph: Callable[..., dict] | None = None,
        sync_knowledge_mesh: Callable[[], dict] | None = None,
        get_knowledge_resonances: Callable[..., list] | None = None,
        get_knowledge_work_fragments: Callable[..., list] | None = None,
        on_create_knowledge_link: Callable[..., bool] | None = None,
        on_add_knowledge_to_compilation: Callable[[int, int], bool] | None = None,
        current_theme_mode: str = "light",
        auto_scale: bool = True,
        manual_scale: float = 1.0,
        on_change_theme: Callable[[str], None] | None = None,
        on_toggle_auto_scale: Callable[[bool], None] | None = None,
        on_change_scale: Callable[[float], None] | None = None,
        on_reset_settings: Callable[[], None] | None = None,
        on_toggle_maximize: Callable[[], None] | None = None,
        nous_service: NousAIService | None = None,
    ):
        self.page = page
        self.scale = scale
        self.config = config
        self.on_navigate = on_navigate
        self.on_work_click = on_work_click
        self.on_edit_work = on_edit_work
        self.on_format_reference = on_format_reference
        self.on_copy_reference = on_copy_reference
        self.on_delete_work = on_delete_work
        self.on_create_parent_work = on_create_parent_work
        self.on_fragment_save = on_fragment_save
        self.on_fragment_delete = on_fragment_delete
        self.search_fragment_works = search_fragment_works
        self.search_compilation_works = search_compilation_works
        self.refresh_compilations = refresh_compilations
        self.on_compilation_create = on_compilation_create
        self.on_compilation_update = on_compilation_update
        self.on_compilation_delete = on_compilation_delete
        self.on_compilation_add_work = on_compilation_add_work
        self.on_compilation_remove_work = on_compilation_remove_work
        self.on_compilation_reorder_works = on_compilation_reorder_works
        self.on_compilation_fragment_membership = (
            on_compilation_fragment_membership
        )
        self.on_compilation_fragment_note = on_compilation_fragment_note
        self.on_compilation_section_create = on_compilation_section_create
        self.on_compilation_section_update = on_compilation_section_update
        self.on_compilation_section_delete = on_compilation_section_delete
        self.on_compilation_section_reorder = on_compilation_section_reorder
        self.on_compilation_fragment_assign_section = (
            on_compilation_fragment_assign_section
        )
        self.on_compilation_section_reorder_fragments = (
            on_compilation_section_reorder_fragments
        )
        self.on_compilation_copy_caderno = on_compilation_copy_caderno
        self.on_compilation_create_work = on_compilation_create_work
        self.on_compilation_edit_work = on_compilation_edit_work
        self.on_compilation_create_fragment = (
            on_compilation_create_fragment
        )
        self.on_compilation_edit_fragment = on_compilation_edit_fragment
        self.get_knowledge_graph = get_knowledge_graph
        self.sync_knowledge_mesh = sync_knowledge_mesh
        self.get_knowledge_resonances = get_knowledge_resonances
        self.get_knowledge_work_fragments = get_knowledge_work_fragments
        self.on_create_knowledge_link = on_create_knowledge_link
        self.on_add_knowledge_to_compilation = on_add_knowledge_to_compilation
        self.knowledge_composer: KnowledgeComposer | None = None
        self.current_theme_mode = current_theme_mode
        self.auto_scale = auto_scale
        self.manual_scale = manual_scale
        self.on_change_theme = on_change_theme
        self.on_toggle_auto_scale = on_toggle_auto_scale
        self.on_change_scale = on_change_scale
        self.on_reset_settings = on_reset_settings
        self.on_toggle_maximize = on_toggle_maximize
        self.compilations_composer: CompilationsComposer | None = None
        self.nous_service = nous_service
        self.nous_composer: NousComposer | None = None

    def _window_control_button(
        self,
        icon: ft.IconData | ft.Control | None,
        on_click: Callable[..., object] | None,
        color: str,
        tooltip: str | None = None,
    ) -> ft.IconButton:
        return ft.IconButton(
            icon=icon,
            icon_color=color,
            icon_size=16,
            tooltip=tooltip,
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
            if self.on_toggle_maximize is not None:
                self.on_toggle_maximize()
            else:
                self.page.window.maximized = not self.page.window.maximized
                self.page.update()

        async def close_window(_):
            await self.page.window.close()

        is_maximized = bool(
            getattr(getattr(self.page, "window", None), "maximized", False)
        )
        maximize_icon = (
            ft.Icons.FILTER_NONE
            if is_maximized
            else ft.Icons.CROP_SQUARE
        )
        maximize_tooltip = "Restaurar" if is_maximized else "Maximizar"

        title_controls: list[ft.Control] = [
            ft.Image(
                src="assets/images/icon.ico",
                width=56,
                height=56
            ),
        ]
        self.maximize_button = self._window_control_button(
            icon=maximize_icon,
            on_click=toggle_maximize_window,
            color=self.config.colors["text"],
            tooltip=maximize_tooltip,
        )
        toolbar_controls: list[ft.Control] = [
            self._window_control_button(
                icon=ft.Icons.REMOVE,
                on_click=minimize_window,
                color=self.config.colors["text"],
                tooltip="Minimizar",
            ),
            self.maximize_button,
            self._window_control_button(
                icon=ft.Icons.CLOSE,
                on_click=close_window,
                color=self.config.colors["text"],
                tooltip="Fechar",
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

    def update_window_state(self, is_maximized: bool) -> None:
        """Atualiza dinamicamente o ícone e tooltip do botão de maximizar/restaurar sem recriar a UI."""
        if hasattr(self, "maximize_button") and self.maximize_button is not None:
            self.maximize_button.icon = (
                ft.Icons.FILTER_NONE if is_maximized else ft.Icons.CROP_SQUARE
            )
            self.maximize_button.tooltip = "Restaurar" if is_maximized else "Maximizar"
            try:
                self.maximize_button.update()
            except Exception:
                pass

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
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def show_view(
        self,
        destination: str,
        works: list[BibliographicResource] | None = None,
        fragments: list[FragmentRecord] | None = None,
        compilations: list[CompilationRecord] | None = None,
    ) -> None:
        views = {
            "dashboard": self._compose_dashboard,
            "Acervo": lambda: self._compose_works(works),
            "Fragmentos": lambda: self._compose_fragments(fragments),
            "Compilações": lambda: self._compose_compilations(compilations),
            "Estruturas de Saber": self._compose_knowledge,
            "Nous": self._compose_nous,
            "Configurações": self._compose_settings,
        }
        view_factory = views.get(destination)
        if not view_factory:
            if destination not in self.config.core_menus:
                return
            self.content.content = self._compose_placeholder_dashboard(
                destination
            )
        else:
            self.content.content = view_factory()
        try:
            self.content.update()
        except RuntimeError:
            pass

    def _compose_dashboard(self) -> ft.Control:
        return DashboardComposer(
            scale=self.scale,
            config=self.config,
            on_navigate=self.on_navigate,
        ).compose()

    def _compose_placeholder_dashboard(self, section: str) -> ft.Control:
        return DashboardComposer(
            scale=self.scale,
            config=self.config,
            on_navigate=self.on_navigate,
        ).compose_placeholder(section)

    def _compose_settings(self) -> ft.Control:
        return SettingsComposer(
            scale=self.scale,
            config=self.config,
            current_theme_mode=self.current_theme_mode,
            auto_scale=self.auto_scale,
            manual_scale=self.manual_scale,
            effective_scale=self.scale,
            on_navigate=self.on_navigate,
            on_change_theme=self.on_change_theme or (lambda _: None),
            on_toggle_auto_scale=self.on_toggle_auto_scale or (lambda _: None),
            on_change_scale=self.on_change_scale or (lambda _: None),
            on_reset_settings=self.on_reset_settings or (lambda: None),
        ).compose()

    def _compose_nous(self) -> ft.Control:
        self.nous_composer = NousComposer(
            page=getattr(self, "page", None),
            config=self.config,
            scale=self.scale,
            on_navigate=self.on_navigate,
            nous_service=getattr(self, "nous_service", None),
            current_theme_mode=getattr(self, "current_theme_mode", "light"),
        )
        return self.nous_composer.compose()

    def _compose_knowledge(self) -> ft.Control:
        self.knowledge_composer = KnowledgeComposer(
            page=getattr(self, "page", None),
            config=self.config,
            scale=self.scale,
            on_navigate=self.on_navigate,
            get_graph_data=getattr(self, "get_knowledge_graph", None) or (lambda _: {"nodes": [], "links": [], "clusters": []}),
            sync_mesh=getattr(self, "sync_knowledge_mesh", None) or (lambda: {"vectorized": 0, "clusters": 0}),
            get_resonances=getattr(self, "get_knowledge_resonances", None) or (lambda *_: []),
            get_work_fragments=getattr(self, "get_knowledge_work_fragments", None) or (lambda _: []),
            on_add_to_compilation=getattr(self, "on_add_knowledge_to_compilation", None),
            list_compilations=getattr(self, "refresh_compilations", None),
            on_create_link=getattr(self, "on_create_knowledge_link", None),
            current_theme_mode=getattr(self, "current_theme_mode", "light"),
        )
        return self.knowledge_composer.compose()

    def _compose_works(
        self,
        works: list[BibliographicResource] | None,
    ) -> ft.Control:
        return WorksComposer(
            scale=self.scale,
            config=self.config,
            works=works or [],
            on_navigate=self.on_navigate,
            on_work_click=self.on_work_click,
            on_edit_work=self.on_edit_work,
            format_reference=self.on_format_reference,
            on_copy_reference=self.on_copy_reference,
            on_delete_work=self.on_delete_work,
        ).compose()

    def _compose_fragments(
        self,
        fragments: list[FragmentRecord] | None,
    ) -> ft.Control:
        return FragmentsComposer(
            page=self.page,
            config=self.config,
            fragments=fragments or [],
            search_works=self.search_fragment_works,
            on_save=self.on_fragment_save,
            on_delete=self.on_fragment_delete,
            on_copy_reference=self.on_copy_reference,
        ).compose()

    def _compose_compilations(
        self,
        compilations: list[CompilationRecord] | None,
    ) -> ft.Control:
        self.compilations_composer = CompilationsComposer(
            page=self.page,
            config=self.config,
            compilations=compilations or [],
            search_works=self.search_compilation_works,
            refresh_compilations=self.refresh_compilations,
            on_create=self.on_compilation_create,
            on_update=self.on_compilation_update,
            on_delete=self.on_compilation_delete,
            on_add_work=self.on_compilation_add_work,
            on_remove_work=self.on_compilation_remove_work,
            on_reorder_works=self.on_compilation_reorder_works,
            on_fragment_membership=(
                self.on_compilation_fragment_membership
            ),
            on_fragment_note=self.on_compilation_fragment_note,
            on_create_section=self.on_compilation_section_create,
            on_update_section=self.on_compilation_section_update,
            on_delete_section=self.on_compilation_section_delete,
            on_reorder_sections=self.on_compilation_section_reorder,
            on_assign_fragment_to_section=(
                self.on_compilation_fragment_assign_section
            ),
            on_reorder_section_fragments=(
                self.on_compilation_section_reorder_fragments
            ),
            on_copy_caderno=self.on_compilation_copy_caderno,
            on_create_work=self.on_compilation_create_work,
            on_edit_work=self.on_compilation_edit_work,
            on_create_fragment=self.on_compilation_create_fragment,
            on_edit_fragment=self.on_compilation_edit_fragment,
        )
        return self.compilations_composer.compose()

    def refresh_compilation_hub(self, compilation_id: int) -> None:
        if self.compilations_composer is not None:
            self.compilations_composer.refresh_compilation_hub(
                compilation_id
            )

    @staticmethod
    def compose_work_details_popup(
        resource,
        config: ViewConfig,
        on_close: Callable[[], None],
        page: ft.Page | None = None,
        nous_service: object | None = None,
    ) -> ft.AlertDialog:
        return WorkDetailsPopup(
            resource=resource,
            config=config,
            on_close=on_close,
            page=page,
            nous_service=nous_service,
        ).compose()

    @staticmethod
    def compose_work_insert_modal(
        page: ft.Page,
        config: ViewConfig,
        on_save: Callable[[dict[str, object]], bool],
        search_authors: (
            Callable[[str], list[AuthorSearchResult]] | None
        ) = None,
        search_works: (
            Callable[[str, str | None], list[tuple[int, str]]] | None
        ) = None,
        on_create_parent_work: Callable[
            [Callable[[int, str], None], str | None], None
        ] | None = None,
        initial_work_type: str | None = None,
        parent_mode: bool = False,
        edit_mode: bool = False,
        initial_values: dict[str, object] | None = None,
        initial_author_references: list[AuthorReference] | None = None,
        initial_parent_work_id: int | None = None,
        initial_parent_work_title: str = "",
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
            edit_mode=edit_mode,
            initial_values=initial_values,
            initial_author_references=initial_author_references,
            initial_parent_work_id=initial_parent_work_id,
            initial_parent_work_title=initial_parent_work_title,
        ).compose()

    @staticmethod
    def compose_multiple_authors_modal(
        authors,
        on_select: Callable[[int], None],
        on_create_new: Callable[[], None],
        on_cancel: Callable[[], None],
        config: ViewConfig
    ) -> ft.AlertDialog:
        return MultipleAuthorsPopup().compose(
            authors=authors,
            on_select=on_select,
            on_create_new=on_create_new,
            on_cancel=on_cancel,
            config=config
        )
