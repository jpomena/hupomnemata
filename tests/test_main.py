from datetime import date

import flet as ft
import pytest
from sqlalchemy import create_engine

from src.db import db as db_module
from src.domains import (
    AcademicMonograph,
    Author,
    Authorship,
    BibliographicResource,
    CorrespondenceMonograph,
    DatePrecision,
    EditorialMonograph,
    JournalArticle,
    MonographicProceedings,
    NewspaperArticle,
    Patent,
    PeriodicalCollection,
    PeriodicalProceedings,
    Statute,
    WorkMixin,
)
from src.controllers.core_controller import CoreController
from src.services.work_service import WorkService
from src.strategies import (
    CoreNormalizer, MonographFormatter, PeriodicalFormatter
)
from src.utils import ABNTUtils
from src.views.work_insert_specs import (
    INHERITED_FROM_PARENT_FIELDS,
    PARTIAL_WORK_TYPES,
    WORK_TYPES,
)


@pytest.fixture(autouse=True)
def clean_test_db(tmp_path):
    db_file = tmp_path / 'hupomnemata_test.db'
    engine = create_engine(f'sqlite:///{db_file.as_posix()}')
    db_module.engine = engine
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    yield
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()


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


def test_work_models_require_unique_bib_res_id():
    unique_columns = {
        column.name
        for constraint in EditorialMonograph.__table__.constraints
        if hasattr(constraint, 'columns')
        for column in constraint.columns
    }
    assert 'bib_res_id' in unique_columns


def test_partial_metadata_is_declared_only_for_supported_models():
    supported = (
        EditorialMonograph,
        AcademicMonograph,
        CorrespondenceMonograph,
        PeriodicalCollection,
        JournalArticle,
        NewspaperArticle,
        MonographicProceedings,
        PeriodicalProceedings,
    )

    assert 'is_partial' not in BibliographicResource.__table__.columns
    assert 'parent_bibliographic_resource_id' not in (
        BibliographicResource.__table__.columns
    )

    for model in supported:
        assert 'is_partial' in model.__table__.columns
        assert 'parent_bibliographic_resource_id' in model.__table__.columns

    assert 'is_partial' not in Patent.__table__.columns
    assert 'parent_bibliographic_resource_id' not in Patent.__table__.columns


def test_editorial_monograph_conversion_ignores_unsupported_responsibilities():
    converted = WorkService.convert_model_values({
        'work_type': 'editorial_monograph',
        'title': 'A obra',
        'publication_place': 'São Paulo',
        'publisher': 'Editora',
        'date_precision': 'Data exata',
    })

    assert 'responsibilities' not in converted


def test_legal_documents_include_required_db_fields_in_payload():
    statute = WorkService.convert_model_values({
        'work_type': 'statute',
        'title': 'Lei X',
        'publication_media': 'Diário Oficial',
        'publication_number': '123',
        'promulgation_date': '02/01/2024',
        'date_precision': 'Data exata',
    })
    caselaw = WorkService.convert_model_values({
        'work_type': 'caselaw',
        'title': 'Acórdão Y',
        'publication_media': 'TRF-4',
        'decision_type': 'Acórdão',
        'decision_date': '10/11/2024',
        'date_precision': 'Data exata',
    })

    statute_date = statute['promulgation_date']
    caselaw_date = caselaw['decision_date']

    assert statute['publication_number'] == 123
    assert isinstance(statute_date, date)
    assert statute_date.isoformat() == '2024-01-02'
    assert isinstance(caselaw_date, date)
    assert caselaw_date.isoformat() == '2024-11-10'


def test_statute_uses_only_two_dates_in_form_and_payload():
    statute_spec = next(spec for spec in WORK_TYPES if spec.key == 'statute')
    keys = {field.key for field in statute_spec.fields}

    assert 'date_anchor' in keys
    assert 'promulgation_date' in keys
    assert 'publication_date' not in keys

    payload = WorkService.convert_model_values({
        'work_type': 'statute',
        'title': 'Lei Z',
        'publication_media': 'Diário Oficial',
        'date_anchor': '15/02/2024',
        'promulgation_date': '02/01/2024',
        'date_precision': 'Data exata',
    })

    promulgation = payload['promulgation_date']
    assert isinstance(promulgation, date)
    assert promulgation.isoformat() == '2024-01-02'
    assert 'publication_date' not in payload


def test_controller_does_not_send_responsibilities_for_editorial_monograph():
    converted = CoreController.convert_model_values({
        'work_type': 'editorial_monograph',
        'title': 'A obra',
        'publication_place': 'São Paulo',
        'publisher': 'Editora',
        'date_precision': 'Data exata',
    })

    assert 'responsibilities' not in converted


def test_specific_work_is_detected_after_resource_creation():
    from src.db.db import SessionLocal

    with SessionLocal() as session:
        resource = BibliographicResource()
        resource.editorial_monograph = EditorialMonograph(
            title='Obra principal',
            display_year='2024',
            date_anchor=date(2024, 1, 1),
            publication_place='São Paulo',
            publisher='Editora',
            responsibilities={},
        )
        session.add(resource)
        session.commit()
        session.refresh(resource)

        assert resource.specific_work is not None
        assert isinstance(resource.specific_work, EditorialMonograph)


def test_service_returns_materialized_work_data_after_session_close():
    payload = {
        'work_model': EditorialMonograph,
        'relationship_name': 'editorial_monograph',
        'author_names': [{
            'name': 'Maria Silva',
            'id': None,
            'corporation': False,
            'acronym': None,
            'jurisdiction_id': None,
            'jurisdiction_name': None,
        }],
        'resource_data': {},
        'work_data': {
            'title': 'Livro materializado',
            'display_year': '2024',
            'date_anchor': date(2024, 1, 1),
            'date_precision': DatePrecision.EXACT,
            'publication_place': 'São Paulo',
            'publisher': 'Editora',
            'responsibilities': {},
        },
    }

    result = WorkService().resolve_and_create(payload)
    assert result['requires_choice'] is False
    assert result['resource_id'] > 0
    assert result['work_title'] == 'Livro materializado'


def test_repository_lists_partial_works_with_parent_loaded():
    from src.db.db import SessionLocal
    from src.repositories import WorkRepository

    with SessionLocal() as session:
        parent = BibliographicResource()
        parent.editorial_monograph = EditorialMonograph(
            title='Obra principal',
            display_year='2023',
            date_anchor=date(2023, 1, 1),
            publication_place='São Paulo',
            publisher='Editora',
            responsibilities={},
        )

        child_resource = BibliographicResource()
        partial = EditorialMonograph(
            title='Trecho de obra',
            is_partial=True,
            display_year='2024',
            date_anchor=date(2024, 1, 1),
            publication_place='São Paulo',
            publisher='Editora',
            responsibilities={},
        )
        child_resource.editorial_monograph = partial
        session.add_all([parent, child_resource])
        session.flush()
        partial.parent_bibliographic_resource_id = parent.id
        session.commit()

        works = WorkRepository(session).list_works()
        partial_work = next(
            resource.specific_work
            for resource in works
            if resource.specific_work is not None
            and getattr(resource.specific_work, 'is_partial', False)
        )

        assert (
            getattr(partial_work, 'parent_bibliographic_resource', None)
            is not None
        )
        assert partial_work.parent_bibliographic_resource.id == parent.id


def test_partial_work_controls_are_not_universal_in_form_specs():
    for spec in WORK_TYPES:
        keys = {field.key for field in spec.fields}
        if spec.key in PARTIAL_WORK_TYPES:
            assert 'is_partial' in keys
        else:
            assert 'is_partial' not in keys

    assert 'publication_place' in INHERITED_FROM_PARENT_FIELDS
    assert 'isbn' in INHERITED_FROM_PARENT_FIELDS
    assert 'issn' in INHERITED_FROM_PARENT_FIELDS


def test_legal_documents_require_exact_date_and_publication_fields():
    statutes = next(spec for spec in WORK_TYPES if spec.key == 'statute')
    caselaw = next(spec for spec in WORK_TYPES if spec.key == 'caselaw')

    assert statutes.date_kind == 'date'
    assert caselaw.date_kind == 'date'


def test_legal_documents_accept_full_date_in_date_anchor():
    from src.controllers.core_controller import CoreController

    controller = CoreController.__new__(CoreController)
    controller.service = WorkService(CoreNormalizer())
    controller.normalizer = CoreNormalizer()

    payload = controller.prepare_work_payload(
        {
            'work_type': 'statute',
            'title': 'Lei X',
            'authors': [],
            'date_precision': 'Data exata',
            'date_anchor': '31/12/2024',
            'publication_media': 'Diário Oficial',
            'publication_place': 'Brasília',
            'promulgation_date': '01/12/2024',
        }
    )

    assert payload['work_data']['date_anchor'] == date(2024, 12, 31)
    assert payload['work_data']['promulgation_date'] == date(2024, 12, 1)


def test_statute_uses_date_anchor_and_promulgation_date_only():
    statute_spec = next(spec for spec in WORK_TYPES if spec.key == 'statute')
    keys = {field.key for field in statute_spec.fields}

    assert 'date_anchor' in keys
    assert 'promulgation_date' in keys
    assert 'publication_date' not in keys

    from src.db.db import SessionLocal

    with SessionLocal() as session:
        resource = BibliographicResource()
        resource.statute = Statute(
            title='Lei X',
            display_year='2024',
            date_anchor=date(2024, 1, 1),
            publication_media='Diário Oficial',
            publication_place='Brasília',
            promulgation_date=date(2024, 1, 2),
            publication_number=123,
        )
        session.add(resource)
        session.commit()
        session.refresh(resource)

        assert resource.specific_work is not None
        assert resource.specific_work.date_anchor == date(2024, 1, 1)
        assert resource.specific_work.promulgation_date == date(2024, 1, 2)

    assert any(
        field.key == 'publication_media' for field in statute_spec.fields
    )
    assert any(
        field.key == 'publication_place' for field in statute_spec.fields
    )
    caselaw_spec = next(spec for spec in WORK_TYPES if spec.key == 'caselaw')
    assert any(
        field.key == 'publication_media' for field in caselaw_spec.fields
    )
    assert any(
        field.key == 'publication_place' for field in caselaw_spec.fields
    )


def test_repository_materializes_work_parent_for_detached_objects():
    from src.db.db import SessionLocal
    from src.repositories import WorkRepository

    with SessionLocal() as session:
        author = WorkRepository(session)._find_or_create_author({
            'name': 'Empresa do Brasil',
            'id': None,
            'corporation': True,
            'acronym': 'EB',
            'jurisdiction_id': None,
            'jurisdiction_name': 'Brasil',
        })
        resource = BibliographicResource()
        resource.statute = Statute(
            title='Lei de teste',
            display_year='2024',
            date_anchor=date(2024, 1, 1),
            publication_media='Diário Oficial',
            publication_place='Brasília',
            promulgation_date=date(2024, 1, 2),
            publication_number=123,
        )
        resource.authorships.append(Authorship(author=author))
        session.add(resource)
        session.commit()

        works = WorkRepository(session).list_works()

    detached = works[0]
    assert detached.specific_work is not None
    assert len(detached.specific_work.authors) == 1
    assert detached.specific_work.authors[0].given_names == 'Empresa do Brasil'


def test_legal_formatter_uses_author_jurisdiction_fields():
    from src.strategies.legal_docs_formatter import LegalDocsFormatter

    author = type(
        'AuthorStub',
        (),
        {
            'corporation': True,
            'given_names': 'Empresa do Brasil',
            'last_name': '',
            'jurisdiction': type(
                'JurisdictionStub',
                (),
                {'given_names': 'Brasil', 'last_name': ''},
            )(),
        },
    )()
    work = type(
        'WorkStub',
        (),
        {
            'authors': [author],
            'region': None,
            'panel': None,
            'title': 'Lei do teste',
            'case_number': None,
            'abstract': None,
            'rapporteur': None,
            'decision_date': None,
            'publication_media': 'Diário Oficial',
            'publication_number': 123,
            'date_anchor': date(2024, 1, 2),
            'additional_notes': None,
            'url': None,
            'viewed_at': None,
        },
    )()

    parts = LegalDocsFormatter._format_author(work)
    rendered = ''.join(part.content for part in parts)
    assert 'BRASIL' in rendered


def test_search_authors_returns_given_names_only_for_corporations():
    from src.db.db import SessionLocal
    from src.repositories import WorkRepository

    with SessionLocal() as session:
        WorkRepository(session)._find_or_create_author({
            'name': 'Empresa do Brasil',
            'id': None,
            'corporation': True,
            'acronym': 'EB',
            'jurisdiction_id': None,
            'jurisdiction_name': 'Brasil',
        })

        results = WorkRepository(session).search_authors('Empresa')

    assert results
    assert results[0]['corporation'] is True
    assert results[0]['name'] == 'Empresa do Brasil'
    assert 'Empresa do Brasil Empresa do Brasil' not in results[0]['name']


def test_repository_creates_corporate_author_with_jurisdiction():
    from src.db.db import SessionLocal
    from src.repositories import WorkRepository

    with SessionLocal() as session:
        author = WorkRepository(session)._find_or_create_author({
            'name': 'Empresa do Brasil',
            'id': None,
            'corporation': True,
            'acronym': 'EB',
            'jurisdiction_id': None,
            'jurisdiction_name': 'Brasil',
        })

        assert author.corporation is True
        assert author.jurisdiction is not None
        assert author.jurisdiction.given_names == 'Brasil'
        assert author.jurisdiction.corporation is True


def test_regular_checkbox_fields_render_in_separate_rows():
    class DummyPage:
        def update(self):
            pass

    config = type(
        'ConfigStub',
        (),
        {
            'colors': {
                'border': '#111',
                'gold': '#d4af37',
                'text': '#fff',
                'muted': '#bbb',
                'surface': '#222',
                'card_hover': '#333',
                'black': '#000',
            },
            'font_families': {
                'montserrat': 'Montserrat',
                'cormorant': 'Cormorant',
            },
            'font_sizes': {
                'cormorant_small': 14,
                'montserrat_medium': 16,
                'montserrat_tiny': 12,
                'cormorant_large': 30,
                'montserrat_large': 18,
            },
            'font_weights': {
                'montserrat_normal': 'normal',
                'montserrat_semibold': 'bold',
                'cormorant_semibold': 'bold',
                'cormorant_bold': 'bold',
            },
            'ui': {
                'control_gap': 12,
                'modal_gap': 16,
                'card_radius': 12,
                'card_padding': 10,
                'animation_ms': 200,
                'modal_content_padding': 10,
                'modal_type_panel_width': 180,
                'modal_width': 900,
                'modal_height': 700,
            },
        },
    )()

    from src.views.work_insert_modal import WorkInsertModalComposer

    composer = WorkInsertModalComposer(
        DummyPage(),
        config,
        on_save=lambda data: True,
        search_authors=lambda q: [],
        search_works=lambda q: [],
        on_create_parent_work=lambda callback: None,
    )
    composer.selected = next(
        spec for spec in WORK_TYPES if spec.key == 'audiovisual_document'
    )
    composer.partial_enabled = False
    composer._render(update_page=False)

    rows = composer.form.controls[1].controls
    checkbox_row = next(
        row for row in rows
        if isinstance(row, ft.Row)
        and row.controls
        and any(isinstance(control, ft.Checkbox) for control in row.controls)
    )

    checkbox_pairs = [
        type(control).__name__ for control in checkbox_row.controls
    ]
    assert checkbox_pairs == ['Checkbox', 'Checkbox']
    assert all(name != 'Text' for name in checkbox_pairs)
    assert checkbox_row in rows[:1]


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
        responsibilities={},
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
