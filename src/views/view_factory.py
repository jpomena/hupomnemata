"""Fábrica de telas do gabinete.

Concentra a composição das views navegáveis, mantendo o ``CoreComposer``
responsável apenas pelo shell (barra de título, sidebar, paleta e modais).
A fábrica é instanciada de forma preguiçosa por ``CoreComposer._view_factory``
para continuar funcionando quando o composer é criado via ``__new__``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from src.contracts import CompilationRecord, FragmentRecord
from src.domains import BibliographicResource
from src.views import ui_kit as ui
from src.views.compilations import CompilationsComposer
from src.views.dashboard import DashboardComposer
from src.views.fragments import FragmentsComposer
from src.views.knowledge import KnowledgeComposer
from src.views.nous_composer import NousComposer
from src.views.settings import SettingsComposer
from src.views.works import WorksComposer

if TYPE_CHECKING:
    from src.views.core_composer import CoreComposer


class ViewFactory:
    """Compõe as telas navegáveis a partir do estado do ``CoreComposer``."""

    def __init__(self, composer: "CoreComposer"):
        self.composer = composer

    # ── telas principais ───────────────────────────────────

    def dashboard(self) -> ft.Control:
        c = self.composer
        return DashboardComposer(
            scale=c.scale,
            config=c.config,
            on_navigate=c.on_navigate,
            get_dashboard_data=getattr(c, "get_dashboard_data", None),
            on_navigate_with=getattr(c, "on_navigate_with", None),
            on_new_fragment=c.open_fragment_create,
            on_open_palette=c.open_palette,
            on_import_work=getattr(c, "on_import_work", None),
            on_reverse_import=getattr(c, "on_reverse_import", None),
        ).compose()

    def placeholder(self, section: str) -> ft.Control:
        c = self.composer
        return DashboardComposer(
            scale=c.scale,
            config=c.config,
            on_navigate=c.on_navigate,
        ).compose_placeholder(section)

    def settings(self) -> ft.Control:
        c = self.composer
        return SettingsComposer(
            scale=c.scale,
            config=c.config,
            current_theme_mode=c.current_theme_mode,
            auto_scale=c.auto_scale,
            manual_scale=c.manual_scale,
            effective_scale=c.scale,
            on_navigate=c.on_navigate,
            on_change_theme=c.on_change_theme or (lambda _: None),
            on_toggle_auto_scale=c.on_toggle_auto_scale or (lambda _: None),
            on_change_scale=c.on_change_scale or (lambda _: None),
            on_reset_settings=c.on_reset_settings or (lambda: None),
            cloud_sync_service=getattr(c, "cloud_sync_service", None),
            page=getattr(c, "page", None),
            on_delete_databases=getattr(c, "on_delete_databases", None),
        ).compose()

    def nous(self) -> ft.Control:
        c = self.composer
        c.nous_composer = NousComposer(
            page=getattr(c, "page", None),
            config=c.config,
            scale=c.scale,
            on_navigate=c.on_navigate,
            nous_service=getattr(c, "nous_service", None),
            current_theme_mode=getattr(c, "current_theme_mode", "light"),
        )
        return c.nous_composer.compose()

    def knowledge(self) -> ft.Control:
        c = self.composer
        c.knowledge_composer = KnowledgeComposer(
            page=getattr(c, "page", None),
            config=c.config,
            scale=c.scale,
            on_navigate=c.on_navigate,
            get_graph_data=getattr(c, "get_knowledge_graph", None)
            or (lambda _: {"nodes": [], "links": [], "clusters": []}),
            sync_mesh=getattr(c, "sync_knowledge_mesh", None)
            or (lambda: {"vectorized": 0, "clusters": 0}),
            get_resonances=getattr(c, "get_knowledge_resonances", None)
            or (lambda *_: []),
            get_work_fragments=getattr(c, "get_knowledge_work_fragments", None)
            or (lambda _: []),
            on_add_to_compilation=getattr(
                c, "on_add_knowledge_to_compilation", None
            ),
            list_compilations=getattr(c, "refresh_compilations", None),
            on_create_link=getattr(c, "on_create_knowledge_link", None),
            current_theme_mode=getattr(c, "current_theme_mode", "light"),
        )
        return c.knowledge_composer.compose()

    # ── Acervo, Fragmentos e Compilações ───────────────────

    def works(
        self,
        works: list[BibliographicResource] | None,
    ) -> ft.Control:
        c = self.composer
        options = getattr(c, "view_options", {}) or {}
        context = (
            c.get_acervo_context()
            if getattr(c, "get_acervo_context", None)
            else None
        )
        c.works_composer = WorksComposer(
            scale=c.scale,
            config=c.config,
            works=works or [],
            on_navigate=c.on_navigate,
            on_work_click=c.on_work_click,
            on_edit_work=c.on_edit_work,
            format_reference=c.on_format_reference,
            on_copy_reference=c.on_copy_reference,
            on_delete_work=c.on_delete_work,
            page=c.page,
            context=context,
            focus_work_id=options.get("focus_work_id"),
            type_filter=options.get("type_filter"),
            sort_key=options.get("sort_key"),
            sort_desc=options.get("sort_desc"),
            on_add_to_compilation=c.on_compilation_add_work,
            on_delete_works=getattr(c, "on_delete_works", None),
            nous_service=getattr(c, "nous_service", None),
            on_import_work=getattr(c, "on_import_work", None),
            on_update_magazine=getattr(c, "on_update_magazine", None),
            on_delete_magazine=getattr(c, "on_delete_magazine", None),
        )
        return c.works_composer.compose()

    def fragments(
        self,
        fragments: list[FragmentRecord] | None,
    ) -> ft.Control:
        c = self.composer
        options = getattr(c, "view_options", {}) or {}
        on_navigate_with = getattr(c, "on_navigate_with", None)
        composer = FragmentsComposer(
            page=c.page,
            config=c.config,
            fragments=fragments or [],
            search_works=c.search_fragment_works,
            on_save=c.on_fragment_save,
            on_delete=c.on_fragment_delete,
            on_copy_reference=c.on_copy_reference,
            compilations_by_fragment=self._fragment_compilations(),
            on_open_work=(
                (lambda work_id: on_navigate_with("Acervo", focus_work_id=work_id))
                if on_navigate_with is not None
                else None
            ),
            initial_query=str(options.get("query") or ""),
        )
        control = composer.compose()
        if options.get("create"):
            composer.open_create()
        elif options.get("open_create_work_id"):
            composer.open_create_for_work(
                bib_res_id=int(options["open_create_work_id"]),
                title=str(options.get("work_title") or ""),
                initial_location_type=options.get("initial_location_type"),
                initial_location_value=options.get("initial_location_value"),
                initial_excerpt=options.get("initial_excerpt"),
            )
        return control

    def compilations(
        self,
        compilations: list[CompilationRecord] | None,
    ) -> ft.Control:
        c = self.composer
        c.compilations_composer = CompilationsComposer(
            page=c.page,
            config=c.config,
            compilations=compilations or [],
            search_works=c.search_compilation_works,
            refresh_compilations=c.refresh_compilations,
            on_create=c.on_compilation_create,
            on_update=c.on_compilation_update,
            on_delete=c.on_compilation_delete,
            on_add_work=c.on_compilation_add_work,
            on_remove_work=c.on_compilation_remove_work,
            on_reorder_works=c.on_compilation_reorder_works,
            on_fragment_membership=c.on_compilation_fragment_membership,
            on_fragment_note=c.on_compilation_fragment_note,
            on_create_section=c.on_compilation_section_create,
            on_update_section=c.on_compilation_section_update,
            on_transfer_section=c.on_compilation_section_transfer,
            on_delete_section=c.on_compilation_section_delete,
            on_reorder_sections=c.on_compilation_section_reorder,
            on_assign_fragment_to_section=(
                c.on_compilation_fragment_assign_section
            ),
            on_link_fragment_to_section=(
                c.on_compilation_fragment_link_section
            ),
            on_reorder_section_fragments=(
                c.on_compilation_section_reorder_fragments
            ),
            on_copy_caderno=c.on_compilation_copy_caderno,
            on_create_work=c.on_compilation_create_work,
            on_edit_work=c.on_compilation_edit_work,
            on_create_fragment=c.on_compilation_create_fragment,
            on_edit_fragment=c.on_compilation_edit_fragment,
            on_navigate=c.on_navigate,
            on_open_work=lambda work_id: c.on_navigate_with(
                "Acervo", focus_work_id=work_id
            ),
            on_chrome_changed=c.refresh_chrome,
            work_references=getattr(c, "compilation_work_references", None),
        )
        return c.compilations_composer.compose(
            open_create=bool(c.view_options.get("create"))
        )

    def compilation_page(
        self,
        compilations: list[CompilationRecord] | None,
        compilation_id: int,
    ) -> ft.Control:
        """Página de uma compilação; se ela não existe mais, cai na lista."""
        c = self.composer
        control = self.compilations(compilations)
        if c.compilations_composer is not None:
            return (
                c.compilations_composer.open_compilation_page(compilation_id)
                or control
            )
        return control

    # ── leitor de PDF ──────────────────────────────────────

    def pdf_reader(self, work_id: int) -> ft.Control:
        """Espaço imersivo de leitura e anotação do PDF da obra."""
        from src.services.pdf_service import PdfService
        from src.views.pdf_reader import PdfReaderView

        c = self.composer
        pdf_service = PdfService()
        context = pdf_service.reader_context(work_id)
        if context is None:
            return ui.empty_state(
                c.config,
                "triangle-exclamation",
                "Obra não encontrada",
                "A obra solicitada para leitura não pôde ser localizada.",
            )

        resource, work_title = context
        if c.page:
            ui.toast(
                c.page,
                c.config,
                f"Carregando leitor: {work_title}...",
                icon_name="book-open",
            )

        reader_holder: list[PdfReaderView] = []

        def on_back():
            if reader_holder:
                reader_holder[0].close()
            c.on_navigate_with("Acervo", focus_work_id=work_id)

        reader_view = PdfReaderView(
            config=c.config,
            resource=resource,
            on_back=on_back,
            pdf_service=pdf_service,
            page=c.page,
        )
        reader_holder.append(reader_view)
        c.pdf_reader_view = reader_view
        return reader_view

    # ── apoio ──────────────────────────────────────────────

    def _fragment_compilations(self) -> dict[int, list[str]]:
        """Nomes das compilações em que cada fragmento entrou (selo na linha)."""
        c = self.composer
        names: dict[int, list[str]] = {}
        refresh = getattr(c, "refresh_compilations", None)
        if refresh is None:
            return names
        try:
            compilations = refresh() or []
        except Exception:
            return names
        for compilation in compilations:
            for work in compilation.get("works", []):
                for fragment in work.get("fragments", []):
                    if fragment.get("is_member"):
                        names.setdefault(fragment["id"], []).append(
                            compilation["name"]
                        )
        return names
