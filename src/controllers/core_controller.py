import flet as ft
from datetime import date, datetime
from collections.abc import Callable
from sqlalchemy import inspect as sqlalchemy_inspect

import src.domains  # noqa: F401
from src.configs.settings import (
    COLORS,
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
from src.domains import (
    AudiovisualDocument,
    AudioDocument,
    CaseLaw,
    CartographicDocument,
    CorrespondenceMonograph,
    EditorialMonograph,
    JournalArticle,
    Magazine,
    MiscDigitalDocument,
    MonographicProceedings,
    MusicalScore,
    NewspaperArticle,
    PeriodicalCollection,
    PeriodicalProceedings,
    Statute,
    ThreeDimensionalDocument,
    VisualDocument,
    AcademicMonograph,
    DatePrecision,
    BibliographicResource,
    WorkMixin,
)
from typing import cast

from src.contracts import AuthorSearchResult
from src.services import WorkService
from src.utils.normalizers import CoreNormalizer
from src.strategies import (
    DigitalFormatter,
    LegalDocsFormatter,
    MonographFormatter,
    AudiovisualFormatter,
    AudioFormatter,
    CartographicFormatter,
    MusicalScoreFormatter,
    PeriodicalFormatter,
    ProceedingsFormatter,
    ThreeDimensionalFormatter,
    VisualFormatter,
)
from src.utils.ft_responsiveness import Responsive
from src.views.core_composer import CoreComposer
from src.views.page_config import PageConfigurator
from src.utils.types import ViewConfig
from src.utils.clipboard import copy_reference as copy_reference_html
from src.utils.types import ViewReference
from src.utils.error_log import log_exception
from src.views.work_insert_specs import (
    WORK_TYPES,
)
from src.services.work_form_service import WorkFormService
from src.controllers.work_submission_controller import (
    WorkSubmissionController,
)


class CoreController:
    """Orquestra o ciclo de vida e os fluxos principais da aplicação."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.work_insert_modal: ft.AlertDialog | None = None
        self.normalizer = CoreNormalizer()
        self.service = WorkService(self.normalizer)
        self.form_service = WorkFormService(self.normalizer)
        self.view_config = ViewConfig(
            colors=COLORS,
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

    def navigate(self, destination: str) -> None:
        if destination == "dashboard":
            self.application.show_view("dashboard")
        if destination == "work_insert":
            self.open_insert_work()
        if destination == "Acervo":
            works = self.service.list_works()
            self.application.show_view("Acervo", works)
        if destination == "Fragmentos":
            self.application.show_view("Fragmentos")

    def build_application(self) -> None:
        scale = Responsive.get_scale(self.page)
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
        self.application = CoreComposer(
            page=self.page,
            scale=scale,
            config=self.view_config,
            on_navigate=self.navigate,
            on_work_click=self.open_work_details,
            on_edit_work=self.open_work_edit,
            on_format_reference=self.format_reference,
            on_copy_reference=self.copy_reference,
            on_delete_work=self.delete_work,
            on_create_parent_work=self.open_parent_work,
        )
        self.page.add(self.application.compose_main())

    def open_insert_work(self) -> None:
        if self.work_insert_modal is not None:
            self.page.show_dialog(self.work_insert_modal)

    def open_work_details(self, resource) -> None:
        modal = CoreComposer.compose_work_details_popup(
            resource=resource,
            config=self.view_config,
            on_close=lambda: self.close_dialog(modal),
        )
        self.page.show_dialog(modal)

    @staticmethod
    def format_reference(
        resource: BibliographicResource,
    ) -> ViewReference | None:
        """Select and run the reference strategy for a bibliographic work."""
        work = resource.specific_work
        if work is None:
            return None
        if isinstance(
            work,
            (
                EditorialMonograph,
                AcademicMonograph,
                CorrespondenceMonograph,
            ),
        ):
            return MonographFormatter.formatter(resource)
        if isinstance(
            work,
            (
                PeriodicalCollection,
                JournalArticle,
                Magazine,
                NewspaperArticle,
            ),
        ):
            return PeriodicalFormatter.formatter(resource)
        if isinstance(work, (MonographicProceedings, PeriodicalProceedings)):
            return ProceedingsFormatter.formatter(resource)
        if isinstance(work, (Statute, CaseLaw)):
            return LegalDocsFormatter.formatter(work)
        if isinstance(work, MiscDigitalDocument):
            return DigitalFormatter.formatter(work)
        if isinstance(work, AudiovisualDocument):
            return AudiovisualFormatter.formatter(work)
        if isinstance(work, AudioDocument):
            return AudioFormatter.formatter(work)
        if isinstance(work, MusicalScore):
            return MusicalScoreFormatter.formatter(resource)
        if isinstance(work, VisualDocument):
            return VisualFormatter.formatter(work)
        if isinstance(work, CartographicDocument):
            return CartographicFormatter.formatter(work)
        if isinstance(work, ThreeDimensionalDocument):
            return ThreeDimensionalFormatter.formatter(work)
        return None

    def open_work_edit(self, resource) -> None:
        """Open a pre-populated form to edit the selected resource."""
        work = resource.specific_work
        if work is None:
            self.show_message(
                'A obra cadastrada não possui detalhes disponíveis.',
                COLORS['text'],
            )
            return

        work_type = next(
            (
                spec.key
                for spec in WORK_TYPES
                if self.service.work_model_for(spec.key) is type(work)
            ),
            None,
        )
        if work_type is None:
            self.show_message(
                'Não há formulário de edição para este tipo de obra.',
                COLORS['text'],
            )
            return

        initial_values = self._edit_form_values(work, work_type)
        authors = []
        for author in resource.authors:
            jurisdiction = author.jurisdiction
            authors.append({
                'name': (
                    author.given_names
                    if author.corporation
                    else f'{author.given_names} {author.last_name}'.strip()
                ),
                'id': author.id,
                'corporation': author.corporation,
                'acronym': author.acronym,
                'jurisdiction_id': (
                    jurisdiction.id if jurisdiction is not None else None
                ),
                'jurisdiction_name': (
                    jurisdiction.given_names
                    if jurisdiction is not None
                    else None
                ),
            })

        parent_id = getattr(work, 'parent_bibliographic_resource_id', None)
        parent_title = (
            self.service.get_work_title(parent_id)
            if parent_id is not None
            else None
        )
        modal = CoreComposer.compose_work_insert_modal(
            page=self.page,
            config=self.view_config,
            on_save=lambda form_data: self.handle_work_update(
                resource.id, form_data
            ),
            search_authors=self.search_authors,
            search_works=self.search_works,
            on_create_parent_work=self.open_parent_work,
            initial_work_type=work_type,
            edit_mode=True,
            initial_values=initial_values,
            initial_author_references=authors,
            initial_parent_work_id=parent_id,
            initial_parent_work_title=(
                parent_title or ''
            ),
        )
        self.page.show_dialog(modal)

    @staticmethod
    def _edit_form_values(
        work: WorkMixin,
        work_type: str,
    ) -> dict[str, object]:
        """Convert persisted model values back to form control values."""
        spec = next(item for item in WORK_TYPES if item.key == work_type)
        values: dict[str, object] = {}
        for column in sqlalchemy_inspect(work).mapper.column_attrs:
            key = column.key
            value = getattr(work, key)
            if key in {
                'id', 'bib_res_id', 'created_at', 'updated_at',
                'display_year',
            }:
                continue
            if key == 'date_precision':
                precision_labels = {
                    'exact': 'Data exata',
                    'decade': 'Década',
                    'century': 'Século',
                    'millenia': 'Milênio',
                    'unknown': 'Data desconhecida',
                }
                value = precision_labels[value.value]
            elif key in {'date_anchor'}:
                if (
                    value is None
                    or (
                        getattr(work, 'date_precision', None)
                        == DatePrecision.UNKNOWN
                    )
                ):
                    value = ''
                elif spec.date_kind == 'date':
                    value = value.strftime('%d/%m/%Y')
                elif spec.date_kind == 'month':
                    value = value.strftime('%m/%Y')
                else:
                    value = value.strftime('%Y')
            elif isinstance(value, (date, datetime)):
                value = value.strftime('%d/%m/%Y')
            elif isinstance(value, int) and not isinstance(value, bool):
                value = str(value)
            values[key] = value
        return values

    def handle_work_update(
        self,
        resource_id: int,
        form_data: dict[str, object],
    ) -> bool:
        """Validate and persist edits while retaining the resource identity."""
        missing_fields = (
            WorkSubmissionController._missing_required_fields(form_data)
        )
        if missing_fields:
            self.show_message(
                'Preencha os campos obrigatórios: '
                + ', '.join(missing_fields)
                + '.',
                COLORS['text'],
            )
            return False

        try:
            payload = self.form_service.prepare_payload(
                form_data,
                include_empty=True,
            )
            work_title = self.service.update(resource_id, payload)
        except (ValueError, TypeError) as error:
            log_exception("Dados inválidos ao editar uma obra", error)
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception("Falha ao editar uma obra", error)
            self.show_message(
                f'Não foi possível salvar as alterações.\n\n{error}',
                COLORS['text'],
            )
            return False

        self.navigate('Acervo')
        self.show_message(
            f'A obra “{work_title}” foi atualizada.',
            COLORS['gold'],
        )
        return True

    def open_parent_work(
        self,
        on_created: Callable[[int, str], None],
        work_type: str | None = None,
    ) -> None:
        """Abre um cadastro auxiliar e devolve a obra-pai recém-criada."""
        parent_modal: ft.AlertDialog | None = None

        def close_parent_modal() -> None:
            if parent_modal is not None:
                self.close_dialog(parent_modal)

        def save_parent(form_data: dict[str, object]) -> bool:
            return self.submission_controller.handle_work_submission(
                form_data,
                on_created=on_created,
                on_deferred_close=close_parent_modal,
            )

        parent_modal = CoreComposer.compose_work_insert_modal(
            page=self.page,
            config=self.view_config,
            on_save=save_parent,
            search_authors=self.search_authors,
            search_works=self.search_works,
            on_create_parent_work=self.open_parent_work,
            initial_work_type=work_type,
            parent_mode=True,
        )
        content = cast(ft.Container, parent_modal.content)
        content.opacity = 0.92
        content.scale = 0.96
        self.page.show_dialog(parent_modal)
        content.opacity = 1
        content.scale = 1
        parent_modal.update()

    async def copy_reference(self, reference: ViewReference) -> None:
        """Copia uma referencia formatada para a area de transferencia."""
        if not copy_reference_html(reference):
            await self.page.clipboard.set(
                "".join(part.content for part in reference.parts).strip()
            )
        self.show_message('Referência copiada.', COLORS['gold'])

    def delete_work(self, resource) -> None:
        """Remove uma obra do acervo e atualiza a listagem."""
        try:
            self.service.remove_work(resource)
        except Exception as error:
            log_exception("Falha ao excluir uma obra", error)
            self.show_message(
                f'Não foi possível excluir a obra.\n\n{error}', COLORS['text']
            )
            return

        self.navigate('Acervo')
        self.show_message('Obra excluída do acervo.', COLORS['gold'])

    def close_dialog(self, modal: ft.AlertDialog) -> None:
        modal.open = False
        self.page.update()

    def search_authors(self, query: str) -> list[AuthorSearchResult]:
        """Retorna autores existentes para a busca do modal."""
        return self.service.search_authors(query)

    def search_works(
        self,
        query: str,
        work_type: str | None = None,
    ) -> list[tuple[int, str]]:
        """Retorna obras encontradas para seletores relacionados."""
        return self.service.search_works(query, work_type)

    def close_insert_work(self) -> None:
        if self.work_insert_modal is not None:
            self.work_insert_modal.open = False
            self.page.update()

    def show_message(self, message: str, bgcolor: str) -> None:
        self.page.show_dialog(
            ft.SnackBar(
                content=ft.Text(value=message, color=COLORS['surface']),
                bgcolor=bgcolor,
            )
        )
