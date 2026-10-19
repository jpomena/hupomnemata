from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.controllers.core_controller import CoreController
from src.controllers.work_submission_controller import (
    WorkSubmissionController,
)
from src.db.db import Base
from src.db import db as db_module
from src.domains import AudioDocument, Author, BibliographicResource
from src.repositories import WorkRepository
from src.strategies import AudioFormatter
from src.services.work_form_service import WorkFormService
from src.utils import TextStyle
from src.views.work_insert_specs import PARTIAL_WORK_TYPES, WORK_TYPES


def formatted_text(work: AudioDocument) -> str:
    parts = AudioFormatter.formatter(work).parts
    return ''.join(part.content for part in parts)


def test_formats_disc_with_responsibilities_and_physical_details():
    work = AudioDocument(
        title='Chico Buarque',
        responsibilities={'[Compositor]': 'Chico Buarque'},
        publication_place='Rio de Janeiro',
        publisher='Polygran',
        display_year='1984',
        carrier_type='disco vinil',
        seconds=17 * 60,
        physical_details='33 rpm, estéreo',
        part_responsibilities={},
    )

    assert formatted_text(work) == (
        'CHICO Buarque. [Compositor]: Chico Buarque. 1 disco vinil '
        '(17 min), 33 rpm, estéreo. Rio de Janeiro: Polygran, 1984.'
    )


def test_formats_audiobook_author_before_title():
    author = Author(
        given_names='Charles',
        last_name='DUHIGG',
        given_names_initials='C.',
        last_name_initial='D.',
    )
    work = AudioDocument(
        title='O poder do hábito',
        subtitle='porque fazemos o que fazemos',
        responsibilities={'Ledor': 'Francisco Ramos'},
        publication_place='Rio de Janeiro',
        publisher='Objetiva',
        display_year='2019',
        carrier_type='audiolivro',
        part_responsibilities={},
    )
    resource = BibliographicResource(authors=[author], audio_document=work)
    reference = CoreController.format_reference(resource)

    assert reference is not None
    assert reference.parts[0].content == 'DUHIGG, C. '
    assert ''.join(part.content for part in reference.parts) == (
        'DUHIGG, C. O poder do hábito: porque fazemos o que fazemos. '
        'Ledor: Francisco Ramos. 1 audiolivro. '
        'Rio de Janeiro: Objetiva, 2019.'
    )


def test_formats_online_podcast_with_access_date():
    work = AudioDocument(
        title='Você conhece os métodos contraceptivos?',
        responsibilities={
            'Entrevistada': 'Efigênia Maciel de Freitas',
            'Entrevistadora': 'Eliane Moreira',
        },
        publication_place='Uberlândia',
        publisher='DIRCO/UFU',
        display_year='2019',
        carrier_type='podcast',
        part_responsibilities={},
        url='https://example.com/podcast',
        viewed_at=date(2019, 8, 3),
    )

    assert formatted_text(work) == (
        'VOCÊ conhece os métodos contraceptivos? '
        'Entrevistada: Efigênia Maciel de Freitas. '
        'Entrevistadora: Eliane Moreira. Podcast. '
        'Uberlândia: DIRCO/UFU, 2019. '
        'Disponível em: https://example.com/podcast. '
        'Acesso em: 3 ago. 2019.'
    )


def test_formats_track_in_parent_recording_and_controller_dispatches():
    parent = AudioDocument(
        title='Chico Buarque',
        responsibilities={'[Compositor]': 'Chico Buarque'},
        publication_place='Rio de Janeiro',
        publisher='Polygran',
        display_year='1984',
        carrier_type='disco vinil',
        part_responsibilities={},
    )
    parent_resource = BibliographicResource(audio_document=parent)
    part = AudioDocument(
        title='Vai passar',
        responsibilities={},
        part_responsibilities={
            '[Intérpretes]': 'Francis Hime e Chico Buarque'
        },
        is_partial=True,
        parent_bibliographic_resource=parent_resource,
        part_identifier='lado 2, faixa 5',
        seconds=6 * 60 + 14,
        carrier_type='disco vinil',
    )
    resource = BibliographicResource(audio_document=part)
    reference = CoreController.format_reference(resource)

    assert reference is not None
    assert any(
        part.style == TextStyle.ITALIC and part.content == ' In: '
        for part in reference.parts
    )
    assert ''.join(part.content for part in reference.parts) == (
        'VAI passar. [Intérpretes]: Francis Hime e Chico Buarque. In: '
        'CHICO Buarque. [Compositor]: Chico Buarque. '
        '1 disco vinil, lado 2, faixa 5 (6 min 14 s). '
        'Rio de Janeiro: Polygran, 1984.'
    )


def test_audio_documents_are_configured_as_partial_works():
    audio_spec = next(
        spec for spec in WORK_TYPES if spec.key == 'audio_document'
    )

    assert 'audio_document' in PARTIAL_WORK_TYPES
    assert 'is_partial' in {field.key for field in audio_spec.fields}
    assert 'part_identifier' in {field.key for field in audio_spec.fields}
    authors_field = next(
        field for field in audio_spec.fields if field.key == 'authors'
    )
    assert not authors_field.required
    assert 'audiolivro' in authors_field.label


def test_audio_part_form_requires_parent_and_identifier():
    missing = WorkSubmissionController._missing_required_fields({
        'work_type': 'audio_document',
        'title': 'Faixa',
        'is_partial': True,
    })

    assert 'Obra-pai' in missing
    assert 'Identificador da parte' in missing
    assert 'Autores / responsáveis, separados por ponto e vírgula' not in missing


def test_complete_audio_form_requires_support_unless_it_is_online():
    missing = WorkSubmissionController._missing_required_fields({
        'work_type': 'audio_document',
        'title': 'Podcast',
        'date_anchor': '2019',
    })
    assert 'Tipo de suporte' in missing

    online_missing = WorkSubmissionController._missing_required_fields({
        'work_type': 'audio_document',
        'title': 'Podcast',
        'date_anchor': '2019',
        'url': 'https://example.com/podcast',
    })
    assert 'Tipo de suporte' not in online_missing
    assert 'Data de acesso' in online_missing


def test_online_audio_form_requires_a_url_for_streaming_carriers():
    missing = WorkSubmissionController._missing_required_fields({
        'work_type': 'audio_document',
        'title': 'Podcast',
        'date_anchor': '2019',
        'carrier_type': 'Podcast',
    })

    assert 'URL' in missing


def test_audio_part_is_created_with_parent_publication_data():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    form_service = WorkFormService()

    try:
        with Session(engine) as session:
            repository = WorkRepository(session)
            parent = repository.create(form_service.prepare_payload({
                'work_type': 'audio_document',
                'title': 'Chico Buarque',
                'responsibilities': {'[Compositor]': 'Chico Buarque'},
                'publication_place': 'Rio de Janeiro',
                'publisher': 'Polygran',
                'date_anchor': '1984',
                'date_precision': 'Data exata',
                'carrier_type': 'disco vinil',
                'authors': [],
            }))
            part_payload = form_service.prepare_payload({
                'work_type': 'audio_document',
                'title': 'Vai passar',
                'is_partial': True,
                'parent_bibliographic_resource_id': str(parent.id),
                'part_identifier': 'lado 2, faixa 5',
                'part_responsibilities': {
                    '[Intérpretes]': 'Francis Hime e Chico Buarque'
                },
                'seconds': str(6 * 60 + 14),
                'authors': [],
            })
            part = repository.create(part_payload)

            audio_part = part.specific_work
            assert isinstance(audio_part, AudioDocument)
            assert audio_part.is_partial
            assert audio_part.parent_bibliographic_resource_id == parent.id
            assert audio_part.carrier_type == 'disco vinil'
            assert audio_part.publication_place == 'Rio de Janeiro'
            assert audio_part.publisher == 'Polygran'
            assert audio_part.display_year == '1984'
            assert formatted_text(audio_part) == (
                'VAI passar. [Intérpretes]: Francis Hime e Chico Buarque. '
                'In: CHICO buarque. [Compositor]: Chico Buarque. '
                '1 disco vinil, lado 2, faixa 5 (6 min 14 s). '
                'Rio de Janeiro: Polygran, 1984.'
            )
    finally:
        engine.dispose()


def test_existing_audio_schema_gets_new_part_and_physical_columns(
    monkeypatch,
):
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'CREATE TABLE bibliographic_resources '
            '(id INTEGER PRIMARY KEY)'
        )
        connection.exec_driver_sql(
            'CREATE TABLE audio_documents '
            '(id INTEGER PRIMARY KEY, is_part BOOLEAN NOT NULL)'
        )
        connection.exec_driver_sql(
            'INSERT INTO audio_documents (id, is_part) VALUES (1, 1)'
        )
    monkeypatch.setattr(db_module, 'engine', engine)

    try:
        db_module._ensure_legacy_columns()

        with engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    'PRAGMA table_info("audio_documents")'
                )
            }
            partial_value = connection.exec_driver_sql(
                'SELECT is_partial FROM audio_documents WHERE id = 1'
            ).scalar_one()
        assert {
            'is_partial',
            'parent_bibliographic_resource_id',
            'seconds',
            'physical_details',
            'additional_notes',
        } <= columns
        assert 'is_part' not in columns
        assert partial_value == 1
    finally:
        engine.dispose()


def test_conflicting_specific_work_types_are_split_without_data_loss(
    monkeypatch,
):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'INSERT INTO bibliographic_resources (id) VALUES (1)'
        )
        connection.exec_driver_sql(
            "INSERT INTO audiovisual_documents "
            "(id, bib_res_id, title, display_year, responsibilities, "
            "date_precision, publication_place, publisher, carrier_type, "
            "seconds, sound, colorized, created_at) VALUES "
            "(1, 1, 'Filme', '2020', '{}', 'EXACT', '[s.l.]', '[s.n.]', "
            "'DVD', 60, 1, 1, CURRENT_TIMESTAMP)"
        )
        connection.exec_driver_sql(
            "INSERT INTO magazines "
            "(id, bib_res_id, title, display_year, publication_place, "
            "date_precision, created_at) "
            "VALUES (1, 1, 'Revista', '2020', 'São Paulo', 'EXACT', "
            "CURRENT_TIMESTAMP)"
        )
    monkeypatch.setattr(db_module, 'engine', engine)

    try:
        db_module._split_resources_with_multiple_work_types()
        db_module._split_resources_with_multiple_work_types()

        with engine.connect() as connection:
            audiovisual_resource_id = connection.exec_driver_sql(
                'SELECT bib_res_id FROM audiovisual_documents'
            ).scalar_one()
            magazine_resource_id = connection.exec_driver_sql(
                'SELECT bib_res_id FROM magazines'
            ).scalar_one()
            resource_count = connection.exec_driver_sql(
                'SELECT COUNT(*) FROM bibliographic_resources'
            ).scalar_one()
        assert audiovisual_resource_id != magazine_resource_id
        assert magazine_resource_id == 1
        assert audiovisual_resource_id != 1
        assert resource_count == 2
    finally:
        engine.dispose()


def test_online_audio_requires_url_and_access_date():
    work = AudioDocument(
        title='Podcast',
        responsibilities={},
        publication_place='Uberlândia',
        publisher='UFU',
        display_year='2026',
        carrier_type='podcast',
        part_responsibilities={},
    )

    with pytest.raises(ValueError, match='URL'):
        AudioFormatter.formatter(work)

    work.url = 'https://example.com/podcast'
    with pytest.raises(ValueError, match='data de acesso'):
        AudioFormatter.formatter(work)
