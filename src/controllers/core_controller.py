import flet as ft
from datetime import date, datetime
from collections.abc import Callable

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
    Author,
    AudiovisualDocument,
    AudioDocument,
    CaseLaw,
    CartographicDocument,
    CorrespondenceMonograph,
    EditorialMonograph,
    JournalArticle,
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
    AcademicMonograph,
    DatePrecision,
    WorkMixin,
)
from typing import cast

from src.repositories import (
    AuthorReference,
    AuthorSearchResult,
    WorkCreationPayload,
)
from src.services import WorkService
from src.strategies import CoreNormalizer
from src.utils.ft_responsiveness import Responsive
from src.views.application import ApplicationComposer
from src.views.page_config import PageConfigurator
from src.utils.types import ViewConfig
from src.utils.clipboard import copy_reference as copy_reference_html
from src.utils.types import ViewReference


class CoreController:
    """Orquestra o ciclo de vida e os fluxos principais da aplicação."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.work_insert_modal: ft.AlertDialog | None = None
        self._pending_payload: WorkCreationPayload | None = None
        self._pending_author_ids: dict[int, int] = {}
        self._new_author_indexes: set[int] = set()
        self._pending_on_created: Callable[[int, str], None] | None = None
        self._pending_on_deferred_close: Callable[[], None] | None = None
        self.normalizer = CoreNormalizer()
        self.service = WorkService(self.normalizer)
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
            ApplicationComposer.compose_work_insert_modal(
                page=self.page,
                config=self.view_config,
                on_save=self.handle_work_submission,
                search_authors=self.search_authors,
                search_works=self.search_works,
                on_create_parent_work=self.open_parent_work,
            )
        )
        self.multiple_authors_modal: ft.AlertDialog | None = None
        self.application = ApplicationComposer(
            page=self.page,
            scale=scale,
            config=self.view_config,
            on_navigate=self.navigate,
            on_work_click=self.open_work_details,
            on_copy_reference=self.copy_reference,
            on_delete_work=self.delete_work,
            on_create_parent_work=self.open_parent_work,
        )
        self.page.add(self.application.compose_main())

    def open_insert_work(self) -> None:
        if self.work_insert_modal is not None:
            self.page.show_dialog(self.work_insert_modal)

    def open_work_details(self, resource) -> None:
        modal = ApplicationComposer.compose_work_details_popup(
            resource=resource,
            config=self.view_config,
            on_close=lambda: self.close_dialog(modal),
        )
        self.page.show_dialog(modal)

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
            return self.handle_work_submission(
                form_data,
                on_created=on_created,
                on_deferred_close=close_parent_modal,
            )

        parent_modal = ApplicationComposer.compose_work_insert_modal(
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

    def search_works(self, query: str) -> list[tuple[int, str]]:
        """Retorna obras encontradas para seletores relacionados."""
        return self.service.search_works(query)

    def handle_work_submission(
        self,
        form_data: dict[str, object],
        on_created: Callable[[int, str], None] | None = None,
        on_deferred_close: Callable[[], None] | None = None,
    ) -> bool:
        """Normaliza a entrada e coordena sua persistência."""
        title = str(form_data.get('title', '')).strip()
        authors = form_data.get('authors', [])
        if not title or not self._author_references(authors):
            self.show_message(
                'Os campos Título e Autor são obrigatórios!',
                COLORS['text'],
            )
            return False

        try:
            self._pending_payload = self.prepare_work_payload(form_data)
            self._pending_author_ids.clear()
            self._new_author_indexes.clear()
            self._pending_on_created = on_created
            self._pending_on_deferred_close = on_deferred_close
            return self._continue_pending_submission(close_form=False)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as e:
            self.show_message(
                f'Não foi possível salvar a obra.\n\n{e} ', COLORS['text']
            )
            return False

    def _continue_pending_submission(self, close_form: bool) -> bool:
        """Resolve autores semelhantes um por vez e persiste no fim."""
        if self._pending_payload is None:
            return False

        created_work: tuple[int, str] | None = None
        try:
            result = self.service.resolve_and_create(
                self._pending_payload,
                author_ids=self._pending_author_ids,
                new_author_indexes=self._new_author_indexes,
            )
            if result.get('requires_choice') is True:
                choice_result = cast(
                    dict[str, object],
                    result,
                )
                choice_index = choice_result['index']
                choice_candidates = choice_result['candidates']
                if not isinstance(choice_index, int):
                    choice_index = int(str(choice_index))
                if not isinstance(choice_candidates, list):
                    raise TypeError('Lista de autores duplicados inválida.')
                authors_candidates = [
                    candidate
                    for candidate in choice_candidates
                    if isinstance(candidate, Author)
                ]
                self._show_multiple_authors_modal(
                    choice_index,
                    authors_candidates,
                )
                return False

            created_result = cast(dict[str, object], result)
            resource_id = created_result['resource_id']
            work_title = created_result['work_title']
            if not isinstance(resource_id, int):
                resource_id = int(str(resource_id))
            if not isinstance(work_title, str):
                work_title = str(work_title)
            created_work = (resource_id, work_title)
        except (ValueError, TypeError) as error:
            self._clear_pending_submission()
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception as error:
            self._clear_pending_submission()
            self.show_message(
                f'Não foi possível salvar a obra.\n\n{error}', COLORS['text']
            )
            return False

        on_created = self._pending_on_created
        on_deferred_close = self._pending_on_deferred_close
        self._clear_pending_submission()
        if close_form:
            if on_deferred_close is not None:
                on_deferred_close()
            else:
                self.close_insert_work()
        if created_work is not None and on_created is not None:
            on_created(*created_work)
        self.show_message('Obra adicionada ao acervo.', COLORS['gold'])
        return True

    def _show_multiple_authors_modal(
        self, index: int, candidates: list[Author]
    ) -> None:
        self.multiple_authors_modal = (
            ApplicationComposer.compose_multiple_authors_modal(
                authors=candidates,
                on_select=lambda author_id: self._select_existing_author(
                    index, author_id
                ),
                on_create_new=lambda: self._create_new_author(index),
                on_cancel=self._clear_pending_submission,
                config=self.view_config
            )
        )
        self.page.show_dialog(self.multiple_authors_modal)

    def _select_existing_author(self, index: int, author_id: int) -> None:
        self._pending_author_ids[index] = author_id
        self._continue_pending_submission(close_form=True)

    def _create_new_author(self, index: int) -> None:
        self._new_author_indexes.add(index)
        self._continue_pending_submission(close_form=True)

    def _clear_pending_submission(self) -> None:
        self._pending_payload = None
        self._pending_author_ids.clear()
        self._new_author_indexes.clear()
        self._pending_on_created = None
        self._pending_on_deferred_close = None

    def prepare_work_payload(
        self, form_data: dict[str, object]
    ) -> WorkCreationPayload:
        model = self.service.work_model_for(
            str(form_data.get('work_type', ''))
        )
        authors = form_data.get('authors', [])
        date_precision = self.service.parse_date_precision(
            str(form_data.get('date_precision') or 'Data exata')
        )
        form_data = dict(form_data)
        raw_date_anchor = str(form_data.get('date_anchor', '')).strip()
        work_type = str(form_data.get('work_type', ''))
        if work_type == 'statute':
            raw_promulgation = str(
                form_data.get('promulgation_date', '')
            ).strip()
            if not raw_promulgation and raw_date_anchor:
                form_data['promulgation_date'] = raw_date_anchor
        elif work_type == 'caselaw':
            raw_decision = str(form_data.get('decision_date', '')).strip()
            if not raw_decision and raw_date_anchor:
                form_data['decision_date'] = raw_date_anchor

        complete_date = (
            '/' in raw_date_anchor
            or work_type in {
                'journal_article', 'newspaper_article', 'statute', 'caselaw'
            }
        )
        date_anchor = self.service.parse_date(
            raw_date_anchor,
            year_only=not complete_date,
            unknown=(
                str(form_data.get('date_precision', ''))
                == 'Data desconhecida'
            ),
        )
        converted = self.service.convert_model_values(form_data)
        if 'title' in converted:
            converted['title'] = self.normalizer.title_normalizer(
                str(converted['title'])
            )
        converted['date_anchor'] = date_anchor
        converted['date_precision'] = date_precision
        converted['display_year'] = self.normalizer.display_year_normalizer(
            date_precision, date_anchor
        )
        partial_keys = {
            'part_volume', 'part_chapter', 'part_start_page', 'part_end_page',
            'consult_start_year', 'consult_end_year',
            'is_partial', 'parent_bibliographic_resource_id',
        }
        resource_data = {}
        work_data = {
            key: value for key, value in converted.items()
            if key not in partial_keys
        }
        work_data.update({
            key: converted[key]
            for key in partial_keys
            if key in converted
        })
        return {
            'work_model': model,
            'relationship_name': model.__tablename__.removesuffix('s'),
            'author_names': cast(
                list[AuthorReference],
                self.service.author_references(authors),
            ),
            'resource_data': resource_data,
            'work_data': work_data,
        }

    @staticmethod
    def _author_references(value: object) -> list[AuthorReference]:
        if isinstance(value, list):
            references: list[AuthorReference] = []
            for item in value:
                if isinstance(item, dict):
                    name = str(item.get('name', '')).strip()
                    if name:
                        references.append({
                            'name': name,
                            'id': (
                                int(item['id'])
                                if item.get('id') is not None else None
                            ),
                            'corporation': bool(
                                item.get('corporation', False)
                            ),
                            'acronym': (
                                str(item['acronym']).strip().upper()
                                if item.get('acronym') else None
                            ),
                            'jurisdiction_id': (
                                int(item['jurisdiction_id'])
                                if item.get('jurisdiction_id') is not None
                                else None
                            ),
                            'jurisdiction_name': (
                                str(item['jurisdiction_name']).strip()
                                if item.get('jurisdiction_name')
                                else None
                            ),
                        })
                elif str(item).strip():
                    references.append({
                        'name': str(item).strip(),
                        'id': None,
                        'corporation': False,
                        'acronym': None,
                        'jurisdiction_id': None,
                        'jurisdiction_name': None,
                    })
            return references

        return [
            {
                'name': name.strip(),
                'id': None,
                'corporation': False,
                'acronym': None,
                'jurisdiction_id': None,
                'jurisdiction_name': None,
            }
            for name in str(value).replace(',', ';').split(';')
            if name.strip()
        ]

    @staticmethod
    def work_model_for(work_type: str) -> type[WorkMixin]:
        models: dict[str, type[WorkMixin]] = {
            'editorial_monograph': EditorialMonograph,
            'academic_monograph': AcademicMonograph,
            'correspondence_monograph': CorrespondenceMonograph,
            'periodical_collection': PeriodicalCollection,
            'journal_article': JournalArticle,
            'newspaper_article': NewspaperArticle,
            'monographic_proceedings': MonographicProceedings,
            'periodical_proceedings': PeriodicalProceedings,
            'patent': Patent,
            'statute': Statute,
            'caselaw': CaseLaw,
            'miscellaneous_digital_document': MiscDigitalDocument,
            'audiovisual_document': AudiovisualDocument,
            'audio_document': AudioDocument,
            'musical_score': MusicalScore,
            'visual_document': VisualDocument,
            'cartographic_document': CartographicDocument,
            'three_dimensional_document': ThreeDimensionalDocument,
        }
        try:
            return models[work_type]
        except KeyError as error:
            raise ValueError('Tipo de obra inválido.') from error

    @staticmethod
    def parse_date(
        value: str,
        year_only: bool,
        unknown: bool = False,
    ) -> date:
        if unknown and not value.strip():
            return date(1, 1, 1)
        try:
            if year_only:
                return date(int(value), 1, 1)
            return datetime.strptime(value, '%d/%m/%Y').date()
        except (TypeError, ValueError) as error:
            expected = 'AAAA' if year_only else 'DD/MM/AAAA'
            raise ValueError(
                f'Informe a data no formato {expected}.'
            ) from error

    @staticmethod
    def parse_date_precision(value: str) -> DatePrecision:
        options = {
            'Data exata': DatePrecision.EXACT,
            'Década': DatePrecision.DECADE,
            'Século': DatePrecision.CENTURY,
            'Milênio': DatePrecision.MILLENIA,
            'Data desconhecida': DatePrecision.UNKNOWN,
        }
        try:
            return options[value]
        except KeyError as error:
            raise ValueError('Precisão de data inválida.') from error

    @staticmethod
    def convert_model_values(
        form_data: dict[str, object]
    ) -> dict[str, object]:
        numeric_fields = {
            'consult_start_year', 'consult_end_year',
            'edition', 'page_quantity', 'volumes', 'collection_number',
            'first_volume_year', 'last_volume_year', 'volume', 'year_season',
            'number', 'event_number', 'event_year', 'publication_year',
            'vol_or_year', 'version', 'seconds', 'defense_year',
        }
        date_fields = {
            'viewed_at', 'publication_date', 'filing_date', 'grant_date',
            'decision_date',
        }
        result = {}
        for key, value in form_data.items():
            if key in {
                'work_type', 'authors', 'date_precision', 'date_anchor'
            }:
                continue
            if value in ('', None):
                continue
            if key in numeric_fields:
                result[key] = int(str(value))
            elif key in date_fields:
                result[key] = datetime.strptime(
                    str(value), '%d/%m/%Y'
                ).date()
            else:
                result[key] = value
        if form_data.get('work_type') in {
            'audiovisual_document',
            'audio_document',
        }:
            result.setdefault('responsibilities', {})
        if form_data.get('work_type') == 'audio_document':
            result.setdefault('part_responsibilities', {})
        return result

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
