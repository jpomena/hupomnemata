from datetime import date, datetime
from typing import Literal, TypedDict

from src.db.db import SessionLocal
from src.domains import (
    AcademicMonograph,
    AudiovisualDocument,
    Author,
    AudioDocument,
    CaseLaw,
    CartographicDocument,
    CorrespondenceMonograph,
    DatePrecision,
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
    WorkMixin,
)
from src.repositories import (
    AuthorReference,
    WorkCreationPayload,
    WorkRepository,
)
from src.strategies import CoreNormalizer


class RequiresChoiceResult(TypedDict):
    requires_choice: Literal[True]
    index: int
    candidates: list[Author]


class CreatedResourceResult(TypedDict):
    requires_choice: Literal[False]
    resource_id: int
    work_title: str


class WorkService:
    """Centraliza regras de negócio de criação, busca e validação de obras."""

    def __init__(self, normalizer: CoreNormalizer | None = None):
        self.normalizer = normalizer or CoreNormalizer()

    def create(
        self,
        payload: WorkCreationPayload,
        author_ids: dict[int, int] | None = None,
    ):
        with SessionLocal() as session:
            return WorkRepository(session, self.normalizer).create(
                payload,
                author_ids=author_ids,
            )

    def search_authors(self, query: str):
        with SessionLocal() as session:
            return WorkRepository(session, self.normalizer).search_authors(
                query
            )

    def search_works(self, query: str):
        with SessionLocal() as session:
            resources = WorkRepository(session, self.normalizer).search_works(
                query
            )
        return [
            (resource.id, resource.specific_work.title)
            for resource in resources
            if resource.specific_work is not None
        ]

    def list_works(self):
        with SessionLocal() as session:
            return WorkRepository(session, self.normalizer).list_works()

    def remove_work(self, resource):
        with SessionLocal() as session:
            WorkRepository(session, self.normalizer).remove_work(resource)

    def resolve_and_create(
        self,
        payload: WorkCreationPayload,
        author_ids: dict[int, int] | None = None,
        new_author_indexes: set[int] | None = None,
    ) -> RequiresChoiceResult | CreatedResourceResult:
        with SessionLocal() as session:
            repository = WorkRepository(session, self.normalizer)
            pending_author_ids = author_ids or {}
            pending_new_author_indexes = new_author_indexes or set()

            author_names: list[AuthorReference] = payload['author_names']
            for index, author_reference in enumerate(author_names):
                if (
                    index in pending_author_ids
                    or index in pending_new_author_indexes
                ):
                    continue
                if author_reference['id'] is not None:
                    continue
                candidates = repository.find_possible_duplicate_authors(
                    author_reference['name']
                )
                if candidates:
                    return {
                        'requires_choice': True,
                        'index': index,
                        'candidates': candidates,
                    }

            resource = repository.create(
                payload,
                author_ids=pending_author_ids,
            )
            work = resource.specific_work
            if work is None:
                raise ValueError('A obra cadastrada não possui detalhes.')
            return {
                'requires_choice': False,
                'resource_id': resource.id,
                'work_title': work.title,
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
    def parse_date(value: str, year_only: bool, unknown: bool = False) -> date:
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
            'publication_number', 'vol_or_year', 'version', 'seconds',
            'defense_year',
        }
        date_fields = {
            'viewed_at', 'filing_date', 'grant_date',
            'decision_date', 'promulgation_date',
        }
        result = {}
        for key, value in form_data.items():
            if key in {
                'work_type',
                'authors',
                'date_precision',
                'date_anchor',
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

    @staticmethod
    def author_references(value: object):
        if isinstance(value, list):
            references = []
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
