from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.controllers.core_controller import CoreController
from src.controllers.work_submission_controller import (
    WorkSubmissionController,
)
from src.db import db as db_module
from src.db.db import Base
from src.domains import (
    Author,
    BibliographicResource,
    MusicalScore,
)
from src.repositories import WorkRepository
from src.services.work_form_service import WorkFormService
from src.strategies import MusicalScoreFormatter
from src.utils import TextStyle
from src.services.work_form_service import WorkFormService
from src.views.work_insert_specs import PARTIAL_WORK_TYPES, WORK_TYPES


def formatted_text(resource: BibliographicResource) -> str:
    reference = MusicalScoreFormatter.formatter(resource)
    return ''.join(part.content for part in reference.parts)


def test_formats_printed_score_with_composer_and_instrumentation():
    composer = Author(
        given_names='Ludwig van',
        last_name='BEETHOVEN',
        given_names_initials='L. v.',
        last_name_initial='B.',
    )
    work = MusicalScore(
        title='Streichquartett Es-dur',
        subtitle='Opus 127 = String quartet in E flat major: op. 127',
        instrumentation='Música de câmara',
        publication_place='München',
        publisher='G. Henle',
        display_year='c2003',
        physical_description='4 partes',
    )
    resource = BibliographicResource(
        authors=[composer],
        musical_score=work,
    )

    assert formatted_text(resource) == (
        'BEETHOVEN, L. v. Streichquartett Es-dur: Opus 127 = '
        'String quartet in E flat major: op. 127. Música de câmara. '
        'München: G. Henle, c2003. 4 partes.'
    )


def test_formats_part_of_a_score_collection_with_italic_in_marker():
    editor = Author(
        given_names='Robert L.',
        last_name='LARSEN',
        given_names_initials='R. L.',
        last_name_initial='L.',
    )
    composer = Author(
        given_names='Gaetano',
        last_name='DONIZETTI',
        given_names_initials='G.',
        last_name_initial='D.',
    )
    parent = MusicalScore(
        title='Arias for baritone',
        instrumentation='Canto',
        author_role='comp.',
        publication_place='New York',
        publisher='G. Schirmer',
        display_year='c1991',
    )
    parent_resource = BibliographicResource(
        authors=[editor],
        musical_score=parent,
    )
    part = MusicalScore(
        title='Don Pasquale',
        subtitle='Bella siccome un Angelo',
        is_partial=True,
        parent_bibliographic_resource=parent_resource,
        part_start_page='96',
        part_end_page='99',
    )
    resource = BibliographicResource(
        authors=[composer],
        musical_score=part,
    )

    reference = MusicalScoreFormatter.formatter(resource)
    assert any(
        part.content == ' In: ' and part.style == TextStyle.ITALIC
        for part in reference.parts
    )
    assert ''.join(part.content for part in reference.parts) == (
        'DONIZETTI, G. Don Pasquale: Bella siccome un Angelo. '
        'In: LARSEN, R. L. (comp.). Arias for baritone. Canto. '
        'New York: G. Schirmer, c1991. p. 96-99.'
    )


def test_formats_online_score_and_requires_access_date():
    work = MusicalScore(
        title='Seductor',
        subtitle='tango',
        instrumentation='Piano',
        publication_place='Rio de Janeiro',
        publisher='Imperial Estabelecimento de Piano',
        display_year='[19--?]',
        physical_description='3 p. de música',
        url='https://example.com/seductor.pdf',
        viewed_at=date(2019, 8, 4),
    )
    resource = BibliographicResource(musical_score=work)

    assert formatted_text(resource).endswith(
        '3 p. de música. Disponível em: https://example.com/seductor.pdf. '
        'Acesso em: 4 ago. 2019.'
    )

    missing_access_date = MusicalScore(
        title='Seductor',
        instrumentation='Piano',
        publication_place='Rio de Janeiro',
        publisher='Imperial Estabelecimento de Piano',
        display_year='[19--?]',
        url='https://example.com/seductor.pdf',
    )
    with pytest.raises(
        ValueError,
        match='data de acesso para partituras on-line',
    ):
        MusicalScoreFormatter.formatter(
            BibliographicResource(musical_score=missing_access_date)
        )


def test_form_accepts_the_publication_year_as_printed_on_score():
    payload = WorkFormService().prepare_payload({
        'work_type': 'musical_score',
        'title': 'Obras para violão solo',
        'authors': ['Waldir Azevedo'],
        'date_anchor': 'c2003',
    })

    assert payload['work_data']['display_year'] == 'c2003'
    assert payload['work_data']['date_anchor'] == date(2003, 1, 1)


def test_musical_score_is_partial_and_controller_dispatches_formatter():
    score_spec = next(
        spec for spec in WORK_TYPES if spec.key == 'musical_score'
    )
    field_labels = {
        field.key: field.label for field in score_spec.fields
    }
    work = MusicalScore(
        title='Obras para violão solo',
        instrumentation='Violão',
        publication_place='[s.l.]',
        publisher='[s.n.]',
        display_year='[200-]',
    )
    resource = BibliographicResource(musical_score=work)

    assert 'musical_score' in PARTIAL_WORK_TYPES
    assert field_labels['authors'] == 'Compositor(es), se houver'
    assert 'physical_description' in field_labels
    assert 'date_anchor' in field_labels
    assert 'display_year' not in field_labels
    assert 'date_precision' not in field_labels
    reference = CoreController.format_reference(resource)
    assert reference is not None
    assert ''.join(part.content for part in reference.parts).startswith(
        'OBRAS para violão solo.'
    )


def test_form_and_repository_create_score_part_with_parent_link():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    form_service = WorkFormService()

    try:
        with Session(engine) as session:
            repository = WorkRepository(session)
            parent = repository.create(form_service.prepare_payload({
                'work_type': 'musical_score',
                'title': 'Arias for baritone',
                'authors': ['Robert Larsen'],
                'author_role': 'comp.',
                'instrumentation': 'Canto',
                'publication_place': 'New York',
                'publisher': 'G. Schirmer',
                'date_anchor': 'c1991',
            }))
            part = repository.create(form_service.prepare_payload({
                'work_type': 'musical_score',
                'title': 'Don Pasquale',
                'subtitle': 'Bella siccome un Angelo',
                'authors': ['Gaetano Donizetti'],
                'is_partial': True,
                'parent_bibliographic_resource_id': str(parent.id),
                'part_start_page': '96',
                'part_end_page': '99',
            }))

            child_work = part.specific_work
            assert isinstance(child_work, MusicalScore)
            assert child_work.is_partial
            assert child_work.parent_bibliographic_resource_id == parent.id
            assert child_work.publication_place == 'New York'
            assert child_work.publisher == 'G. Schirmer'
            assert child_work.display_year == 'c1991'
            assert formatted_text(part).startswith(
                'DONIZETTI, G. Don pasquale: Bella siccome un Angelo. '
                'In: LARSEN, R. (comp.). Arias for baritone. Canto.'
            )
            assert formatted_text(part).endswith(
                'New York: G. Schirmer, c1991. p. 96-99.'
            )
    finally:
        engine.dispose()


def test_score_part_form_does_not_require_publication_date():
    missing = WorkSubmissionController._missing_required_fields({
        'work_type': 'musical_score',
        'title': 'Parte',
        'authors': ['Compositor'],
        'is_partial': True,
        'parent_bibliographic_resource_id': '1',
    })

    assert 'Ano de publicação (ou estimado)' not in missing
    assert 'Obra-pai' not in missing


def test_existing_musical_score_table_receives_partial_and_reference_fields(
    monkeypatch,
):
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'CREATE TABLE musical_scores ('
            'id INTEGER PRIMARY KEY, bib_res_id INTEGER NOT NULL, '
            'title VARCHAR(150) NOT NULL, instrumentation VARCHAR(50) NOT '
            'NULL, publication_place VARCHAR(150) NOT NULL, '
            'publisher VARCHAR(100) NOT NULL)'
        )
    monkeypatch.setattr(db_module, 'engine', engine)

    try:
        db_module._ensure_legacy_columns()
        with engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    text('PRAGMA table_info("musical_scores")')
                )
            }
        assert {
            'is_partial',
            'parent_bibliographic_resource_id',
            'part_start_page',
            'part_end_page',
            'author_role',
            'physical_description',
        } <= columns
    finally:
        engine.dispose()
