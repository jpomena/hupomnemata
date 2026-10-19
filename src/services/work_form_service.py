import re
from datetime import date, datetime

from src.domains import (
    AcademicMonograph,
    AudiovisualDocument,
    AudioDocument,
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
from src.contracts import AuthorReference, WorkCreationPayload
from src.utils.error_log import log_exception
from src.utils.normalizers import CoreNormalizer


class WorkFormService:
    """
    Converts and validates form values before they enter the work service.
    """

    PARTIAL_KEYS = {
        'part_volume',
        'part_chapter',
        'part_start_page',
        'part_end_page',
        'consult_start_year',
        'consult_end_year',
        'is_partial',
        'parent_bibliographic_resource_id',
    }
    MULTIMEDIA_WORK_TYPES = {
        'audiovisual_document',
        'audio_document',
        'musical_score',
        'visual_document',
        'cartographic_document',
        'three_dimensional_document',
    }
    PARTIAL_DATE_INHERITED_TYPES = {
        'editorial_monograph',
        'academic_monograph',
        'correspondence_monograph',
        'monographic_proceedings',
        'periodical_proceedings',
        'audio_document',
        'musical_score',
    }

    def __init__(self, normalizer: CoreNormalizer | None = None) -> None:
        self.normalizer = normalizer or CoreNormalizer()

    def prepare_payload(
        self,
        form_data: dict[str, object],
        include_empty: bool = False,
    ) -> WorkCreationPayload:
        work_type = str(form_data.get('work_type', ''))
        model = self.work_model_for(work_type)
        raw_values = dict(form_data)
        raw_date_anchor = str(raw_values.get('date_anchor', '')).strip()
        if (
            work_type == 'periodical_collection'
            and not raw_date_anchor
        ):
            raw_date_anchor = str(
                raw_values.get('first_volume_year', '')
            ).strip()
        elif work_type == 'periodical_proceedings' and not raw_date_anchor:
            raw_date_anchor = str(
                raw_values.get('publication_date', '')
            ).strip()
        precision_label = str(
            raw_values.get('date_precision') or 'Data exata'
        )
        partial_without_date = (
            work_type in self.PARTIAL_DATE_INHERITED_TYPES
            and bool(raw_values.get('is_partial'))
            and not raw_date_anchor
        )
        precision = (
            DatePrecision.UNKNOWN
            if partial_without_date
            else self.parse_date_precision(precision_label)
        )
        multimedia_display_year = None
        if work_type in {'journal_article', 'periodical_collection'}:
            raw_values['is_partial'] = True

        if work_type == 'statute':
            promulgation_date = str(
                raw_values.get('promulgation_date', '')
            ).strip()
            if not promulgation_date and raw_date_anchor:
                raw_values['promulgation_date'] = raw_date_anchor
        elif work_type == 'caselaw':
            decision_date = str(
                raw_values.get('decision_date', '')
            ).strip()
            if not decision_date and raw_date_anchor:
                raw_values['decision_date'] = raw_date_anchor

        full_date_types = {
            'journal_article',
            'newspaper_article',
            'statute',
            'caselaw',
        }
        if work_type != 'magazine':
            if partial_without_date:
                date_anchor = date(1, 1, 1)
            elif work_type in self.MULTIMEDIA_WORK_TYPES:
                (
                    date_anchor,
                    precision,
                    multimedia_display_year,
                ) = self.parse_multimedia_publication_year(
                    raw_date_anchor
                )
            elif work_type == 'journal_article':
                date_anchor = self.parse_month_date(
                    raw_date_anchor,
                    unknown=precision_label == 'Data desconhecida',
                )
            else:
                date_anchor = self.parse_date(
                    raw_date_anchor,
                    year_only=(
                        '/' not in raw_date_anchor
                        and work_type not in full_date_types
                    ),
                    unknown=precision_label == 'Data desconhecida',
                )
        converted = self.convert_model_values(
            raw_values,
            include_empty=include_empty,
        )
        if work_type == 'visual_document' and not str(
            converted.get('title') or ''
        ).strip():
            converted['title'] = '[Sem título]'
        if 'title' in converted:
            converted['title'] = self.normalizer.title_normalizer(
                str(converted['title'])
            )
        if work_type != 'magazine':
            converted['date_anchor'] = date_anchor
            converted['date_precision'] = precision
            converted['display_year'] = (
                self.normalizer.display_year_normalizer(
                    precision, date_anchor
                )
            )
            if multimedia_display_year is not None:
                converted['display_year'] = multimedia_display_year
            if work_type == 'monographic_proceedings':
                converted['publication_year'] = date_anchor.year
            elif (
                work_type == 'periodical_proceedings'
                and isinstance(converted.get('publication_date'), date)
            ):
                converted['publication_year'] = converted[
                    'publication_date'
                ].year

        work_data = {
            key: value
            for key, value in converted.items()
            if key not in self.PARTIAL_KEYS
        }
        work_data.update({
            key: converted[key]
            for key in self.PARTIAL_KEYS
            if key in converted
        })
        return {
            'work_model': model,
            'relationship_name': model.__tablename__.removesuffix('s'),
            'author_names': self.author_references(
                raw_values.get('authors', [])
            ),
            'resource_data': {},
            'work_data': work_data,
        }

    @staticmethod
    def author_references(value: object) -> list[AuthorReference]:
        references: list[AuthorReference] = []
        if isinstance(value, list):
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
                    references.append(
                        WorkFormService._simple_author_reference(
                            str(item).strip()
                        )
                    )
            return references

        return [
            WorkFormService._simple_author_reference(name.strip())
            for name in str(value).replace(',', ';').split(';')
            if name.strip()
        ]

    @staticmethod
    def _simple_author_reference(name: str) -> AuthorReference:
        return {
            'name': name,
            'id': None,
            'corporation': False,
            'acronym': None,
            'jurisdiction_id': None,
            'jurisdiction_name': None,
        }

    @staticmethod
    def work_model_for(work_type: str) -> type[WorkMixin]:
        models: dict[str, type[WorkMixin]] = {
            'editorial_monograph': EditorialMonograph,
            'academic_monograph': AcademicMonograph,
            'correspondence_monograph': CorrespondenceMonograph,
            'periodical_collection': PeriodicalCollection,
            'journal_article': JournalArticle,
            'magazine': Magazine,
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
            log_exception('Tipo de obra desconhecido', error)
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
            log_exception('Data informada em formato inválido', error)
            expected = 'AAAA' if year_only else 'DD/MM/AAAA'
            raise ValueError(
                f'Informe a data no formato {expected}.'
            ) from error

    @staticmethod
    def parse_multimedia_publication_year(
        value: str,
    ) -> tuple[date, DatePrecision, str]:
        display_year = value.strip()
        if len(display_year) > 30:
            raise ValueError(
                'O ano de publicação deve ter no máximo 30 caracteres.'
            )
        if re.fullmatch(r'\[?s\.d\.?\]?', display_year, re.IGNORECASE):
            return date(1, 1, 1), DatePrecision.UNKNOWN, '[s.d.]'

        patterns = (
            (r'^\[(\d{3})-\??\]$', 10, DatePrecision.DECADE),
            (r'^\[(\d{2})--\??\]$', 100, DatePrecision.CENTURY),
            (r'^\[(\d)-{3}\??\]$', 1000, DatePrecision.MILLENIA),
        )
        for pattern, multiplier, precision in patterns:
            match = re.fullmatch(pattern, display_year)
            if match:
                year = int(match.group(1)) * multiplier
                return date(year, 1, 1), precision, display_year

        match = re.search(r'\d{4}', display_year)
        if match:
            year = int(match.group())
            if year == 0:
                raise ValueError(
                    'O ano de publicação deve ser maior que zero.'
                )
            return date(year, 1, 1), DatePrecision.EXACT, display_year

        raise ValueError(
            'Informe o ano de publicação (ex.: 2024, c2003, '
            '[ca. 1470-1475], [200-] ou [s.d.]).'
        )

    @staticmethod
    def parse_month_date(value: str, unknown: bool = False) -> date:
        if unknown and not value.strip():
            return date(1, 1, 1)
        try:
            month, year = value.split('/')
            return date(int(year), int(month), 1)
        except (TypeError, ValueError) as error:
            log_exception('Mês e ano informados em formato inválido', error)
            raise ValueError(
                'Informe o mês e o ano no formato MM/AAAA.'
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
            log_exception('Precisão de data desconhecida', error)
            raise ValueError('Precisão de data inválida.') from error

    @staticmethod
    def convert_model_values(
        form_data: dict[str, object],
        include_empty: bool = False,
    ) -> dict[str, object]:
        numeric_fields = {
            'consult_start_year',
            'consult_end_year',
            'edition',
            'page_quantity',
            'volumes',
            'collection_number',
            'first_volume_year',
            'last_volume_year',
            'volume',
            'year_season',
            'number',
            'event_number',
            'event_year',
            'publication_year',
            'publication_number',
            'vol_or_year',
            'version',
            'seconds',
            'defense_year',
        }
        date_fields = {
            'viewed_at',
            'filing_date',
            'grant_date',
            'decision_date',
            'promulgation_date',
            'publication_date',
        }
        result: dict[str, object] = {}
        for key, value in form_data.items():
            if key in {
                'work_type', 'authors', 'date_precision', 'date_anchor'
            }:
                continue
            if value in ('', None):
                if include_empty:
                    result[key] = None
                continue
            if key in numeric_fields:
                result[key] = int(str(value))
            elif key in date_fields:
                result[key] = datetime.strptime(
                    str(value), '%d/%m/%Y'
                ).date()
            else:
                result[key] = value

        work_type = form_data.get('work_type')
        if work_type in {'audiovisual_document', 'audio_document'}:
            result.setdefault('responsibilities', {})
        if work_type == 'audio_document':
            result.setdefault('part_responsibilities', {})
        return result
