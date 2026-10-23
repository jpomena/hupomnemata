import flet as ft
from datetime import date, datetime
from collections.abc import Callable
from sqlalchemy import inspect as sqlalchemy_inspect

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

from src.contracts import (
    AuthorSearchResult,
    CompilationPayload,
    FragmentRecord,
)
from src.services import CompilationService, FragmentService, WorkService
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
from src.views.fragments import FragmentsComposer
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
        self.fragment_service = FragmentService()
        self.compilation_service = CompilationService()
        self.compilation_fragment_composer = None
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
            fragments = self.fragment_service.list_fragments()
            self.application.show_view(
                "Fragmentos",
                fragments=fragments,
            )
        if destination == "Compilações":
            compilations = self.compilation_service.list_compilations()
            self.application.show_view(
                "Compilações",
                compilations=compilations,
            )
        if destination in {
            "Nous",
            "Configurações",
            "Limbo",
            "Estruturas de Saber",
        }:
            self.application.show_view(destination)

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

        if compilation_id is None:
            self.navigate('Acervo')
        else:
            self.refresh_compilation_hub(compilation_id)
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

    def save_fragment(
        self,
        fragment_id: int | None,
        data: dict[str, object],
    ) -> bool:
        try:
            if fragment_id is None:
                self.fragment_service.create(data)
                message = 'Fragmento cadastrado.'
            else:
                self.fragment_service.update(fragment_id, data)
                message = 'Fragmento atualizado.'
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao salvar fragmento', error)
            self.show_message(
                f'Não foi possível salvar o fragmento.\n\n{error}',
                COLORS['text'],
            )
            return False

        self.navigate('Fragmentos')
        self.show_message(message, COLORS['gold'])
        return True

    def save_compilation_fragment(
        self,
        compilation_id: int,
        fragment_id: int | None,
        data: dict[str, object],
    ) -> bool:
        try:
            payload = self.fragment_service._payload(data)
            if fragment_id is None:
                self.compilation_service.create_fragment(
                    compilation_id,
                    payload,
                )
                message = 'Fragmento cadastrado na compilação.'
            else:
                if not self.compilation_service.contains_work(
                    compilation_id,
                    payload['bib_res_id'],
                ):
                    raise ValueError(
                        'A obra do fragmento deve pertencer à compilação.'
                    )
                self.fragment_service.update(fragment_id, payload)
                message = 'Fragmento atualizado.'
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception(
                'Falha ao salvar fragmento pela compilação',
                error,
            )
            self.show_message(
                f'Não foi possível salvar o fragmento.\n\n{error}',
                COLORS['text'],
            )
            return False

        self.refresh_compilation_hub(compilation_id)
        self.show_message(message, COLORS['gold'])
        return True

    def delete_fragment(self, fragment_id: int) -> None:
        try:
            self.fragment_service.delete(fragment_id)
        except Exception as error:
            log_exception('Falha ao excluir fragmento', error)
            self.show_message(
                f'Não foi possível excluir o fragmento.\n\n{error}',
                COLORS['text'],
            )
            return

        self.navigate('Fragmentos')
        self.show_message('Fragmento excluído.', COLORS['gold'])

    def search_fragment_works(self, query: str) -> list[tuple[int, str]]:
        try:
            return self.service.search_works(query, include_partial=True)
        except Exception as error:
            log_exception('Falha ao buscar obras para fragmentos', error)
            self.show_message(
                f'Não foi possível buscar obras no Acervo.\n\n{error}',
                COLORS['text'],
            )
            return []

    def search_compilation_works(
        self,
        query: str,
    ) -> list[tuple[int, str]]:
        try:
            return self.service.search_works(query, include_partial=True)
        except Exception as error:
            log_exception('Falha ao buscar obras para compilações', error)
            self.show_message(
                f'Não foi possível buscar obras no Acervo.\n\n{error}',
                COLORS['text'],
            )
            return []

    def create_compilation(
        self,
        payload: CompilationPayload,
    ) -> int | None:
        try:
            compilation_id = self.compilation_service.create(payload)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return None
        except Exception as error:
            log_exception('Falha ao criar compilação', error)
            self.show_message(
                f'Não foi possível criar a compilação.\n\n{error}',
                COLORS['text'],
            )
            return None

        self.show_message('Compilação criada.', COLORS['gold'])
        return compilation_id

    def update_compilation(
        self,
        compilation_id: int,
        payload: CompilationPayload,
    ) -> bool:
        try:
            self.compilation_service.update(compilation_id, payload)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao atualizar compilação', error)
            self.show_message(
                f'Não foi possível atualizar a compilação.\n\n{error}',
                COLORS['text'],
            )
            return False

        self.show_message('Compilação atualizada.', COLORS['gold'])
        return True

    def delete_compilation(self, compilation_id: int) -> bool:
        try:
            self.compilation_service.delete(compilation_id)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao excluir compilação', error)
            self.show_message(
                f'Não foi possível excluir a compilação.\n\n{error}',
                COLORS['text'],
            )
            return False

        self.show_message('Compilação excluída.', COLORS['gold'])
        return True

    def add_work_to_compilation(
        self,
        compilation_id: int,
        bib_res_id: int,
    ) -> bool:
        try:
            self.compilation_service.add_work(compilation_id, bib_res_id)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao adicionar obra à compilação', error)
            self.show_message(
                f'Não foi possível adicionar a obra.\n\n{error}',
                COLORS['text'],
            )
            return False

        self.show_message('Obra adicionada à compilação.', COLORS['gold'])
        return True

    def remove_work_from_compilation(
        self,
        compilation_id: int,
        bib_res_id: int,
    ) -> bool:
        try:
            self.compilation_service.remove_work(compilation_id, bib_res_id)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao remover obra da compilação', error)
            self.show_message(
                f'Não foi possível remover a obra.\n\n{error}',
                COLORS['text'],
            )
            return False

        self.show_message('Obra removida da compilação.', COLORS['gold'])
        return True

    def reorder_compilation_works(
        self,
        compilation_id: int,
        ordered_resource_ids: list[int],
    ) -> bool:
        try:
            self.compilation_service.reorder_works(
                compilation_id,
                ordered_resource_ids,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao ordenar obras da compilação', error)
            self.show_message(
                f'Não foi possível ordenar as obras.\n\n{error}',
                COLORS['text'],
            )
            return False

        return True

    def set_compilation_fragment_membership(
        self,
        compilation_id: int,
        fragment_id: int,
        selected: bool,
    ) -> bool:
        try:
            if selected:
                self.compilation_service.add_fragment(
                    compilation_id,
                    fragment_id,
                )
            else:
                self.compilation_service.remove_fragment(
                    compilation_id,
                    fragment_id,
                )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception(
                'Falha ao atualizar vínculo de fragmento da compilação',
                error,
            )
            self.show_message(
                f'Não foi possível atualizar o fragmento.\n\n{error}',
                COLORS['text'],
            )
            return False

        return True

    def update_compilation_fragment_note(
        self,
        compilation_id: int,
        fragment_id: int,
        note: str | None,
    ) -> bool:
        try:
            self.compilation_service.update_fragment_note(
                compilation_id,
                fragment_id,
                note,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception(
                'Falha ao salvar nota do fragmento no caderno',
                error,
            )
            self.show_message(
                f'Não foi possível salvar a nota.\n\n{error}',
                COLORS['text'],
            )
            return False
        return True

    def create_compilation_section(
        self,
        compilation_id: int,
        title: str,
        central_idea: str | None,
    ) -> int | None:
        try:
            section_id = self.compilation_service.create_section(
                compilation_id,
                title,
                central_idea,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return None
        except Exception as error:
            log_exception('Falha ao criar seção do caderno', error)
            self.show_message(
                f'Não foi possível criar a seção.\n\n{error}',
                COLORS['text'],
            )
            return None
        return section_id

    def update_compilation_section(
        self,
        compilation_id: int,
        section_id: int,
        title: str,
        central_idea: str | None,
    ) -> bool:
        try:
            self.compilation_service.update_section(
                compilation_id,
                section_id,
                title,
                central_idea,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao atualizar seção do caderno', error)
            self.show_message(
                f'Não foi possível atualizar a seção.\n\n{error}',
                COLORS['text'],
            )
            return False
        return True

    def delete_compilation_section(
        self,
        compilation_id: int,
        section_id: int,
    ) -> bool:
        try:
            self.compilation_service.delete_section(compilation_id, section_id)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao remover seção do caderno', error)
            self.show_message(
                f'Não foi possível remover a seção.\n\n{error}',
                COLORS['text'],
            )
            return False
        return True

    def reorder_compilation_sections(
        self,
        compilation_id: int,
        section_ids: list[int],
    ) -> bool:
        try:
            self.compilation_service.reorder_sections(
                compilation_id,
                section_ids,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao ordenar seções do caderno', error)
            self.show_message(
                f'Não foi possível ordenar as seções.\n\n{error}',
                COLORS['text'],
            )
            return False
        return True

    def assign_compilation_fragment_to_section(
        self,
        compilation_id: int,
        fragment_id: int,
        section_id: int | None,
    ) -> bool:
        try:
            self.compilation_service.assign_fragment_to_section(
                compilation_id,
                fragment_id,
                section_id,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao mover fragmento entre seções', error)
            self.show_message(
                f'Não foi possível mover o fragmento.\n\n{error}',
                COLORS['text'],
            )
            return False
        return True

    def reorder_compilation_section_fragments(
        self,
        compilation_id: int,
        section_id: int,
        fragment_ids: list[int],
    ) -> bool:
        try:
            self.compilation_service.reorder_section_fragments(
                compilation_id,
                section_id,
                fragment_ids,
            )
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            log_exception('Falha ao ordenar fragmentos na seção', error)
            self.show_message(
                f'Não foi possível ordenar os fragmentos.\n\n{error}',
                COLORS['text'],
            )
            return False
        return True

    async def copy_compilation_caderno(self, text: str) -> None:
        try:
            await self.page.clipboard.set(text)
        except Exception as error:
            log_exception('Falha ao copiar caderno de trabalho', error)
            self.show_message(
                f'Não foi possível copiar o caderno.\n\n{error}',
                COLORS['text'],
            )
            return
        self.show_message('Caderno copiado.', COLORS['gold'])

    def open_compilation_work_insert(self, compilation_id: int) -> None:
        def add_created_work(resource_id: int, title: str) -> None:
            del title
            self._add_created_compilation_work(compilation_id, resource_id)

        modal = CoreComposer.compose_work_insert_modal(
            page=self.page,
            config=self.view_config,
            on_save=lambda form_data: (
                self.submission_controller.handle_work_submission(
                    form_data,
                    on_created=add_created_work,
                )
            ),
            search_authors=self.search_authors,
            search_works=self.search_works,
            on_create_parent_work=self.open_parent_work,
        )
        self.page.show_dialog(modal)

    def _add_created_compilation_work(
        self,
        compilation_id: int,
        resource_id: int,
    ) -> None:
        if self.add_work_to_compilation(compilation_id, resource_id):
            self.refresh_compilation_hub(compilation_id)

    def open_compilation_work_edit(
        self,
        compilation_id: int,
        resource_id: int,
    ) -> None:
        resource = next(
            (
                work
                for work in self.service.list_works()
                if work.id == resource_id
            ),
            None,
        )
        if resource is None:
            self.show_message(
                'A obra da compilação não está mais disponível.',
                COLORS['text'],
            )
            return
        self.open_work_edit(resource, compilation_id=compilation_id)

    def _compilation_work_options(
        self,
        compilation_id: int,
    ) -> list[tuple[int, str]]:
        compilation = next(
            (
                record
                for record in self.compilation_service.list_compilations()
                if record['id'] == compilation_id
            ),
            None,
        )
        if compilation is None:
            raise ValueError('A compilação não está mais disponível.')
        return [
            (work['id'], work['title'])
            for work in compilation['works']
        ]

    def _open_compilation_fragment_composer(
        self,
        compilation_id: int,
    ):
        work_options = self._compilation_work_options(compilation_id)
        allowed_work_ids = {resource_id for resource_id, _ in work_options}

        def search_allowed_works(query: str) -> list[tuple[int, str]]:
            return [
                match
                for match in self.search_fragment_works(query)
                if match[0] in allowed_work_ids
            ]

        composer = FragmentsComposer(
            page=self.page,
            config=self.view_config,
            fragments=[],
            search_works=search_allowed_works,
            on_save=lambda fragment_id, data: (
                self.save_compilation_fragment(
                    compilation_id,
                    fragment_id,
                    data,
                )
            ),
            on_delete=self.delete_fragment,
            on_copy_reference=self.copy_reference,
            allowed_work_ids=allowed_work_ids,
        )
        self.compilation_fragment_composer = composer
        return composer, work_options

    def open_compilation_fragment_create(
        self,
        compilation_id: int,
        resource_id: int,
    ) -> None:
        composer, work_options = self._open_compilation_fragment_composer(
            compilation_id
        )
        title = next(
            (
                title
                for option_id, title in work_options
                if option_id == resource_id
            ),
            None,
        )
        if title is None:
            self.show_message(
                'Inclua a obra na compilação antes de criar um fragmento.',
                COLORS['text'],
            )
            return
        composer.open_create_for_work(resource_id, title)

    def open_compilation_fragment_edit(
        self,
        compilation_id: int,
        fragment: FragmentRecord,
    ) -> None:
        composer = self._open_compilation_fragment_composer(
            compilation_id
        )[0]
        composer.open_edit_fragment(fragment)

    def refresh_compilation_hub(self, compilation_id: int) -> None:
        application = getattr(self, 'application', None)
        if application is not None:
            application.refresh_compilation_hub(compilation_id)

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
