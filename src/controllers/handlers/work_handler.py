"""Handler para operações, formulários e estratégias de formatação de obras."""

from collections.abc import Callable
from datetime import date, datetime
from typing import cast
import flet as ft
from sqlalchemy import inspect as sqlalchemy_inspect

from src.contracts import AuthorSearchResult
from src.domains import (
    AcademicMonograph,
    AudioDocument,
    AudiovisualDocument,
    BibliographicResource,
    CartographicDocument,
    CaseLaw,
    CorrespondenceMonograph,
    DatePrecision,
    EditorialMonograph,
    JournalArticle,
    Magazine,
    MiscDigitalDocument,
    MonographicProceedings,
    MusicalScore,
    NewspaperArticle,
    Patent,
    PeriodicalCollection,
    PeriodicalProceedings,
    Statute,
    ThreeDimensionalDocument,
    VisualDocument,
    WorkMixin,
)
from src.strategies import (
    AudioFormatter,
    AudiovisualFormatter,
    CartographicFormatter,
    DigitalFormatter,
    LegalDocsFormatter,
    MonographFormatter,
    MusicalScoreFormatter,
    PatentFormatter,
    PeriodicalFormatter,
    ProceedingsFormatter,
    ThreeDimensionalFormatter,
    VisualFormatter,
)
from src.utils.clipboard import copy_reference as copy_reference_html
from src.utils.error_log import log_exception
from src.utils.types import ViewReference
from src.views.work_insert_specs import WORK_TYPES
from src.views.core_composer import CoreComposer
from src.controllers.work_submission_controller import WorkSubmissionController


class WorkControllerMixin:
    """Orquestra o ciclo de vida de cadastro, edição, exclusão e formatação ABNT de obras."""

    def open_insert_work(self) -> None:
        if self.work_insert_modal is not None:
            self.page.show_dialog(self.work_insert_modal)

    def open_work_details(self, resource) -> None:
        modal = CoreComposer.compose_work_details_popup(
            resource=resource,
            config=self.view_config,
            on_close=lambda: self.close_dialog(modal),
            page=self.page,
            nous_service=getattr(self, "nous_service", None),
        )
        self.page.show_dialog(modal)

    @staticmethod
    def format_reference(
        resource: BibliographicResource,
    ) -> ViewReference | None:
        """Select and run the reference strategy for a bibliographic work."""
        try:
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
            if isinstance(
                work, (MonographicProceedings, PeriodicalProceedings)
            ):
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
            if isinstance(work, Patent):
                return PatentFormatter.formatter(work)
            return None
        except Exception as error:
            log_exception(
                'Falha ao formatar referência do recurso '
                f'{getattr(resource, "id", "?")!r}',
                error,
            )
            return None

    def open_work_edit(
        self,
        resource,
        compilation_id: int | None = None,
    ) -> None:
        """Open a pre-populated form to edit the selected resource."""
        work = resource.specific_work
        if work is None:
            self.show_message(
                'A obra cadastrada não possui detalhes disponíveis.',
                self.view_config.colors['text'],
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
                self.view_config.colors['text'],
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
                resource.id,
                form_data,
                compilation_id=compilation_id,
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
        compilation_id: int | None = None,
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
                self.view_config.colors['text'],
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
            self.show_message(str(error), self.view_config.colors['text'])
            return False
        except Exception as error:
            log_exception("Falha ao editar uma obra", error)
            self.show_message(
                f'Não foi possível salvar as alterações.\n\n{error}',
                self.view_config.colors['text'],
            )
            return False

        if compilation_id is None:
            self.navigate('Acervo')
        else:
            self.refresh_compilation_hub(compilation_id)
        self.show_message(
            f'A obra “{work_title}” foi atualizada.',
            self.view_config.colors['gold'],
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
        self.show_message(
            'Referência copiada.', self.view_config.colors['gold']
        )

    def delete_work(self, resource) -> None:
        """Remove uma obra do acervo e atualiza a listagem."""
        try:
            self.service.remove_work(resource)
        except Exception as error:
            log_exception("Falha ao excluir uma obra", error)
            self.show_message(
                f'Não foi possível excluir a obra.\n\n{error}',
                self.view_config.colors['text']
            )
            return

        self.navigate('Acervo')
        self.show_message(
            'Obra excluída do acervo.', self.view_config.colors['gold']
        )

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
