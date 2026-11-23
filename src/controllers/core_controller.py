"""Controlador principal da aplicação."""

import asyncio
import logging
import os
import threading

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
from src.db.maintenance import delete_local_databases
from src.services.desktop_boundary import close_desktop_view
from src.services import (
    CloudSyncService,
    CompilationService,
    FragmentService,
    WorkService,
    KnowledgeService,
    NousAIService,
    SettingsService,
    SyncStatus,
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
from src.utils.control_safety import safe_execute, safe_update
from src.utils.ui_thread import run_on_ui
from src.views import ui_kit as ui

logger = logging.getLogger('hupomnemata.lifecycle')
AUTO_SYNC_INTERVAL_SECONDS = 300


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
        self.cloud_sync_service = CloudSyncService()
        self._auto_sync_started = False
        self._shutting_down = False
        self._cloud_pull_suspended = (
            self.cloud_sync_service.sync_dir / 'auto_pull_suspended'
        ).exists()
        self._close_dialog_open = False
        self._close_dialog: ft.AlertDialog | None = None
        self._closing_sync = False
        self._close_watchdog_timer: threading.Timer | None = None
        self._auto_conflict_dialog_open = False
        self._auto_conflict_dialog: ft.AlertDialog | None = None
        self._last_auto_conflict_signature = None
        self._deleting_databases = False
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
        self.start_auto_sync()

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
        elif destination.startswith("pdf_reader:"):
            self.application.show_view(destination, **options)
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
        except Exception as error:
            log_exception("CoreController.sidebar_data", error)
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
        composer = CoreComposer(
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
            on_compilation_section_transfer=self.transfer_compilation_section,
            on_compilation_section_delete=self.delete_compilation_section,
            on_compilation_section_reorder=self.reorder_compilation_sections,
            on_compilation_fragment_assign_section=(
                self.assign_compilation_fragment_to_section
            ),
            on_compilation_fragment_link_section=(
                self.link_compilation_fragment_to_section
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
            on_request_close=self.request_close,
            on_delete_databases=self.delete_databases,
        )
        composer.cloud_sync_service = self.cloud_sync_service
        return composer

    # ── ciclo de vida: autosave e encerramento ─────────────

    def start_auto_sync(self) -> None:
        """Agenda o salvamento automático na nuvem a cada 5 minutos."""
        if self._auto_sync_started:
            return
        run_task = getattr(self.page, "run_task", None)
        if not callable(run_task):
            return
        self._auto_sync_started = True
        logger.info(
            'Autosave da nuvem ativo a cada %s segundos.',
            AUTO_SYNC_INTERVAL_SECONDS,
        )
        run_task(self._auto_sync_loop)

    async def _auto_sync_loop(self) -> None:
        while not self._shutting_down:
            await asyncio.sleep(AUTO_SYNC_INTERVAL_SECONDS)
            if self._shutting_down:
                break
            await self.perform_auto_sync()

    async def perform_auto_sync(self):
        """Executa uma rodada de autosave e devolve o ``SyncResult``."""
        if (
            self._shutting_down
            or self._closing_sync
            or self._close_dialog_open
            or self._auto_conflict_dialog_open
            or self._deleting_databases
            or self._cloud_pull_suspended
            or self._has_open_modal()
        ):
            return None
        try:
            result = await asyncio.to_thread(
                self.cloud_sync_service.sync,
                sync_pdfs=False,
            )
        except Exception as error:
            log_exception('Sincronização automática da nuvem', error)
            return None

        if result.status == SyncStatus.CONFLICT:
            logger.warning(
                'Autosave encontrou conflito com outra estação; '
                'aguardando decisão manual.'
            )
            self._show_auto_conflict(result)
        elif result.status == SyncStatus.ERROR:
            logger.warning('Autosave falhou: %s', result.message)
        elif result.status == SyncStatus.UNAUTHENTICATED:
            logger.debug('Autosave ignorado: nuvem não autenticada.')
        elif result.status == SyncStatus.NO_CHANGES:
            logger.debug('Autosave sem alterações.')
        elif result.status == SyncStatus.SUCCESS:
            logger.info(
                'Autosave concluído (%s): %s',
                result.direction or 'sync',
                result.message,
            )
            if result.direction == 'pull':
                # A nuvem substituiu o banco: a árvore de views precisa ser refeita.
                self.rebuild_ui()
        return result

    def _has_open_modal(self) -> bool:
        """Evita autosave/pull enquanto o usuário edita dentro de um modal."""
        if self.work_insert_modal is not None and getattr(
            self.work_insert_modal, 'open', False
        ):
            return True
        for control in getattr(self.page, 'overlay', None) or []:
            if isinstance(control, ft.AlertDialog) and getattr(
                control, 'open', False
            ):
                return True
        return False

    def _show_auto_conflict(self, result) -> None:
        """Avisa sobre conflito detectado pelo autosave e oferece a escolha."""
        if (
            self._close_dialog_open
            or self._auto_conflict_dialog_open
            or self._has_open_modal()
        ):
            return
        details = getattr(result, 'details', None) or {}
        if not isinstance(details, dict):
            details = {}
        remote = details.get('remote_manifest', {})
        if not isinstance(remote, dict):
            remote = {}
        signature = (remote.get('db_sha256'), details.get('local_sha256'))
        if signature == self._last_auto_conflict_signature:
            return
        self._last_auto_conflict_signature = signature
        self._auto_conflict_dialog_open = True

        c = self.view_config
        counts = remote.get('counts')
        if isinstance(counts, dict) and counts:
            detail = (
                f"Nuvem: {counts.get('resources', 0)} obras, "
                f"{counts.get('fragments', 0)} fragmentos, "
                f"{counts.get('compilations', 0)} compilações. "
                "Nada foi alterado nesta estação."
            )
        else:
            detail = (
                "A nuvem possui uma versão diferente desta estação. "
                "Nada foi alterado nesta estação."
            )
        dialog = ui.modal(
            c,
            title='Conflito de sincronização',
            subtitle='Autosave de 5 minutos',
            controls=[
                ui.ui_text(
                    c,
                    detail,
                    size=13,
                    color=c.colors['text'],
                    max_lines=None,
                ),
                ui.ui_text(
                    c,
                    'Escolha qual cópia deve prevalecer.',
                    size=12,
                    color=c.colors['muted'],
                    max_lines=None,
                ),
            ],
            actions=[
                ui.button(
                    c,
                    'Depois',
                    on_click=lambda _e: self._dismiss_auto_conflict(),
                    variant='default',
                ),
                ui.button(
                    c,
                    'Manter Nuvem',
                    on_click=lambda _e: self._resolve_auto_conflict('pull'),
                    variant='default',
                ),
                ui.button(
                    c,
                    'Manter Local',
                    on_click=lambda _e: self._resolve_auto_conflict('push'),
                    variant='primary',
                ),
            ],
            width=520,
            dismissible=True,
            on_dismiss=lambda _e: self._dismiss_auto_conflict(),
        )
        self._auto_conflict_dialog = dialog
        show_dialog = getattr(self.page, 'show_dialog', None)
        if callable(show_dialog):
            show_dialog(dialog)
        else:
            overlay = getattr(self.page, 'overlay', None)
            if overlay is not None:
                overlay.append(dialog)
                dialog.open = True
        safe_update(self.page)

    def _dismiss_auto_conflict(self) -> None:
        dialog = self._auto_conflict_dialog
        self._auto_conflict_dialog = None
        self._auto_conflict_dialog_open = False
        if dialog is not None:
            dialog.open = False
        safe_execute(
            'fechar aviso de conflito',
            getattr(self.page, 'pop_dialog', lambda: None),
        )
        safe_update(self.page)

    def _resolve_auto_conflict(self, direction: str) -> None:
        self._dismiss_auto_conflict()
        c = self.view_config
        label = (
            'Enviando dados locais para a nuvem...'
            if direction == 'push'
            else 'Baixando dados da nuvem...'
        )
        self.show_message(label, c.colors['gold'])

        def work() -> None:
            try:
                result = self.cloud_sync_service.sync(
                    force_push=direction == 'push',
                    force_pull=direction == 'pull',
                    sync_pdfs=False,
                )
            except Exception as error:
                log_exception('Resolução de conflito do autosave', error)
                result = None
            run_on_ui(
                self.page,
                lambda: self._after_auto_conflict(result, direction),
            )

        threading.Thread(target=work, daemon=True).start()

    def _after_auto_conflict(self, result, direction: str) -> None:
        c = self.view_config
        if result is not None and result.status in (
            SyncStatus.SUCCESS,
            SyncStatus.NO_CHANGES,
        ):
            self._last_auto_conflict_signature = None
            if direction == 'pull' or getattr(result, 'direction', None) == 'pull':
                self.rebuild_ui()
            self.show_message('Sincronização concluída.', c.colors['gold'])
            return
        if result is not None and result.status == SyncStatus.ERROR:
            self.show_message(result.message, c.colors['danger'])
        elif result is not None and result.status == SyncStatus.CONFLICT:
            self.show_message(
                'O conflito persiste; resolva na tela de configurações.',
                c.colors['danger'],
            )
        else:
            self.show_message(
                'Falha ao resolver o conflito de sincronização.',
                c.colors['danger'],
            )

    def delete_databases(self, delete_cloud: bool) -> None:
        """Apaga bancos locais e, opcionalmente, a cópia remota do banco.

        Executado em thread pelo painel de configurações. Toda mutação de UI
        é devolvida ao loop da página via ``run_on_ui``.
        """
        if self._deleting_databases:
            return
        self._deleting_databases = True
        try:
            marker = self.cloud_sync_service.sync_dir / 'auto_pull_suspended'
            with self.cloud_sync_service.sync_exclusive():
                if delete_cloud:
                    self.cloud_sync_service.delete_remote_database()
                    marker.unlink(missing_ok=True)
                else:
                    marker.write_text('1', encoding='utf-8')
                delete_local_databases()
                init_db()
            self._cloud_pull_suspended = not delete_cloud
            self._last_auto_conflict_signature = None
            logger.info(
                'Bancos apagados (nuvem=%s); base limpa recriada.',
                delete_cloud,
            )
            run_on_ui(
                self.page,
                lambda: self._after_delete_databases(None),
            )
        except Exception as error:
            log_exception('Falha ao apagar bancos de dados', error)
            run_on_ui(
                self.page,
                lambda err=error: self._after_delete_databases(err),
            )
        finally:
            self._deleting_databases = False

    def _after_delete_databases(self, error: Exception | None) -> None:
        c = self.view_config
        if error is not None:
            self.show_message(
                f'Não foi possível apagar os bancos: {error}',
                c.colors['danger'],
            )
            return
        self.rebuild_ui()
        if self._cloud_pull_suspended:
            self.show_message(
                'Bancos locais apagados. A cópia na nuvem foi preservada e o '
                'autosave está suspenso; sincronize manualmente para restaurá-la.',
                c.colors['gold'],
            )
        else:
            self.show_message(
                'Bancos de dados apagados e base limpa recriada.',
                c.colors['gold'],
            )

    def request_close(self) -> None:
        """Sincroniza automaticamente e encerra sem perguntar sobre salvar."""
        if self._auto_conflict_dialog_open:
            self._dismiss_auto_conflict()
        if self._shutting_down or self._closing_sync:
            return
        window = getattr(self.page, 'window', None)
        if window is not None:
            window.prevent_close = True
        self._closing_sync = True
        # Cobre também uma falha na criação/start do worker. O worker rearmará
        # o timer ao começar e ao receber o resultado da nuvem.
        self._arm_close_watchdog(45.0)
        self.show_message(
            'Sincronizando antes de sair...',
            self.view_config.colors['gold'],
        )
        threading.Thread(
            target=self._close_sync_worker,
            daemon=True,
        ).start()

    def _close_sync_worker(self) -> None:
        # Rede ou lock de autosave podem demorar. Se a sincronização não
        # devolver controle, o processo não pode ficar preso para sempre.
        self._arm_close_watchdog(45.0)
        try:
            result = self.cloud_sync_service.sync(sync_pdfs=False)
        except Exception as error:
            log_exception('Sincronização antes de sair', error)
            result = None
        logger.info(
            'Sincronização de saída concluída: %s',
            getattr(result, 'status', None),
        )
        terminal = result is not None and result.status in (
            SyncStatus.SUCCESS,
            SyncStatus.NO_CHANGES,
            SyncStatus.UNAUTHENTICATED,
        )
        if terminal:
            # Se a ponte para a thread de UI falhar, o app não pode ficar
            # preso na tela de despedida.
            self._arm_close_watchdog(6.0)
        else:
            # Conflito ou erro exigem decisão humana; não matar o app.
            self._cancel_close_watchdog()
        run_on_ui(
            self.page,
            lambda: self._after_close_sync(result),
        )

    def _after_close_sync(self, result) -> None:
        if result is not None and result.status in (
            SyncStatus.SUCCESS,
            SyncStatus.NO_CHANGES,
        ):
            self._shutdown()
            return
        if (
            result is not None
            and result.status == SyncStatus.UNAUTHENTICATED
        ):
            logger.info(
                'Encerrando sem nuvem autenticada; dados locais preservados.'
            )
            self._shutdown()
            return
        if result is not None and result.status == SyncStatus.CONFLICT:
            self._show_close_conflict(result)
            return
        self._show_close_error(result)

    def _show_close_conflict(self, result) -> None:
        self._cancel_close_watchdog()
        c = self.view_config
        details = getattr(result, 'details', None) or {}
        if not isinstance(details, dict):
            details = {}
        remote = details.get('remote_manifest', {})
        if not isinstance(remote, dict):
            remote = {}
        counts = remote.get('counts')
        if isinstance(counts, dict) and counts:
            detail = (
                f"Nuvem: {counts.get('resources', 0)} obras, "
                f"{counts.get('fragments', 0)} fragmentos, "
                f"{counts.get('compilations', 0)} compilações."
            )
        else:
            detail = 'A nuvem possui uma versão diferente desta estação.'
        dialog = ui.modal(
            c,
            title='Conflito de sincronização',
            subtitle='Escolha antes de encerrar',
            controls=[
                ui.ui_text(
                    c,
                    detail,
                    size=13,
                    color=c.colors['text'],
                    max_lines=None,
                ),
                ui.ui_text(
                    c,
                    'Nada foi alterado. Use Cancelar para permanecer no app.',
                    size=12,
                    color=c.colors['muted'],
                    max_lines=None,
                ),
            ],
            actions=[
                ui.button(
                    c,
                    'Cancelar',
                    on_click=lambda _e: self._cancel_close(),
                    variant='default',
                ),
                ui.button(
                    c,
                    'Manter Nuvem',
                    on_click=lambda _e: self._resolve_close_conflict('pull'),
                    variant='default',
                ),
                ui.button(
                    c,
                    'Manter Local',
                    on_click=lambda _e: self._resolve_close_conflict('push'),
                    variant='primary',
                ),
            ],
            width=560,
            dismissible=False,
        )
        self._close_dialog = dialog
        self._close_dialog_open = True
        safe_execute(
            'abrir conflito de saída',
            getattr(self.page, 'show_dialog', lambda _dialog: None),
            dialog,
        )
        safe_update(self.page)

    def _resolve_close_conflict(self, direction: str) -> None:
        self._dismiss_close_dialog()
        self._closing_sync = True
        self._arm_close_watchdog(45.0)
        self.show_message(
            'Resolvendo conflito antes de sair...',
            self.view_config.colors['gold'],
        )

        def work() -> None:
            try:
                result = self.cloud_sync_service.sync(
                    force_push=direction == 'push',
                    force_pull=direction == 'pull',
                    sync_pdfs=False,
                )
            except Exception as error:
                log_exception('Resolução de conflito antes de sair', error)
                result = None
            if result is not None and result.status in (
                SyncStatus.SUCCESS,
                SyncStatus.NO_CHANGES,
                SyncStatus.UNAUTHENTICATED,
            ):
                self._arm_close_watchdog(6.0)
            else:
                self._cancel_close_watchdog()
            run_on_ui(
                self.page,
                lambda: self._after_close_sync(result),
            )

        threading.Thread(target=work, daemon=True).start()

    def _show_close_error(self, result) -> None:
        self._cancel_close_watchdog()
        c = self.view_config
        detail = (
            getattr(result, 'message', 'erro desconhecido')
            if result is not None
            else 'erro desconhecido'
        )
        dialog = ui.modal(
            c,
            title='Não foi possível salvar antes de sair',
            subtitle='A base local permanece intacta',
            controls=[
                ui.ui_text(
                    c,
                    f'Falha ao sincronizar: {detail}',
                    size=13,
                    color=c.colors['text'],
                    max_lines=None,
                )
            ],
            actions=[
                ui.button(
                    c,
                    'Cancelar',
                    on_click=lambda _e: self._cancel_close(),
                    variant='default',
                ),
                ui.button(
                    c,
                    'Sair mesmo assim',
                    on_click=lambda _e: self._exit_without_save(),
                    variant='default',
                ),
                ui.button(
                    c,
                    'Tentar novamente',
                    on_click=lambda _e: self._retry_close_sync(),
                    variant='primary',
                ),
            ],
            width=540,
            dismissible=False,
        )
        self._close_dialog = dialog
        self._close_dialog_open = True
        safe_execute(
            'abrir erro de saída',
            getattr(self.page, 'show_dialog', lambda _dialog: None),
            dialog,
        )
        safe_update(self.page)

    def _retry_close_sync(self) -> None:
        self._dismiss_close_dialog()
        self._closing_sync = True
        threading.Thread(
            target=self._close_sync_worker,
            daemon=True,
        ).start()

    def _dismiss_close_dialog(self) -> None:
        dialog = self._close_dialog
        self._close_dialog = None
        self._close_dialog_open = False
        if dialog is not None:
            dialog.open = False
        safe_execute(
            'fechar diálogo de saída',
            getattr(self.page, 'pop_dialog', lambda: None),
        )
        safe_update(self.page)

    def _cancel_close(self) -> None:
        self._cancel_close_watchdog()
        self._dismiss_close_dialog()
        self._closing_sync = False

    def _exit_without_save(self) -> None:
        self._dismiss_close_dialog()
        self._shutdown()

    def _arm_close_watchdog(self, seconds: float) -> None:
        """Garante o encerramento do processo se o destroy do Flet falhar.

        Só é usado quando a sincronização já terminou e não há conflito
        pendente. Em duplos de teste, ``run_task`` é ausente e nenhum
        watchdog é armado.
        """
        if not callable(getattr(self.page, 'run_task', None)):
            return
        self._cancel_close_watchdog()
        timer = threading.Timer(seconds, self._force_exit)
        timer.daemon = True
        self._close_watchdog_timer = timer
        timer.start()

    def _cancel_close_watchdog(self) -> None:
        timer = self._close_watchdog_timer
        self._close_watchdog_timer = None
        if timer is not None:
            timer.cancel()

    def _force_exit(self) -> None:
        """Último recurso: encerra o processo após a sincronização terminal."""
        logger.warning(
            'Destruição da janela não concluiu; encerrando o processo.'
        )
        try:
            # Flet Desktop é outro processo. Matar apenas o backend deixaria
            # a janela aberta tentando reconectar; fecha-se o PID registrado.
            close_desktop_view()
        finally:
            for handler in logging.getLogger('hupomnemata').handlers:
                handler.flush()
            os._exit(0)

    def _shutdown(self) -> None:
        self._shutting_down = True
        self._closing_sync = False
        self._close_dialog_open = False
        self._cancel_close_watchdog()
        dialog = self._close_dialog
        self._close_dialog = None
        if dialog is not None:
            dialog.open = False
        window = getattr(self.page, 'window', None)
        if window is None:
            return
        # A sincronização já foi concluída. Se o cliente Flet não fechar a
        # janela, o processo é encerrado pelo watchdog.
        self._arm_close_watchdog(4.0)
        window.prevent_close = False
        # Sincroniza o flag com o cliente antes de destruir a janela.
        safe_update(self.page)
        destroy = getattr(window, 'destroy', None)
        close = getattr(window, 'close', None)
        action = destroy if callable(destroy) else close
        if not callable(action):
            self._force_exit()
            return
        run_task = getattr(self.page, 'run_task', None)
        try:
            if callable(run_task):
                run_task(action)
            else:
                action()
        except Exception as error:
            log_exception('Falha ao destruir a janela', error)
            self._force_exit()

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
            # Guarda de UI: se o toast rico falhar, cai para SnackBar nativo.
            self.page.show_dialog(ft.SnackBar(content=ft.Text(value=message)))
            if hasattr(self.page, "update"):
                safe_update(self.page)
