from datetime import date

from src.domains import (
    AcademicMonograph,
    Author,
    Authorship,
    BibliographicResource,
    DatePrecision,
    EditorialMonograph,
    JournalArticle,
    MonographicProceedings,
    Patent,
    PeriodicalProceedings,
    WorkMixin,
)
from src.strategies import CoreNormalizer, MonographFormatter, PeriodicalFormatter
from src.utils import ABNTUtils


def test_date_normalizer_handles_supported_precisions():
    normalizer = CoreNormalizer()
    anchor = date(2024, 5, 17)

    assert (
        normalizer.display_year_normalizer(DatePrecision.EXACT, anchor)
        == '2024'
    )
    assert (
        normalizer.display_year_normalizer(DatePrecision.DECADE, anchor)
        == '[202-]'
    )
    assert (
        normalizer.display_year_normalizer(DatePrecision.UNKNOWN, anchor)
        == '[s.d.]'
    )


def test_abnt_date_formatter_accepts_missing_date():
    assert ABNTUtils.format_abbrev_date(None) == '[s.d.]'


def test_exception_models_follow_work_contract():
    for model in (
        MonographicProceedings,
        PeriodicalProceedings,
        Patent,
    ):
        assert issubclass(model, WorkMixin)
        assert hasattr(model, 'bibliographic_resource')
        assert hasattr(model, 'authors')


def text_from_reference(view_reference):
    return ''.join(part.content for part in view_reference.parts)


def test_editorial_monograph_formatter_outputs_basic_abnt_reference():
    resource = BibliographicResource()
    resource.authorships = [
        Authorship(
            author=Author(
                given_names='Machado de',
                last_name='Assis',
                given_names_initials='M.',
                last_name_initial='A',
            )
        )
    ]
    resource.editorial_monograph = EditorialMonograph(
        title='Memorias Postumas de Bras Cubas',
        date_anchor=date(1881, 1, 1),
        display_year='1881',
        responsabilities={},
        publication_place='Rio de Janeiro',
        publisher='Tipografia Nacional',
    )

    formatted = text_from_reference(MonographFormatter.formatter(resource))

    assert formatted == (
        'ASSIS, M. Memorias Postumas de Bras Cubas. '
        'Rio de Janeiro: Tipografia Nacional, 1881.'
    )


def test_academic_monograph_formatter_outputs_basic_abnt_reference():
    resource = BibliographicResource()
    resource.authorships = [
        Authorship(
            author=Author(
                given_names='Ana Maria',
                last_name='Silva',
                given_names_initials='A. M.',
                last_name_initial='S',
            )
        )
    ]
    resource.academic_monograph = AcademicMonograph(
        title='Arquivos de Leitura',
        date_anchor=date(2024, 1, 1),
        display_year='2024',
        page_quantity=120,
        thesis_type='Dissertacao',
        education_level='Mestrado',
        course='Filosofia',
        faculty='Universidade Federal',
        publication_place='Curitiba',
        defense_year=2024,
    )

    formatted = text_from_reference(MonographFormatter.formatter(resource))

    assert formatted == (
        'SILVA, A. M. Arquivos de Leitura. 2024. 120 f. '
        'Dissertacao (Mestrado em Filosofia) — Universidade Federal, '
        'Curitiba, 2024'
    )


def test_journal_article_formatter_outputs_basic_abnt_reference():
    resource = BibliographicResource()
    resource.authorships = [
        Authorship(
            author=Author(
                given_names='Ana Maria',
                last_name='Silva',
                given_names_initials='A. M.',
                last_name_initial='S',
            )
        )
    ]
    resource.journal_article = JournalArticle(
        title='Leitura e memoria',
        date_anchor=date(2024, 5, 17),
        display_year='2024',
        journal_title='Revista Brasileira de Estudos',
        publication_place='Sao Paulo',
        publisher='Editora X',
        number=2,
    )

    formatted = text_from_reference(PeriodicalFormatter.formatter(resource))

    assert formatted == (
        'SILVA, A. M. Leitura e memoria. '
        'Revista Brasileira de Estudos, Sao Paulo, n. 2, 17 maio 2024.'
    )
