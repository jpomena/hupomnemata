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
from src.db.db import SessionLocal
from src.domains import (
    AdministrativeAct,
    AudiovisualDocument,
    AudioDocument,
    CaseLaw,
    CartographicDocument,
    CorrespondenceMonograph,
    EditorialMonograph,
    JournalArticle,
    MiscellaneousDigitalDocument,
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
from src.repositories import WorkCreationPayload, WorkRepository
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
            with SessionLocal() as session:
                works = WorkRepository(session).list_works()
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
        self, on_created: Callable[[int, str], None]
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
        )
        self.page.show_dialog(parent_modal)

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
            with SessionLocal() as session:
                WorkRepository(session).remove_work(resource)
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

    def search_authors(self, query: str) -> list[str]:
        """Retorna autores existentes para a busca do modal."""
        with SessionLocal() as session:
            return WorkRepository(session).search_authors(query)

    def search_works(self, query: str) -> list[tuple[int, str]]:
        """Retorna obras encontradas para seletores relacionados."""
        with SessionLocal() as session:
            resources = WorkRepository(session).search_works(query)
        return [
            (resource.id, resource.specific_work.title)
            for resource in resources
            if resource.specific_work is not None
        ]

    def handle_work_submission(
        self,
        form_data: dict[str, object],
        on_created: Callable[[int, str], None] | None = None,
        on_deferred_close: Callable[[], None] | None = None,
    ) -> bool:
        """Normaliza a entrada e coordena sua persistência."""
        title = str(form_data.get('title', '')).strip()
        authors = str(form_data.get('authors', '')).strip()
        if not title or not authors:
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
            with SessionLocal() as session:
                repository = WorkRepository(session, self.normalizer)
                for index, author_name in enumerate(
                    self._pending_payload['author_names']
                ):
                    if (
                        index in self._pending_author_ids
                        or index in self._new_author_indexes
                    ):
                        continue
                    candidates = repository.find_possible_duplicate_authors(
                        author_name
                    )
                    if candidates:
                        self._show_multiple_authors_modal(index, candidates)
                        return False

                resource = repository.create(
                    self._pending_payload,
                    author_ids=self._pending_author_ids,
                )
                work = resource.specific_work
                if work is None:
                    raise ValueError('A obra cadastrada não possui detalhes.')
                created_work = (resource.id, work.title)
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

    def _show_multiple_authors_modal(self, index: int, candidates) -> None:
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
        model = self.work_model_for(str(form_data.get('work_type', '')))
        authors = str(form_data.get('authors', ''))
        date_precision = self.parse_date_precision(
            str(form_data.get('date_precision') or 'Data exata')
        )
        date_anchor = self.parse_date(
            str(form_data.get('date_anchor', '')),
            year_only=True,
            unknown=(
                str(form_data.get('date_precision', ''))
                == 'Data desconhecida'
            ),
        )
        if str(form_data.get('work_type', '')) in {
            'journal_article', 'newspaper_article'
        }:
            date_anchor = self.parse_date(
                str(form_data.get('date_anchor', '')),
                year_only=False,
            )

        converted = self.convert_model_values(form_data)
        if 'title' in converted:
            converted['title'] = self.normalizer.title_normalizer(
                str(converted['title'])
            )
        converted['date_anchor'] = date_anchor
        converted['date_precision'] = date_precision
        converted['display_year'] = self.normalizer.display_year_normalizer(
            date_precision, date_anchor
        )
        resource_keys = {
            'is_partial',
            'parent_work_id',
            'part_volume', 'part_chapter', 'part_start_page', 'part_end_page',
            'consult_start_year', 'consult_end_year',
        }
        resource_data = {
            key: converted[key]
            for key in resource_keys
            if key in converted
        }
        work_data = {
            key: value for key, value in converted.items()
            if key not in resource_keys
        }
        return {
            'work_model': model,
            'relationship_name': model.__tablename__.removesuffix('s'),
            'author_names': [
                name.strip()
                for name in authors.replace(',', ';').split(';')
                if name.strip()
            ],
            'resource_data': resource_data,
            'work_data': work_data,
        }

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
            'administrative_act': AdministrativeAct,
            'miscellaneous_digital_document': MiscellaneousDigitalDocument,
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
            'editorial_monograph',
            'audiovisual_document',
            'audio_document',
        }:
            result.setdefault('responsabilities', {})
        if form_data.get('work_type') == 'audio_document':
            result.setdefault('part_responsabilities', {})
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
