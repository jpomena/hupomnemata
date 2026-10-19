from datetime import date

import pytest
from sqlalchemy import create_engine, text

from src.controllers.core_controller import CoreController
from src.controllers.work_submission_controller import (
    WorkSubmissionController,
)
from src.db import db as db_module
from src.domains import Author, BibliographicResource, VisualDocument
from src.services.work_form_service import WorkFormService
from src.strategies import VisualFormatter
from src.views.work_insert_specs import WORK_TYPES


def formatted_text(work: VisualDocument) -> str:
    return ''.join(
        part.content for part in VisualFormatter.formatter(work).parts
    )


def test_formats_visual_document_with_author_and_additional_notes():
    author = Author(
        given_names='Rosaly',
        last_name='SENRA',
        given_names_initials='R.',
        last_name_initial='S.',
    )
    work = VisualDocument(
        title='Escada',
        display_year='1997',
        physical_description='3 fotografias, color., 10 cm x 8 cm',
        additional_notes='Fotografias da escultura de Cláudia França',
    )
    BibliographicResource(authors=[author], visual_document=work)

    assert formatted_text(work) == (
        'SENRA, R. Escada. 1997. 3 fotografias, color., 10 cm x 8 cm. '
        'Fotografias da escultura de Cláudia França.'
    )


def test_formats_untitled_visual_document_without_author():
    work = VisualDocument(
        title='',
        display_year='1986',
        physical_description='1 fotografia, p&b, 12 cm x 8 cm',
    )

    assert formatted_text(work) == (
        '[Sem título]. 1986. 1 fotografia, p&b, 12 cm x 8 cm.'
    )


def test_capitalizes_first_non_particle_word_without_author():
    work = VisualDocument(
        title='a escada de madeira',
        display_year='1997',
        physical_description='1 fotografia, color.',
    )

    assert formatted_text(work).startswith('A ESCADA de madeira.')


def test_formats_online_visual_document_and_requires_access_date():
    work = VisualDocument(
        title='Gravuras rupestres',
        subtitle='Paleolítico: Penascosa: Foz Côa: Portugal',
        display_year='1998',
        physical_description='1 gravura, color.',
        url='https://example.com/gravura.jpg',
        viewed_at=date(2019, 8, 4),
    )

    assert formatted_text(work) == (
        'GRAVURAS rupestres: Paleolítico: Penascosa: Foz Côa: Portugal. '
        '1998. 1 gravura, color. Disponível em: '
        'https://example.com/gravura.jpg. Acesso em: 4 ago. 2019.'
    )

    missing_access_date = VisualDocument(
        title='Cartaz',
        display_year='[2019]',
        physical_description='1 cartaz, color.',
        url='https://example.com/cartaz.jpg',
    )
    with pytest.raises(
        ValueError,
        match='data de acesso para documentos visuais on-line',
    ):
        VisualFormatter.formatter(missing_access_date)


def test_visual_form_allows_missing_title_and_author_but_requires_support():
    spec = next(
        item for item in WORK_TYPES if item.key == 'visual_document'
    )
    fields = {field.key: field for field in spec.fields}
    form_data = {
        'work_type': 'visual_document',
        'title': '',
        'authors': [],
        'date_anchor': '1986',
        'physical_description': '1 fotografia, p&b, 12 cm x 8 cm',
    }

    assert not fields['title'].required
    assert not fields['authors'].required
    assert fields['physical_description'].required
    assert WorkSubmissionController._missing_required_fields(form_data) == []
    form_data.pop('physical_description')
    assert 'Especificação do suporte' in (
        WorkSubmissionController._missing_required_fields(form_data)
    )


def test_visual_form_stores_missing_title_as_sem_titulo_and_controller_dispatches():
    payload = WorkFormService().prepare_payload({
        'work_type': 'visual_document',
        'title': ' ',
        'authors': [],
        'date_anchor': '1986',
        'date_precision': 'Data exata',
        'physical_description': '1 fotografia, p&b, 12 cm x 8 cm',
    })
    work = VisualDocument(**payload['work_data'])
    resource = BibliographicResource(visual_document=work)

    assert payload['work_data']['title'] == '[Sem título]'
    reference = CoreController.format_reference(resource)
    assert reference is not None
    assert ''.join(part.content for part in reference.parts) == (
        '[Sem título]. 1986. 1 fotografia, p&b, 12 cm x 8 cm.'
    )


def test_online_visual_form_requires_access_date():
    assert WorkSubmissionController._missing_required_fields({
        'work_type': 'visual_document',
        'title': 'Gravura',
        'date_anchor': '1998',
        'physical_description': '1 gravura, color.',
        'url': 'https://example.com/gravura.jpg',
    }) == ['Data de acesso']


def test_existing_visual_table_gets_description_columns(monkeypatch):
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'CREATE TABLE visual_documents ('
            'id INTEGER PRIMARY KEY, bib_res_id INTEGER NOT NULL, '
            'title VARCHAR(150) NOT NULL)'
        )
    monkeypatch.setattr(db_module, 'engine', engine)

    try:
        db_module._ensure_legacy_columns()
        with engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    text('PRAGMA table_info("visual_documents")')
                )
            }
        assert {
            'physical_description',
            'additional_notes',
        } <= columns
    finally:
        engine.dispose()
