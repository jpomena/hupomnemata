from datetime import date, datetime

import flet as ft
import pytest
from sqlalchemy import create_engine, select

from src.db import db as db_module
from src.domains import (
    AcademicMonograph,
    AudioDocument,
    Author,
    Authorship,
    BibliographicResource,
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
    WorkMixin,
)
from src.controllers.core_controller import CoreController
from src.controllers.work_submission_controller import (
    WorkSubmissionController,
)
from src.services.work_service import WorkService
from src.services.work_form_service import WorkFormService
from src.strategies import (
    CoreNormalizer,
    LegalDocsFormatter,
    MonographFormatter,
    PeriodicalFormatter,
    ProceedingsFormatter,
)
from src.strategies.patent_formatter import PatentFormatter
from src.utils import ABNTUtils
from src.views.work_insert_specs import (
    ALWAYS_PARTIAL_TYPES,
    DEFAULTED_FIELDS,
    INHERITED_FROM_PARENT_FIELDS,
    PARTIAL_FIELDS_BY_TYPE,
    PARTIAL_FORM_FIELDS,
    PARTIAL_WORK_TYPES,
    WORK_TYPES,
)
from src.utils import error_log


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


def test_work_title_spelling_can_be_preserved_for_reference_formatting():
    payload = WorkFormService().prepare_payload({
        'work_type': 'editorial_monograph',
        'title': 'Bíblia King James',
        'preserve_title_spelling': True,
        'authors': [],
        'date_anchor': '2024',
        'date_precision': 'Data exata',
    })

    assert payload['work_data']['title'] == 'Bíblia King James'
    assert payload['work_data']['preserve_title_spelling'] is True
    assert ABNTUtils.format_title_and_subtitle(
        'Bíblia King James',
        preserve_title_spelling=True,
    )[0][0] == ' Bíblia King James'
    assert ABNTUtils.format_title_without_author(
        'Bíblia King James',
        preserve_title_spelling=True,
    ) == 'BÍBLIA King James'
    assert ABNTUtils.format_title_without_author(
        'a bíblia King James',
        preserve_title_spelling=True,
    ) == 'A BÍBLIA King James'
    assert ABNTUtils.format_title_and_subtitle(
        'de volta aos livros',
        without_author=True,
        preserve_title_spelling=True,
    )[0][0] == 'DE VOLTA aos livros'


def test_authors_are_optional_for_every_work_type():
    for spec in WORK_TYPES:
        author_fields = [
            field for field in spec.fields if field.key == 'authors'
        ]
        assert all(not field.required for field in author_fields), spec.key


def test_authorless_work_can_be_created_and_referenced_by_title():
    form_data = {
        'work_type': 'editorial_monograph',
        'title': 'Bíblia King James',
        'preserve_title_spelling': True,
        'date_anchor': '2024',
        'date_precision': 'Data exata',
    }
    assert WorkSubmissionController._missing_required_fields(form_data) == []

    result = WorkService().resolve_and_create(
        WorkFormService().prepare_payload(form_data)
    )
    assert not result['requires_choice']
    resource = next(
        work
        for work in WorkService().list_works()
        if work.id == result['resource_id']
    )
    assert resource.authorships == []

    reference = CoreController.format_reference(resource)
    assert reference is not None
    assert ''.join(part.content for part in reference.parts).startswith(
        'BÍBLIA King James.'
    )


def test_authorless_proceedings_reference_starts_with_title():
    work = MonographicProceedings(
        title='Memórias do encontro científico',
    )

    formatted = ''.join(
        part.content for part in ProceedingsFormatter._format_unpublished(work)
    )
    assert formatted.startswith('MEMÓRIAS do encontro científico.')


def test_authorless_legal_reference_starts_with_title():
    work = CaseLaw(
        title='Decisão sobre direitos autorais',
        decision_type='Acórdão',
        decision_date=date(2024, 1, 2),
        publication_media='Diário da Justiça',
        date_anchor=date(2024, 1, 3),
    )

    formatted = ''.join(
        part.content for part in LegalDocsFormatter.formatter(work).parts
    )
    assert formatted.startswith('DECISÃO sobre direitos autorais.')


def test_authorless_patent_reference_starts_with_title():
    work = Patent(
        title='Sistema de leitura digital',
        applicant='Empresa',
        number='BR123',
        filing_date=date(2024, 1, 2),
    )

    formatted = ''.join(
        part.content for part in PatentFormatter.formatter(work).parts
    )
    assert formatted.startswith('SISTEMA de leitura digital.')

    normalized_payload = WorkFormService().prepare_payload({
        'work_type': 'editorial_monograph',
        'title': 'Bíblia King James',
        'authors': [],
        'date_anchor': '2024',
        'date_precision': 'Data exata',
    })
    assert normalized_payload['work_data']['title'] == 'Bíblia king james'
    assert normalized_payload['work_data']['preserve_title_spelling'] is False


def test_existing_work_tables_migrate_title_spelling_flag():
    with db_module.engine.begin() as connection:
        connection.exec_driver_sql(
            'DROP TABLE editorial_monographs'
        )
        connection.exec_driver_sql(
            'CREATE TABLE editorial_monographs ('
            'id INTEGER PRIMARY KEY, '
            'title VARCHAR(150) NOT NULL, '
            'bib_res_id INTEGER NOT NULL)'
        )

    db_module._ensure_legacy_columns()

    with db_module.engine.connect() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql(
                'PRAGMA table_info("editorial_monographs")'
            )
        }
    assert 'preserve_title_spelling' in columns


def test_exception_models_follow_work_contract():
    for model in (
        MonographicProceedings,
        PeriodicalProceedings,
        AudioDocument,
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
        AudioDocument,
        EditorialMonograph,
        AcademicMonograph,
        CorrespondenceMonograph,
        PeriodicalCollection,
        JournalArticle,
        NewspaperArticle,
        MonographicProceedings,
        PeriodicalProceedings,
        MusicalScore,
    )

    assert 'is_partial' not in BibliographicResource.__table__.columns
    assert 'parent_bibliographic_resource_id' not in (
        BibliographicResource.__table__.columns
    )

    for model in supported:
        assert 'is_partial' in model.__table__.columns
        assert model.__table__.columns['is_partial'].name == 'is_partial'
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


def test_database_required_work_fields_are_required_in_forms():
    auto_provided_fields = {
        'sound',
        'colorized',
        'responsibilities',
        'part_responsibilities',
        'publication_year',
    }

    for spec in WORK_TYPES:
        model = WorkService.work_model_for(spec.key)
        database_required = {
            column.name
            for column in model.__table__.columns
            if not column.nullable
            and not column.primary_key
            and column.default is None
            and column.name not in {'bib_res_id'}
            and column.name not in auto_provided_fields
        }
        if spec.key == 'visual_document':
            database_required.discard('title')
        if spec.key == 'periodical_collection':
            database_required.discard('title')
        interface_required = {
            field.key
            for field in spec.fields
            if field.required
            and field.key not in DEFAULTED_FIELDS.get(spec.key, set())
        }

        assert database_required <= interface_required, (
            f'{spec.key} is missing required fields: '
            f'{database_required - interface_required}'
        )


def test_multimedia_forms_only_expose_formatter_relevant_shared_fields():
    multimedia_types = {
        'audiovisual_document',
        'audio_document',
        'musical_score',
        'visual_document',
        'cartographic_document',
        'three_dimensional_document',
    }
    for spec in WORK_TYPES:
        if spec.key not in multimedia_types:
            continue
        field_keys = {field.key for field in spec.fields}
        assert 'abstract' not in field_keys
        assert 'date_anchor' in field_keys
        assert 'display_year' not in field_keys
        assert 'date_precision' not in field_keys

    three_dimensional = next(
        spec for spec in WORK_TYPES
        if spec.key == 'three_dimensional_document'
    )
    three_dimensional_fields = {
        field.key for field in three_dimensional.fields
    }
    assert 'responsiblity_type' not in three_dimensional_fields
    assert 'publication_place' not in three_dimensional_fields
    assert 'publisher' not in three_dimensional_fields


@pytest.mark.parametrize(
    'work_type',
    [
        'audiovisual_document',
        'audio_document',
        'musical_score',
        'visual_document',
        'cartographic_document',
        'three_dimensional_document',
    ],
)
def test_multimedia_form_uses_one_publication_year_field(work_type):
    payload = WorkFormService().prepare_payload({
        'work_type': work_type,
        'title': 'Obra',
        'authors': [],
        'date_anchor': '[ca. 1470-1475]',
    })

    assert payload['work_data']['display_year'] == '[ca. 1470-1475]'
    assert payload['work_data']['date_anchor'] == date(1470, 1, 1)


@pytest.mark.parametrize(
    ('publication_year', 'expected_year', 'expected_precision'),
    [
        ('c2003', 2003, DatePrecision.EXACT),
        ('[200-]', 2000, DatePrecision.DECADE),
        ('[19--?]', 1900, DatePrecision.CENTURY),
        ('[s.d.]', 1, DatePrecision.UNKNOWN),
    ],
)
def test_multimedia_publication_year_supplies_sorting_date_and_precision(
    publication_year,
    expected_year,
    expected_precision,
):
    payload = WorkFormService().prepare_payload({
        'work_type': 'visual_document',
        'title': 'Imagem',
        'date_anchor': publication_year,
    })

    assert payload['work_data']['display_year'] == publication_year
    assert payload['work_data']['date_anchor'] == date(expected_year, 1, 1)
    assert payload['work_data']['date_precision'] == expected_precision


@pytest.mark.parametrize(
    'work_type',
    [
        'audiovisual_document',
        'audio_document',
        'musical_score',
        'visual_document',
        'cartographic_document',
        'three_dimensional_document',
    ],
)
def test_multimedia_online_form_requires_access_date(work_type):
    missing = WorkSubmissionController._missing_required_fields({
        'work_type': work_type,
        'url': 'https://example.com/documento',
    })

    assert 'Data de acesso' in missing


def test_submission_rejects_empty_required_fields_and_missing_parent():
    missing = WorkSubmissionController._missing_required_fields({
        'work_type': 'academic_monograph',
        'title': 'A obra',
        'authors': [{'name': 'Ana Silva'}],
        'is_partial': True,
    })

    assert 'Quantidade de páginas' not in missing
    assert 'Obra-pai' in missing


def test_magazine_form_has_only_name_and_publication_place():
    magazine_spec = next(
        spec for spec in WORK_TYPES if spec.key == 'magazine'
    )
    assert {field.key for field in magazine_spec.fields} == {
        'title',
        'publication_place',
    }

    payload = WorkFormService().prepare_payload({
        'work_type': 'magazine',
        'title': 'Revista de Estudos',
        'publication_place': 'São Paulo',
    })

    assert payload['author_names'] == []
    assert WorkSubmissionController._missing_required_fields({
        'work_type': 'magazine',
        'title': 'Revista de Estudos',
        'publication_place': 'São Paulo',
    }) == []
    assert 'date_anchor' not in payload['work_data']


def test_magazine_and_periodical_children_are_linked_and_magazine_has_no_author():
    from src.db.db import SessionLocal

    form_service = WorkFormService()
    work_service = WorkService()
    magazine = work_service.create(form_service.prepare_payload({
        'work_type': 'magazine',
        'title': 'Revista de Estudos',
        'publication_place': 'São Paulo',
    }))

    assert work_service.search_works('Revista', 'magazine') == [
        (magazine.id, 'Revista de estudos')
    ]

    article = work_service.create(form_service.prepare_payload({
        'work_type': 'journal_article',
        'title': 'Um artigo',
        'authors': ['Ana Silva'],
        'date_anchor': '05/2024',
        'date_precision': 'Data exata',
        'number': '2',
        'parent_bibliographic_resource_id': magazine.id,
    }))
    collection = work_service.create(form_service.prepare_payload({
        'work_type': 'periodical_collection',
        'first_volume_year': '2018',
        'parent_bibliographic_resource_id': magazine.id,
    }))

    with SessionLocal() as session:
        magazine_work = session.get(
            BibliographicResource, magazine.id
        ).specific_work
        article_work = session.get(
            BibliographicResource, article.id
        ).specific_work
        collection_work = session.get(
            BibliographicResource, collection.id
        ).specific_work

        assert isinstance(magazine_work, Magazine)
        assert magazine_work.bibliographic_resource.authorships == []
        assert isinstance(article_work, JournalArticle)
        assert article_work.is_partial is True
        assert article_work.parent_bibliographic_resource_id == magazine.id
        assert article_work.journal_title == magazine_work.title
        assert article_work.publication_place == 'São Paulo'
        assert isinstance(collection_work, PeriodicalCollection)
        assert collection_work.is_partial is True
        assert collection_work.parent_bibliographic_resource_id == magazine.id
        assert collection_work.title == magazine_work.title


def test_periodical_migration_creates_and_reuses_magazine_parent():
    from src.db.db import SessionLocal

    with SessionLocal() as session:
        article_resource = BibliographicResource()
        article_resource.journal_article = JournalArticle(
            title='Artigo legado',
            journal_title='Revista legada',
            publication_place='Curitiba',
            number=1,
        )
        collection_resource = BibliographicResource()
        collection_resource.periodical_collection = PeriodicalCollection(
            title='Coleção legada',
            journal_title='Revista legada',
            publication_place='Curitiba',
            first_volume_year=2000,
        )
        session.add_all([article_resource, collection_resource])
        session.commit()
        article_id = article_resource.id
        collection_id = collection_resource.id

    db_module._migrate_periodical_parent_links()

    with SessionLocal() as session:
        article = session.get(
            BibliographicResource, article_id
        ).specific_work
        collection = session.get(
            BibliographicResource, collection_id
        ).specific_work
        assert article.is_partial is True
        assert collection.is_partial is True
        assert (
            article.parent_bibliographic_resource_id
            == collection.parent_bibliographic_resource_id
        )
        magazine_resource = session.get(
            BibliographicResource,
            article.parent_bibliographic_resource_id,
        )
        assert isinstance(magazine_resource.specific_work, Magazine)
        assert magazine_resource.specific_work.title == 'Revista legada'
        assert (
            magazine_resource.specific_work.publication_place == 'Curitiba'
        )


def test_periodical_proceedings_publication_date_is_converted():
    converted = WorkService.convert_model_values({
        'work_type': 'periodical_proceedings',
        'publication_date': '16/10/2026',
    })

    publication_date = converted['publication_date']
    assert isinstance(publication_date, date)
    assert publication_date.isoformat() == '2026-10-16'


def test_exception_logger_writes_message_and_traceback(tmp_path, monkeypatch):
    log_path = tmp_path / 'hupomnemata.txt'
    monkeypatch.setattr(error_log, 'LOG_PATH', log_path)

    try:
        raise RuntimeError('erro de teste')
    except RuntimeError as error:
        error_log.log_exception('contexto de teste', error)

    contents = log_path.read_text(encoding='utf-8')
    assert 'contexto de teste: erro de teste' in contents
    assert 'RuntimeError: erro de teste' in contents


def test_edit_form_values_restore_dates_and_precision():
    work = EditorialMonograph(
        title='A obra',
        date_anchor=date(2022, 5, 17),
        display_year='2022',
        date_precision=DatePrecision.EXACT,
        publication_place='São Paulo',
        publisher='Editora',
    )

    values = CoreController._edit_form_values(
        work,
        'editorial_monograph',
    )

    assert values['title'] == 'A obra'
    assert values['date_anchor'] == '2022'
    assert values['date_precision'] == 'Data exata'


def test_repository_update_preserves_resource_id_and_clears_optional_fields():
    from src.db.db import SessionLocal
    from src.repositories import WorkRepository

    initial_payload = {
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
            'title': 'Título antigo',
            'subtitle': 'Subtítulo para remover',
            'display_year': '2024',
            'date_anchor': date(2024, 1, 1),
            'date_precision': DatePrecision.EXACT,
            'publication_place': 'São Paulo',
            'publisher': 'Editora',
        },
    }
    resource_id = WorkService().create(initial_payload).id

    with SessionLocal() as session:
        resource = session.get(BibliographicResource, resource_id)
        assert resource is not None
        author_id = resource.authorships[0].author_id
        updated = WorkRepository(session).update(
            resource_id,
            {
                **initial_payload,
                'author_names': [{
                    **initial_payload['author_names'][0],
                    'id': author_id,
                }],
                'work_data': {
                    **initial_payload['work_data'],
                    'title': 'Título corrigido',
                    'subtitle': None,
                },
            },
        )

        assert updated.id == resource_id
        assert updated.specific_work.title == 'Título corrigido'
        assert updated.specific_work.subtitle is None
        assert len(updated.authorships) == 1


def test_service_update_returns_resource_with_loaded_specific_work():
    payload = {
        'work_model': EditorialMonograph,
        'relationship_name': 'editorial_monograph',
        'author_names': [],
        'resource_data': {},
        'work_data': {
            'title': 'Título antes',
            'display_year': '2024',
            'date_anchor': date(2024, 1, 1),
            'date_precision': DatePrecision.EXACT,
            'publication_place': 'São Paulo',
            'publisher': 'Editora',
        },
    }
    resource_id = WorkService().create(payload).id

    updated_title = WorkService().update(
        resource_id,
        {
            **payload,
            'work_data': {
                **payload['work_data'],
                'title': 'Título depois',
            },
        },
    )

    assert updated_title == 'Título depois'


def test_controller_does_not_send_responsibilities_for_editorial_monograph():
    converted = WorkFormService.convert_model_values({
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


def test_core_controller_routes_digital_document_reference():
    from src.db.db import SessionLocal

    with SessionLocal() as session:
        resource = BibliographicResource()
        resource.miscellaneous_digital_document = MiscDigitalDocument(
            title='Documento digital',
            display_year='2024',
            publication_place='Internet',
        )
        session.add(resource)
        session.flush()

        reference = CoreController.format_reference(resource)

    assert 'DOCUMENTO digital' in ''.join(
        part.content for part in reference.parts
    )


def test_core_controller_formats_patent_reference():
    with db_module.SessionLocal() as session:
        resource = BibliographicResource()
        resource.patent = Patent(
            title='Patente de teste',
            applicant='Autora',
            number='BR123',
            filing_date=date(2024, 1, 1),
        )
        session.add(resource)
        session.flush()

        reference = CoreController.format_reference(resource)
        assert reference is not None
        assert 'PATENTE de teste' in ''.join(part.content for part in reference.parts)


def test_views_do_not_import_strategies_or_repositories():
    import ast
    from pathlib import Path

    views_path = Path(__file__).resolve().parents[1] / 'src' / 'views'
    forbidden_prefixes = ('src.strategies', 'src.repositories')

    for view_file in views_path.glob('*.py'):
        tree = ast.parse(view_file.read_text(encoding='utf-8'))
        imported_modules = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]
        imported_modules.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )

        assert not any(
            module.startswith(forbidden_prefixes)
            for module in imported_modules
        ), view_file


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


def test_service_lists_partial_work_ready_for_detached_reference_formatting():
    from src.db.db import SessionLocal
    from src.repositories import WorkRepository

    with SessionLocal() as session:
        parent = BibliographicResource(
            editorial_monograph=EditorialMonograph(
                title='Obra principal',
                display_year='2023',
                date_anchor=date(2023, 1, 1),
                publication_place='São Paulo',
                publisher='Editora',
            )
        )
        child = BibliographicResource(
            editorial_monograph=EditorialMonograph(
                title='Parte consultada',
                display_year='2024',
                date_anchor=date(2024, 1, 1),
                publication_place='São Paulo',
                publisher='Editora',
                is_partial=True,
            )
        )
        session.add_all([parent, child])
        session.flush()
        child.editorial_monograph.parent_bibliographic_resource_id = parent.id
        session.commit()
        child_id = child.id

    works = WorkService().list_works()
    detached_child = next(resource for resource in works if resource.id == child_id)
    formatted = MonographFormatter.formatter(detached_child)

    assert 'OBRA principal' in ''.join(
        part.content for part in formatted.parts
    )
    assert WorkService().get_work_title(
        detached_child.editorial_monograph.parent_bibliographic_resource_id
    ) == 'Obra principal'


def test_acervo_nesting_uses_parent_id_without_lazy_loading():
    from types import SimpleNamespace
    from src.db.db import SessionLocal
    from src.views.works import WorksComposer

    with SessionLocal() as session:
        parent = BibliographicResource(
            editorial_monograph=EditorialMonograph(
                title='Obra principal',
                display_year='2023',
                date_anchor=date(2023, 1, 1),
                publication_place='São Paulo',
                publisher='Editora',
            )
        )
        child = BibliographicResource(
            editorial_monograph=EditorialMonograph(
                title='Parte consultada',
                display_year='2024',
                date_anchor=date(2024, 1, 1),
                publication_place='São Paulo',
                publisher='Editora',
                is_partial=True,
            )
        )
        session.add_all([parent, child])
        session.flush()
        child.editorial_monograph.parent_bibliographic_resource_id = parent.id
        session.flush()
        parent_id = parent.id
        child_id = child.id
        session.expire(
            child.editorial_monograph,
            ['parent_bibliographic_resource'],
        )
        resources = [parent, child]

    composer = object.__new__(WorksComposer)
    composer.config = SimpleNamespace(ui={'grid_gap': 20})
    composer._resource_card = lambda resource, level=0: ft.Container()

    nested = composer._nest_resources(resources)
    assert len(nested) == 1
    assert resources[0].id == parent_id
    assert resources[1].id == child_id


def test_acervo_search_shows_matches_and_filters_in_real_time():
    from types import SimpleNamespace
    from src.configs.settings import (
        COLORS_LIGHT,
        FONT_FAMILIES,
        FONT_SIZES,
        FONT_WEIGHTS,
        ICON_SIZES,
        MAIN_VIEW_CARDS,
        PAGE_FONTS,
        TEXTS,
        UI,
    )
    from src.utils.types import ViewConfig
    from src.views.works import WorksComposer

    works = [
        SimpleNamespace(
            id=1,
            specific_work=SimpleNamespace(title='Alfa: Introdução'),
        ),
        SimpleNamespace(
            id=2,
            specific_work=SimpleNamespace(title='Alfa: Estudos'),
        ),
        SimpleNamespace(
            id=3,
            specific_work=SimpleNamespace(title='Beta'),
        ),
    ]
    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={},
        main_view_cards=MAIN_VIEW_CARDS,
    )
    composer = WorksComposer(
        scale=1,
        config=config,
        works=works,
        on_navigate=lambda _destination: None,
        on_work_click=lambda _resource: None,
        on_edit_work=lambda _resource: None,
        format_reference=lambda _resource: None,
        on_copy_reference=lambda _reference: None,
        on_delete_work=lambda _resource: None,
    )
    matched_resource_ids = []

    def render_resources(resources):
        matched_resource_ids[:] = [resource.id for resource in resources]
        return [ft.Container(key=str(resource.id)) for resource in resources]

    composer._nest_resources = render_resources
    composer._compose_board()
    composer.board.update = lambda: None

    assert not composer.work_search.expand
    assert composer.work_search_group.expand
    composer.work_search.value = 'alfa'
    composer._search_works(SimpleNamespace(
        control=SimpleNamespace(value='alfa')
    ))
    assert composer.work_matches.visible
    assert [
        match.content.value for match in composer.work_matches.controls
    ] == ['Alfa: Introdução', 'Alfa: Estudos']
    assert matched_resource_ids == [1, 2]

    composer.work_matches.controls[0].on_click(SimpleNamespace())
    assert composer.work_search.value == 'Alfa: Introdução'
    assert not composer.work_matches.visible
    assert matched_resource_ids == [1]

    composer.work_search.value = 'ausente'
    composer._search_works(SimpleNamespace(
        control=SimpleNamespace(value='ausente')
    ))
    assert composer.work_matches.controls[0].value == (
        'Nenhuma obra encontrada.'
    )
    assert matched_resource_ids == []


def test_partial_work_controls_are_not_universal_in_form_specs():
    for spec in WORK_TYPES:
        keys = {field.key for field in spec.fields}
        if spec.key in {'journal_article', 'periodical_collection'}:
            assert 'is_partial' not in keys
            assert 'parent_bibliographic_resource_id' not in keys
        elif spec.key in PARTIAL_WORK_TYPES:
            assert 'is_partial' in keys
        else:
            assert 'is_partial' not in keys

    assert 'publication_place' in INHERITED_FROM_PARENT_FIELDS
    assert 'isbn' in INHERITED_FROM_PARENT_FIELDS
    assert 'issn' in INHERITED_FROM_PARENT_FIELDS


def test_periodical_partial_fields_are_specific_to_each_form():
    article = next(
        spec for spec in WORK_TYPES if spec.key == 'journal_article'
    )
    collection = next(
        spec for spec in WORK_TYPES if spec.key == 'periodical_collection'
    )
    article_fields = {field.key for field in article.fields}
    collection_fields = {field.key for field in collection.fields}

    assert {'part_start_page', 'part_end_page'} <= article_fields
    assert not {
        'is_partial',
        'part_volume',
        'part_chapter',
        'consult_start_year',
        'consult_end_year',
        'publisher',
        'collection_name',
    } & article_fields
    assert {
        'consult_start_year',
        'consult_end_year',
    } <= collection_fields
    assert 'publisher' in collection_fields
    assert not {
        'part_volume',
        'part_chapter',
        'part_start_page',
        'part_end_page',
    } & collection_fields


def test_partial_form_fields_match_each_part_reference_format():
    audio_part_keys = {
        field.key for field in PARTIAL_FIELDS_BY_TYPE['audio_document']
    }
    assert {
        'is_partial',
        'part_identifier',
        'part_responsibilities',
    } <= audio_part_keys
    assert not {
        'part_volume',
        'part_chapter',
        'part_start_page',
        'part_end_page',
    } & audio_part_keys

    score_part_keys = {
        field.key for field in PARTIAL_FIELDS_BY_TYPE['musical_score']
    }
    assert {'part_volume', 'part_start_page', 'part_end_page'} <= (
        score_part_keys
    )
    assert 'part_chapter' not in score_part_keys

    proceedings_part_keys = {
        field.key
        for field in PARTIAL_FIELDS_BY_TYPE['monographic_proceedings']
    }
    assert {'part_start_page', 'part_end_page'} <= proceedings_part_keys
    assert not {'part_volume', 'part_chapter'} & proceedings_part_keys

    collection = next(
        spec for spec in WORK_TYPES if spec.key == 'periodical_collection'
    )
    collection_keys = {field.key for field in collection.fields}
    assert {
        'title', 'authors', 'date_anchor', 'date_precision',
    }.isdisjoint(collection_keys)
    assert 'periodical_collection' in ALWAYS_PARTIAL_TYPES
    assert 'first_volume_year' in PARTIAL_FORM_FIELDS['periodical_collection']


@pytest.mark.parametrize(
    'work_type',
    ['monographic_proceedings', 'periodical_proceedings'],
)
def test_partial_proceedings_require_their_page_range(work_type):
    missing = WorkSubmissionController._missing_required_fields({
        'work_type': work_type,
        'title': 'Comunicação',
        'authors': ['Ana Silva'],
        'is_partial': True,
        'parent_bibliographic_resource_id': '1',
    })

    assert 'Página inicial da parte' in missing
    assert 'Página final da parte' in missing


def test_partial_monographic_proceedings_inherit_parent_publication_data():
    from src.db.db import SessionLocal
    from src.repositories import WorkRepository

    form_service = WorkFormService()
    with SessionLocal() as session:
        repository = WorkRepository(session)
        parent = repository.create(form_service.prepare_payload({
            'work_type': 'monographic_proceedings',
            'title': 'Anais do Congresso',
            'authors': [],
            'event_name': 'Congresso Brasileiro',
            'event_year': '2024',
            'publication_place': 'São Paulo',
            'publisher': 'Editora Acadêmica',
            'date_anchor': '2025',
        }))
        child = repository.create(form_service.prepare_payload({
            'work_type': 'monographic_proceedings',
            'title': 'Comunicação',
            'authors': ['Ana Silva'],
            'is_partial': True,
            'parent_bibliographic_resource_id': str(parent.id),
            'part_start_page': '10',
            'part_end_page': '18',
        }))

        child_work = child.specific_work
        parent_work = parent.specific_work
        assert child_work.is_partial
        assert child_work.event_name == parent_work.event_name
        assert child_work.event_year == parent_work.event_year
        assert child_work.publication_year == parent_work.publication_year
        assert child_work.display_year == parent_work.display_year


def test_periodical_proceedings_use_publication_date_and_inherit_part_data():
    from src.db.db import SessionLocal
    from src.domains import PeriodicalProceedings
    from src.repositories import WorkRepository
    from src.strategies.proceedings_formatter import ProceedingsFormatter

    form_service = WorkFormService()
    parent_payload = form_service.prepare_payload({
        'work_type': 'periodical_proceedings',
        'title': 'Anais do evento',
        'authors': [],
        'event_name': 'Congresso Brasileiro',
        'event_year': '2024',
        'publication_place': 'Brasília',
        'vol_or_year': '12',
        'number': '2',
        'start_page': '1',
        'end_page': '120',
        'publication_date': '16/10/2026',
    })
    assert parent_payload['work_data']['publication_year'] == 2026
    assert parent_payload['work_data']['date_anchor'] == date(2026, 10, 16)

    with SessionLocal() as session:
        repository = WorkRepository(session)
        parent = repository.create(parent_payload)
        child = repository.create(form_service.prepare_payload({
            'work_type': 'periodical_proceedings',
            'title': 'Comunicação',
            'authors': ['Ana Silva'],
            'is_partial': True,
            'parent_bibliographic_resource_id': str(parent.id),
            'part_start_page': '20',
            'part_end_page': '25',
        }))
        child_work = child.specific_work
        parent_work = parent.specific_work
        assert isinstance(child_work, PeriodicalProceedings)
        assert child_work.event_name == parent_work.event_name
        assert child_work.publication_date == parent_work.publication_date
        assert child_work.number == parent_work.number
        reference = ProceedingsFormatter.formatter(child)
        rendered = text_from_reference(reference)
        assert 'CONGRESSO BRASILEIRO' in rendered


def test_proceedings_online_references_require_and_format_access_date():
    from src.domains import PeriodicalProceedings
    from src.strategies.proceedings_formatter import ProceedingsFormatter

    work = PeriodicalProceedings(
        title='Anais do evento',
        event_name='Congresso Brasileiro',
        event_year=2024,
        publication_place='Brasília',
        vol_or_year=12,
        number=2,
        start_page='1',
        end_page='120',
        publication_date=date(2026, 10, 16),
        url='https://example.com/anais',
        viewed_at=datetime(2026, 10, 19),
    )
    resource = BibliographicResource(periodical_proceeding=work)

    rendered = text_from_reference(
        ProceedingsFormatter.formatter(resource)
    )
    assert 'Disponível em: https://example.com/anais.' in rendered
    assert 'Acesso em: 19 out. 2026.' in rendered

    work.viewed_at = None
    with pytest.raises(ValueError, match='data de acesso'):
        ProceedingsFormatter.formatter(resource)


def test_legal_documents_require_exact_date_and_publication_fields():
    statutes = next(spec for spec in WORK_TYPES if spec.key == 'statute')
    caselaw = next(spec for spec in WORK_TYPES if spec.key == 'caselaw')

    assert statutes.date_kind == 'date'
    assert caselaw.date_kind == 'date'


def test_legal_documents_accept_full_date_in_date_anchor():
    from src.controllers.core_controller import CoreController

    payload = WorkFormService(CoreNormalizer()).prepare_payload(
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

    parent_searches = []
    created_parent_types = []
    composer = WorkInsertModalComposer(
        DummyPage(),
        config,
        on_save=lambda data: True,
        search_authors=lambda q: [],
        search_works=lambda query, work_type: parent_searches.append(
            (query, work_type)
        ) or [],
        on_create_parent_work=lambda callback, work_type: (
            created_parent_types.append(work_type)
        ),
    )
    composer.selected = next(
        spec for spec in WORK_TYPES if spec.key == 'audiovisual_document'
    )
    composer.partial_enabled = False
    composer._render(update_page=False)
    assert composer.fields['preserve_title_spelling'].value is False
    composer.fields['preserve_title_spelling'].value = True
    assert composer._collect()['preserve_title_spelling'] is True

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

    composer.selected = next(
        spec for spec in WORK_TYPES if spec.key == 'journal_article'
    )
    composer.partial_enabled = True
    composer.parent_work_search = 'Revista'
    composer._render(update_page=False)
    parent_row = composer.form.controls[1].controls[0]

    assert 'is_partial' not in composer.fields
    assert {
        'part_start_page',
        'part_end_page',
    } <= set(composer.fields)
    assert not {
        'part_volume',
        'part_chapter',
        'consult_start_year',
        'consult_end_year',
        'publisher',
        'collection_name',
    } & set(composer.fields)
    assert isinstance(parent_row.controls[0], ft.Text)
    assert parent_row.controls[0].value == 'Revista *'
    assert parent_searches[-1] == ('Revista', 'magazine')

    composer._create_parent_work(None)
    assert created_parent_types == ['magazine']

    composer.selected = next(
        spec for spec in WORK_TYPES if spec.key == 'periodical_collection'
    )
    composer._render(update_page=False)
    assert {
        'consult_start_year',
        'consult_end_year',
    } <= set(composer.fields)
    assert not {
        'part_volume',
        'part_chapter',
        'part_start_page',
        'part_end_page',
    } & set(composer.fields)

    composer.selected = next(
        spec for spec in WORK_TYPES if spec.key == 'audio_document'
    )
    composer.partial_enabled = True
    composer.parent_work_search = 'Chico'
    composer._render(update_page=False)
    assert {
        'part_identifier',
        'part_responsibilities',
        'seconds',
        'physical_details',
    } <= set(composer.fields)
    assert not {
        'part_volume',
        'part_chapter',
        'part_start_page',
        'part_end_page',
        'date_anchor',
        'authors',
        'carrier_type',
    } & set(composer.fields)
    assert parent_searches[-1] == ('Chico', 'audio_document')


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
        'ASSIS, M. Memorias postumas de bras cubas. '
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
        'SILVA, A. M. Arquivos de leitura. 2024. 120 f. '
        'Dissertacao (Mestrado em Filosofia) — Universidade Federal, '
        'Curitiba, 2024'
    )


def test_monograph_without_author_capitalizes_first_significant_title_word():
    resource = BibliographicResource()
    resource.editorial_monograph = EditorialMonograph(
        title='de volta aos livros',
        date_anchor=date(2024, 1, 1),
        display_year='2024',
        responsibilities={},
        publication_place='Rio de Janeiro',
        publisher='Editora',
    )

    formatted = text_from_reference(MonographFormatter.formatter(resource))

    assert formatted.startswith('DE VOLTA aos livros.')


def test_journal_article_formatter_outputs_basic_abnt_reference():
    magazine_resource = BibliographicResource()
    magazine_resource.magazine = Magazine(
        title='Revista Brasileira de Estudos',
        publication_place='Sao Paulo',
    )
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
        parent_bibliographic_resource=magazine_resource,
        is_partial=True,
        publication_place='Sao Paulo',
        publisher='Editora X',
        number=2,
    )

    formatted = text_from_reference(PeriodicalFormatter.formatter(resource))

    assert formatted == (
        'SILVA, A. M. Leitura e memoria. '
        'Revista brasileira de estudos, Sao Paulo, n. 2, maio 2024.'
    )


def test_journal_article_date_is_month_and_year():
    payload = WorkFormService().prepare_payload({
        'work_type': 'journal_article',
        'title': 'Artigo',
        'date_anchor': '03/2025',
        'date_precision': 'Data exata',
        'number': '1',
    })
    date_anchor = payload['work_data']['date_anchor']

    assert date_anchor == date(2025, 3, 1)
    assert ABNTUtils.format_abbrev_month_year(date_anchor) == 'mar. 2025'

    with pytest.raises(ValueError, match='MM/AAAA'):
        WorkFormService().prepare_payload({
            'work_type': 'journal_article',
            'title': 'Artigo',
            'date_anchor': '15/03/2025',
            'date_precision': 'Data exata',
            'number': '1',
        })


def test_periodical_collection_formatter_uses_linked_magazine():
    magazine_resource = BibliographicResource()
    magazine_resource.magazine = Magazine(
        title='Revista Brasileira de Estudos',
        publication_place='Sao Paulo',
    )
    resource = BibliographicResource()
    resource.periodical_collection = PeriodicalCollection(
        title='Coleção consultada',
        parent_bibliographic_resource=magazine_resource,
        is_partial=True,
        first_volume_year=2018,
        publisher='[s.n.]',
    )

    formatted = text_from_reference(PeriodicalFormatter.formatter(resource))

    assert 'REVISTA brasileira de estudos' in formatted
    assert 'Sao Paulo: [s.n.], 2018.' in formatted


def test_natural_name_parser_handles_mononym():
    normalizer = CoreNormalizer()
    elements = normalizer.natural_name_parser('Platão')
    assert elements.given_names == ''
    assert elements.last_name == 'Platão'
    assert elements.given_names_initials == ''
    assert elements.last_name_initial == 'P'


def test_abnt_utils_fmt_authors_handles_mononym():
    author_platao = Author(
        given_names='',
        last_name='Platão',
        given_names_initials='',
        last_name_initial='P',
        corporation=False,
    )
    author_silva = Author(
        given_names='João',
        last_name='Silva',
        given_names_initials='J.',
        last_name_initial='S',
        corporation=False,
    )
    assert ABNTUtils.fmt_authors([author_platao]) == 'PLATÃO'
    assert (
        ABNTUtils.fmt_authors([author_platao, author_silva])
        == 'PLATÃO; SILVA, J.'
    )


def test_patent_formatter_with_author_spacing_and_single_dot():
    author = Author(
        given_names='João',
        last_name='Silva',
        given_names_initials='J.',
        last_name_initial='S',
        corporation=False,
    )
    work = Patent(
        title='Dispositivo de filtragem',
        applicant='Empresa Alpha',
        number='BR2024001',
        filing_date=date(2024, 3, 10),
    )
    BibliographicResource(authors=[author], patent=work)
    formatted = ''.join(
        part.content for part in PatentFormatter.formatter(work).parts
    )
    assert formatted.startswith('SILVA, J. Dispositivo de filtragem.')
    assert not formatted.startswith(' ')
    assert '..' not in formatted


def test_core_controller_format_reference_resilience_on_error(monkeypatch):
    resource = BibliographicResource()
    resource.editorial_monograph = EditorialMonograph(
        title='Livro com erro',
    )
    monkeypatch.setattr(
        MonographFormatter,
        'formatter',
        lambda _res: (_ for _ in ()).throw(ValueError('Erro simulado')),
    )
    result = CoreController.format_reference(resource)
    assert result is None


def test_core_controller_format_reference_dispatch_all_types():
    from src.domains import (
        AudiovisualDocument,
        VisualDocument,
        CartographicDocument,
        ThreeDimensionalDocument,
    )
    mag_r = BibliographicResource(
        magazine=Magazine(
            title='Revista X',
            publication_place='SP',
        )
    )

    resources = [
        BibliographicResource(
            editorial_monograph=EditorialMonograph(
                title='Monografia',
                publication_place='SP',
                publisher='Ed',
                display_year='2020',
            )
        ),
        BibliographicResource(
            academic_monograph=AcademicMonograph(
                title='Tese',
                publication_place='RJ',
                display_year='2021',
                thesis_type='Tese',
            )
        ),
        BibliographicResource(
            correspondence_monograph=CorrespondenceMonograph(
                title='Carta',
                publication_place='BH',
                display_year='2022',
            )
        ),
        BibliographicResource(
            periodical_collection=PeriodicalCollection(
                title='Coleção',
                parent_bibliographic_resource=mag_r,
                is_partial=True,
                first_volume_year=2015,
                publisher='Ed',
            )
        ),
        BibliographicResource(
            magazine=Magazine(
                title='Revista Científica',
                publication_place='Curitiba',
            )
        ),
        BibliographicResource(
            journal_article=JournalArticle(
                title='Artigo A',
                parent_bibliographic_resource=mag_r,
                is_partial=True,
                publisher='Ed',
                year_season=2023,
            )
        ),
        BibliographicResource(
            newspaper_article=NewspaperArticle(
                title='Notícia',
                journal_title='Jornal Hoje',
                publication_place='SP',
                date_anchor=date(2024, 1, 1),
                display_year='2024',
            )
        ),
        BibliographicResource(
            monographic_proceeding=MonographicProceedings(
                title='Anais',
                event_name='Congresso',
                event_number='1',
                event_year='2023',
                event_place='SP',
                publication_place='SP',
                publisher='Ed',
                publication_year='2023',
                display_year='2023',
                published=False,
            )
        ),
        BibliographicResource(
            periodical_proceeding=PeriodicalProceedings(
                title='Anais P',
                event_name='Simpósio',
                event_number='2',
                event_year='2023',
                event_place='RJ',
                publication_place='RJ',
                publisher='Ed',
                publication_year='2023',
                display_year='2023',
            )
        ),
        BibliographicResource(
            statute=Statute(
                title='Lei 123',
                promulgation_date=date(2024, 1, 1),
                publication_media='DOU',
                date_anchor=date(2024, 1, 2),
                display_year='2024',
            )
        ),
        BibliographicResource(
            caselaw=CaseLaw(
                title='Recurso Especial',
                publication_media='DJ',
                date_anchor=date(2024, 2, 1),
                display_year='2024',
            )
        ),
        BibliographicResource(
            miscellaneous_digital_document=MiscDigitalDocument(
                title='Doc Digital',
                publication_place='SP',
                display_year='2024',
            )
        ),
        BibliographicResource(
            audiovisual_document=AudiovisualDocument(
                title='Filme',
                carrier_type='DVD',
                publication_place='SP',
                publisher='Produtora',
                display_year='2020',
                seconds=5400,
                sound=True,
                colorized=True,
                responsibilities={},
            )
        ),
        BibliographicResource(
            audio_document=AudioDocument(
                title='Álbum',
                carrier_type='CD',
                publication_place='RJ',
                publisher='Gravadora',
                display_year='2019',
                responsibilities={},
                part_responsibilities={},
            )
        ),
        BibliographicResource(
            musical_score=MusicalScore(
                title='Partitura',
                publication_place='SP',
                publisher='Editora',
                display_year='2018',
                instrumentation='Piano',
            )
        ),
        BibliographicResource(
            visual_document=VisualDocument(
                title='Fotografia',
                display_year='2022',
            )
        ),
        BibliographicResource(
            cartographic_document=CartographicDocument(
                title='Mapa',
                publication_place='Brasília',
                publisher='IBGE',
                display_year='2021',
            )
        ),
        BibliographicResource(
            three_dimensional_document=ThreeDimensionalDocument(
                title='Escultura',
                manufacturing_place='SP',
                manufacturer='Ateliê',
                display_year='2023',
                physical_description='Bronze',
            )
        ),
        BibliographicResource(
            patent=Patent(
                title='Patente X',
                number='BR999',
                filing_date=date(2024, 1, 1),
                display_year='2024',
            )
        ),
    ]

    for res in resources:
        ref = CoreController.format_reference(res)
        assert ref is not None, f"Dispatch falhou para {res.specific_work}"
        assert len(ref.parts) > 0

    assert CoreController.format_reference(BibliographicResource()) is None
