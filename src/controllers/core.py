import flet as ft
from datetime import date, datetime

import src.domains  # noqa: F401
from src.configs.settings import (
    COLORS,
    CORE_MENUS,
    FONTS,
    FONT_SIZE,
    FONT_WEIGHT,
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
from src.views.view_config import ViewConfig


class CoreController:
    """Orquestra o ciclo de vida e os fluxos principais da aplicação."""

    def __init__(self, page: ft.Page):
        self.page = page
        self.work_insert_modal: ft.AlertDialog | None = None
        self.normalizer = CoreNormalizer()
        self.view_config = ViewConfig(
            colors=COLORS,
            fonts=FONTS,
            page_fonts=PAGE_FONTS,
            font_size=FONT_SIZE,
            font_weight=FONT_WEIGHT,
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

    def build_application(self) -> None:
        scale = Responsive.get_scale(self.page)
        self.work_insert_modal = (
            ApplicationComposer.compose_work_insert_modal(
                page=self.page,
                config=self.view_config,
                on_save=self.handle_work_submission
            )
        )
        self.page.add(
            ApplicationComposer(
                scale=scale,
                config=self.view_config,
                on_insert_work=self.open_insert_work,
            ).compose_main()
        )

    def open_insert_work(self) -> None:
        if self.work_insert_modal is not None:
            self.page.show_dialog(self.work_insert_modal)

    def handle_work_submission(self, form_data: dict[str, object]) -> bool:
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
            payload = self.prepare_work_payload(form_data)
            with SessionLocal() as session:
                WorkRepository(session, self.normalizer).create(payload)
        except (ValueError, TypeError) as error:
            self.show_message(str(error), COLORS['text'])
            return False
        except Exception:
            self.show_message(
                'Não foi possível salvar a obra.', COLORS['text']
            )
            return False

        self.close_insert_work()
        self.show_message('Obra adicionada ao acervo.', COLORS['gold'])
        return True

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
        converted['date_anchor'] = date_anchor
        converted['date_precision'] = date_precision
        converted['display_year'] = self.normalizer.display_year_normalizer(
            date_precision, date_anchor
        )
        resource_keys = {
            'is_partial',
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
