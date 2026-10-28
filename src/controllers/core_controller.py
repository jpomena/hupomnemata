"""Controlador principal da aplicação."""

import flet as ft
from dataclasses import replace

from src.configs.settings import (
    COLORS_LIGHT,
    COLORS_DARK,
    CORE_MENUS,
    FONT_FAMILIES,
    FONT_SIZES,
    FONT_WEIGHTS,
    ICON_SIZES,
    MAIN_VIEW_CARDS,
    PAGE_FONTS,
    TEXTS,
    UI,
)
from src.db.db import init_db
from src.services import (
    CompilationService,
    FragmentService,
    WorkService,
    KnowledgeService,
    NousAIService,
    SettingsService,
    resolve_effective_scale,
    resolve_effective_theme,
)
from src.utils.normalizers import CoreNormalizer
from src.views.core_composer import CoreComposer
from src.views.page_config import PageConfigurator
from src.utils.types import ViewConfig
from src.services.work_form_service import WorkFormService
from src.controllers.work_submission_controller import (
    WorkSubmissionController,
)
from src.controllers.handlers import (
    WindowControllerMixin,
    WorkControllerMixin,
    FragmentControllerMixin,
    CompilationControllerMixin,
    KnowledgeControllerMixin,
    NousControllerMixin,
)


class CoreController(
    WindowControllerMixin,
    WorkControllerMixin,
    FragmentControllerMixin,
    CompilationControllerMixin,
    KnowledgeControllerMixin,
    NousControllerMixin,
):
    """Orquestra o ciclo de vida, navegação e integração de fluxos da aplicação."""

    def __init__(
        self,
        page: ft.Page,
        dark_theme: bool | None = None,
        settings_service: SettingsService | None = None,
    ):
        self.page = page
        self.work_insert_modal: ft.AlertDialog | None = None
        self.normalizer = CoreNormalizer()
        self.service = WorkService(self.normalizer)
        self.fragment_service = FragmentService()
        self.compilation_service = CompilationService()
        self.knowledge_service = KnowledgeService()
        self.compilation_fragment_composer = None
        self.form_service = WorkFormService(self.normalizer)
        self.settings_service = (
            settings_service
            if settings_service is not None
            else SettingsService()
        )
        self.settings = self.settings_service.load_settings()
        self.nous_service = NousAIService(
            settings_service=self.settings_service,
            knowledge_service=self.knowledge_service,
        )
        if dark_theme is not None and not self.settings_service.storage_path.exists():
            self.settings.theme_mode = "dark" if dark_theme else "light"

        effective_theme = resolve_effective_theme(
            self.settings.theme_mode, self.page
        )
        self.view_config = ViewConfig(
            colors=COLORS_DARK if effective_theme == "dark" else COLORS_LIGHT,
            page_fonts=PAGE_FONTS,
            font_families=FONT_FAMILIES,
            font_sizes=FONT_SIZES,
            icon_sizes=ICON_SIZES,
            font_weights=FONT_WEIGHTS,
            ui=UI,
            texts=TEXTS,
            core_menus=CORE_MENUS,
            main_view_cards=MAIN_VIEW_CARDS,
        )
        self.scale = resolve_effective_scale(self.settings, self.page)
        self.current_destination = "dashboard"
        self._last_maximized_state = bool(
            getattr(getattr(self.page, "window", None), "maximized", False)
        )
        self.page_configurator = PageConfigurator(
            config=self.view_config,
        )
        self.submission_controller = WorkSubmissionController(
            page=self.page,
            config=self.view_config,
            service=self.service,
            form_service=self.form_service,
            show_message=self.show_message,
            close_insert_work=self.close_insert_work,
        )

    def start(self) -> None:
        self.initialize_database()
        self.configure_page()
        self.build_application()

    def initialize_database(self) -> None:
        init_db()

    def configure_page(self) -> None:
        self.page_configurator.configure_page(self.page)
        effective_theme = resolve_effective_theme(
            self.settings.theme_mode, self.page
        )
        if hasattr(self.page, "theme_mode"):
            self.page.theme_mode = (
                ft.ThemeMode.DARK
                if effective_theme == "dark"
                else ft.ThemeMode.LIGHT
            )
        if hasattr(self.page, "on_resize"):
            self.page.on_resize = self.handle_window_resize
        if hasattr(self.page, "on_platform_brightness_change"):
            self.page.on_platform_brightness_change = (
                self.handle_brightness_change
            )
        window = getattr(self.page, "window", None)
        if window is not None and hasattr(window, "on_event"):
            window.on_event = self.handle_window_event

    def navigate(self, destination: str) -> None:
        self.current_destination = destination
        if destination == "dashboard":
            self.application.show_view("dashboard")
        elif destination == "work_insert":
            self.open_insert_work()
        elif destination == "Acervo":
            works = self.service.list_works()
            self.application.show_view("Acervo", works)
        elif destination == "Fragmentos":
            fragments = self.fragment_service.list_fragments()
            self.application.show_view(
                "Fragmentos",
                fragments=fragments,
            )
        elif destination == "Compilações":
            compilations = self.compilation_service.list_compilations()
            self.application.show_view(
                "Compilações",
                compilations=compilations,
            )
        elif destination in {
            "Nous",
            "Configurações",
            "Limbo",
            "Estruturas de Saber",
        }:
            self.application.show_view(destination)

    def create_composer(self) -> CoreComposer:
        return CoreComposer(
            page=self.page,
            scale=self.scale,
            config=self.view_config,
            on_navigate=self.navigate,
            on_work_click=self.open_work_details,
            on_edit_work=self.open_work_edit,
            on_format_reference=self.format_reference,
            on_copy_reference=self.copy_reference,
            on_delete_work=self.delete_work,
            on_create_parent_work=self.open_parent_work,
            on_fragment_save=self.save_fragment,
            on_fragment_delete=self.delete_fragment,
            search_fragment_works=self.search_fragment_works,
            search_compilation_works=self.search_compilation_works,
            refresh_compilations=self.compilation_service.list_compilations,
            on_compilation_create=self.create_compilation,
            on_compilation_update=self.update_compilation,
            on_compilation_delete=self.delete_compilation,
            on_compilation_add_work=self.add_work_to_compilation,
            on_compilation_remove_work=self.remove_work_from_compilation,
            on_compilation_reorder_works=self.reorder_compilation_works,
            on_compilation_fragment_membership=(
                self.set_compilation_fragment_membership
            ),
            on_compilation_fragment_note=(
                self.update_compilation_fragment_note
            ),
            on_compilation_section_create=self.create_compilation_section,
            on_compilation_section_update=self.update_compilation_section,
            on_compilation_section_delete=self.delete_compilation_section,
            on_compilation_section_reorder=self.reorder_compilation_sections,
            on_compilation_fragment_assign_section=(
                self.assign_compilation_fragment_to_section
            ),
            on_compilation_section_reorder_fragments=(
                self.reorder_compilation_section_fragments
            ),
            on_compilation_copy_caderno=self.copy_compilation_caderno,
            on_compilation_create_work=self.open_compilation_work_insert,
            on_compilation_edit_work=self.open_compilation_work_edit,
            on_compilation_create_fragment=(
                self.open_compilation_fragment_create
            ),
            on_compilation_edit_fragment=(
                self.open_compilation_fragment_edit
            ),
            get_knowledge_graph=self.get_knowledge_graph,
            sync_knowledge_mesh=self.sync_knowledge_mesh,
            get_knowledge_resonances=self.get_knowledge_resonances,
            on_create_knowledge_link=self.create_knowledge_link,
            on_add_knowledge_to_compilation=(
                self.add_knowledge_fragment_to_compilation
            ),
            current_theme_mode=self.settings.theme_mode,
            auto_scale=self.settings.auto_scale,
            manual_scale=self.settings.manual_scale,
            on_change_theme=self.change_theme,
            on_toggle_auto_scale=self.toggle_auto_scale,
            on_change_scale=self.change_scale,
            on_reset_settings=self.reset_settings,
            on_toggle_maximize=self.toggle_maximize,
            nous_service=self.nous_service,
        )

    def build_application(self) -> None:
        self.work_insert_modal = (
            CoreComposer.compose_work_insert_modal(
                page=self.page,
                config=self.view_config,
                on_save=self.submission_controller.handle_work_submission,
                search_authors=self.search_authors,
                search_works=self.search_works,
                on_create_parent_work=self.open_parent_work,
            )
        )
        self.application = self.create_composer()
        self.page.add(self.application.compose_main())

    def rebuild_ui(self) -> None:
        if not hasattr(self, "application") or self.application is None:
            return
        self.submission_controller.config = self.view_config
        self.work_insert_modal = (
            CoreComposer.compose_work_insert_modal(
                page=self.page,
                config=self.view_config,
                on_save=self.submission_controller.handle_work_submission,
                search_authors=self.search_authors,
                search_works=self.search_works,
                on_create_parent_work=self.open_parent_work,
            )
        )
        if hasattr(self.page, "clean"):
            self.page.clean()
        elif hasattr(self.page, "controls"):
            self.page.controls.clear()

        self.application = self.create_composer()
        self.page.add(self.application.compose_main())
        if self.current_destination != "dashboard":
            self.navigate(self.current_destination)
        if hasattr(self.page, "update"):
            self.page.update()

    def show_message(self, message: str, bgcolor: str) -> None:
        self.page.show_dialog(
            ft.SnackBar(
                content=ft.Text(
                    value=message, color=self.view_config.colors['surface']
                ),
                bgcolor=bgcolor,
            )
        )
