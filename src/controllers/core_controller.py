"""Controlador principal da aplicação."""

import flet as ft

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
from src.views.sidebar import SidebarData
from src.views.works import AcervoContext
from src.utils.error_log import log_exception
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
        if hasattr(self.page, "on_keyboard_event"):
            self.page.on_keyboard_event = self.handle_keyboard
        if hasattr(self.page, "on_resize"):
            self.page.on_resize = self.handle_window_resize
        if hasattr(self.page, "on_platform_brightness_change"):
            self.page.on_platform_brightness_change = (
                self.handle_brightness_change
            )
        window = getattr(self.page, "window", None)
        if window is not None and hasattr(window, "on_event"):
            window.on_event = self.handle_window_event

    def navigate(self, destination: str, push_history: bool = True, **options) -> None:
        """Abre um destino. ``options`` segue para a view (ex.: ``focus_work_id``)."""
        if destination == "work_insert":
            self.open_insert_work()
            return
        if push_history:
            self._push_history(destination)
        self.current_destination = destination
        if destination == "dashboard":
            self.application.show_view("dashboard", **options)
        elif destination == "Acervo":
            works = self.service.list_works()
            self.application.show_view("Acervo", works, **options)
        elif destination == "Fragmentos":
            fragments = self.fragment_service.list_fragments()
            self.application.show_view(
                "Fragmentos",
                fragments=fragments,
                **options,
            )
        elif destination == "Compilações" or destination.startswith("compilacao:"):
            compilations = self.compilation_service.list_compilations()
            self.application.show_view(
                destination,
                compilations=compilations,
                **options,
            )
        elif destination in {
            "Nous",
            "Configurações",
            "Limbo",
            "Estruturas de Saber",
        }:
            self.application.show_view(destination)
        self._sync_history_buttons()

    def navigate_with(self, destination: str, **options) -> None:
        self.navigate(destination, **options)

    # ── histórico (voltar / avançar) ───────────────────────

    def _push_history(self, destination: str) -> None:
        history = getattr(self, "_history", None)
        if history is None:
            self._history, self._history_index = [], -1
        if self._history and self._history[self._history_index] == destination:
            return
        self._history = self._history[: self._history_index + 1] + [destination]
        self._history_index = len(self._history) - 1

    def go_history(self, step: int) -> None:
        history = getattr(self, "_history", [])
        target = getattr(self, "_history_index", -1) + step
        if not 0 <= target < len(history):
            return
        self._history_index = target
        self.navigate(history[target], push_history=False)

    def _sync_history_buttons(self) -> None:
        application = getattr(self, "application", None)
        if application is None or not hasattr(application, "set_history_state"):
            return
        history = getattr(self, "_history", [])
        index = getattr(self, "_history_index", -1)
        application.set_history_state(index > 0, index < len(history) - 1)

    # ── dados do shell ─────────────────────────────────────

    def sidebar_data(self) -> SidebarData:
        try:
            works = sum(
                1 for r in self.service.list_works()
                if not getattr(r, "is_magazine", False)
            )
            fragments = len(self.fragment_service.list_fragments())
            compilations = [
                (record["id"], record["name"])
                for record in self.compilation_service.list_compilations()
            ]
        except Exception:
            return SidebarData()
        return SidebarData(works=works, fragments=fragments, compilations=compilations)

    def palette_search(self, query: str) -> dict:
        query = (query or "").strip().lower()
        works = []
        for resource in self.service.list_works():
            if getattr(resource, "is_magazine", False):
                continue
            work = resource.specific_work
            if work is None:
                continue
            authors = ", ".join(
                (author.corporation if isinstance(author.corporation, str) else None)
                or " ".join(filter(None, [author.given_names, author.last_name]))
                for author in (getattr(work, "authors", None) or [])
            )
            haystack = f"{work.title} {authors} {getattr(work, 'display_year', '')}".lower()
            if not query or query in haystack:
                works.append((resource.id, work.title, authors or "Sem autoria", "book"))
        fragments = []
        if query:
            for record in self.fragment_service.list_fragments():
                if query in str(record.get("excerpt", "")).lower():
                    fragments.append((record["id"], record["excerpt"], record["work_title"]))
        works.sort(key=lambda item: -item[0])
        return {"works": works, "fragments": fragments}

    def acervo_context(self) -> AcervoContext:
        fragments_by_work: dict[int, list[dict]] = {}
        compilations_by_work: dict[int, list[tuple[int, str]]] = {}
        compilations: list[tuple[int, str]] = []
        try:
            for record in self.fragment_service.list_fragments():
                fragments_by_work.setdefault(record["bib_res_id"], []).append(record)
            for record in self.compilation_service.list_compilations():
                compilations.append((record["id"], record["name"]))
                for work in record.get("works", []):
                    compilations_by_work.setdefault(work["id"], []).append((record["id"], record["name"]))
        except Exception as error:
            log_exception("Falha ao montar o contexto do Acervo", error)
        return AcervoContext(fragments_by_work=fragments_by_work, compilations_by_work=compilations_by_work, compilations=compilations)

    def dashboard_data(self) -> dict:
        """Dados reais da tela Início: obras, fragmentos e compilações."""
        from src.utils.types import WORK_TYPE_LABELS

        data: dict = {"works": [], "fragments": [], "compilations": []}
        try:
            for resource in self.service.list_works():
                if getattr(resource, "is_magazine", False):
                    continue
                work = resource.specific_work
                if work is None:
                    continue
                authors = ", ".join(
                    name
                    for name in (
                        author.given_names
                        if author.corporation
                        else " ".join(filter(None, (author.given_names, author.last_name)))
                        for author in (getattr(resource, "authors", None) or [])
                    )
                    if name
                )
                data["works"].append({
                    "id": resource.id,
                    "title": work.title,
                    "authors": authors,
                    "type": WORK_TYPE_LABELS.get(type(work).__name__, type(work).__name__),
                    "year": getattr(work, "display_year", "") or "",
                    "created_at": getattr(work, "created_at", None),
                })
            for record in self.fragment_service.list_fragments():
                data["fragments"].append({
                    "id": record["id"],
                    "kind": record["fragment_type"],
                    "excerpt": record["excerpt"],
                    "bib_res_id": record["bib_res_id"],
                    "work_title": record["work_title"],
                    "created_at": record.get("created_at"),
                })
            for record in self.compilation_service.list_compilations():
                works = record.get("works", [])
                data["compilations"].append({
                    "id": record["id"],
                    "name": record["name"],
                    "description": record.get("description"),
                    "work_ids": [work["id"] for work in works],
                    "fragments": sum(
                        1
                        for work in works
                        for fragment in work.get("fragments", [])
                        if fragment.get("is_member")
                    ),
                    "ideas": len(record.get("sections", [])),
                    "updated_at": record.get("updated_at") or record.get("created_at"),
                })
        except Exception as error:
            log_exception("Falha ao montar os dados do Início", error)
        return data

    def toggle_theme(self) -> None:
        current = "dark" if self.view_config.colors == COLORS_DARK else "light"
        self.change_theme("light" if current == "dark" else "dark")

    def new_compilation(self) -> None:
        self.navigate("Compilações", create=True)

    def handle_keyboard(self, event) -> None:
        key = getattr(event, "key", "")
        mod = bool(getattr(event, "meta", False) or getattr(event, "ctrl", False))
        application = getattr(self, "application", None)
        if application is not None and application.handle_palette_key(key):
            return
        if application is not None and hasattr(application, "handle_view_key") and application.handle_view_key(key, mod):
            return
        if mod and key.upper() == "K":
            application.open_palette()
        elif mod and key.upper() == "N":
            self.open_insert_work()
        elif mod and key.upper() == "I":
            self.open_import_work()
        elif mod and key.upper() == "R":
            self.open_reverse_import()
        elif mod and key == "[":
            self.go_history(-1)
        elif mod and key == "]":
            self.go_history(1)

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
            get_knowledge_work_fragments=self.get_knowledge_work_fragments,
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
            get_sidebar_data=self.sidebar_data,
            on_history=self.go_history,
            on_toggle_theme=self.toggle_theme,
            on_new_compilation=self.new_compilation,
            palette_search=self.palette_search,
            on_navigate_with=self.navigate_with,
            get_acervo_context=self.acervo_context,
            on_delete_works=self.delete_works,
            get_dashboard_data=self.dashboard_data,
            compilation_work_references=self.compilation_work_references,
            on_import_work=self.open_import_work,
            on_reverse_import=self.open_reverse_import,
            on_update_magazine=self.update_magazine,
            on_delete_magazine=self.delete_magazine_cascade,
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
                on_navigate_to_work=lambda wid: self.navigate_with("Acervo", focus_work_id=wid),
            )
        )
        self.application = self.create_composer()
        self.page.add(self.application.compose_main())
        self._push_history("dashboard")

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
                on_navigate_to_work=lambda wid: self.navigate_with("Acervo", focus_work_id=wid),
            )
        )
        if hasattr(self.page, "clean"):
            self.page.clean()
        elif hasattr(self.page, "controls"):
            self.page.controls.clear()

        self.application = self.create_composer()
        self.page.add(self.application.compose_main())
        if self.current_destination != "dashboard":
            self.navigate(self.current_destination, push_history=False)
        else:
            self._sync_history_buttons()
        if hasattr(self.page, "update"):
            self.page.update()

    def show_message(self, message: str, bgcolor: str) -> None:
        """Aviso curto no padrão v2. Cor de texto/erro vira ícone de alerta."""
        from src.views import ui_kit

        is_error = bgcolor in {self.view_config.colors.get("text"), self.view_config.colors.get("danger")} or message.lower().startswith(("não ", "erro", "falha"))
        try:
            ui_kit.toast(
                self.page,
                self.view_config,
                message,
                icon_name="circle-exclamation" if is_error else "circle-check",
            )
        except Exception:
            self.page.show_dialog(ft.SnackBar(content=ft.Text(value=message)))
