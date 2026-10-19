from datetime import date

import pytest
from sqlalchemy import create_engine, text

from src.controllers.core_controller import CoreController
from src.controllers.work_submission_controller import (
    WorkSubmissionController,
)
from src.db import db as db_module
from src.domains import (
    Author,
    BibliographicResource,
    ThreeDimensionalDocument,
)
from src.services.work_form_service import WorkFormService
from src.strategies import ThreeDimensionalFormatter
from src.views.work_insert_specs import WORK_TYPES


def formatted_text(work: ThreeDimensionalDocument) -> str:
    return ''.join(
        part.content
        for part in ThreeDimensionalFormatter.formatter(work).parts
    )


def test_formats_three_dimensional_object_with_creator_and_notes():
    creator = Author(
        given_names='Cláudia',
        last_name='FRANÇA',
        given_names_initials='C.',
        last_name_initial='F.',
    )
    work = ThreeDimensionalDocument(
        title='Escada',
        display_year='1997',
        responsiblity_type='Criador',
        manufacturing_place='[s.l.]',
        manufacturer='[s.n.]',
        physical_description=(
            '1 escultura, estruturas tensionadas, color., '
            '400 x 250 x 250 cm'
        ),
        additional_notes='Coleção particular',
    )
    BibliographicResource(authors=[creator], three_dimensional_document=work)

    assert formatted_text(work) == (
        'FRANÇA, C. Escada. 1997. 1 escultura, estruturas tensionadas, '
        'color., 400 x 250 x 250 cm. Coleção particular.'
    )


def test_formats_object_without_named_creator_and_with_place():
    work = ThreeDimensionalDocument(
        title='Cadeira de Estado (dita de D. Afonso V)',
        display_year='[ca. 1470-1475]',
        responsiblity_type='',
        manufacturing_place='Portugal',
        manufacturer='[s.n.]',
        physical_description='1 cadeira em madeira de carvalho, '
        '180 x 68 x 52,5 cm',
    )

    assert formatted_text(work) == (
        'CADEIRA de Estado (dita de D. Afonso V). Portugal, '
        '[ca. 1470-1475]. 1 cadeira em madeira de carvalho, '
        '180 x 68 x 52,5 cm.'
    )


def test_uses_bracketed_fallback_if_object_has_no_title():
    work = ThreeDimensionalDocument(
        title='',
        display_year='[15--]',
        responsiblity_type='',
        manufacturing_place='Antuérpia',
        manufacturer='[s.n.]',
        physical_description='1 copo de vidro areado, 26 cm',
    )

    assert formatted_text(work).startswith(
        '[Objeto sem título]. Antuérpia, [15--].'
    )


def test_formats_online_object_and_requires_access_date():
    work = ThreeDimensionalDocument(
        title='Escultura digital',
        display_year='2020',
        responsiblity_type='',
        manufacturing_place='São Paulo',
        manufacturer='Museu',
        physical_description='1 modelo 3D, arquivo OBJ',
        url='https://example.com/escultura.obj',
        viewed_at=date(2020, 8, 4),
    )

    assert formatted_text(work).endswith(
        'Disponível em: https://example.com/escultura.obj. '
        'Acesso em: 4 ago. 2020.'
    )

    missing_access_date = ThreeDimensionalDocument(
        title='Escultura digital',
        display_year='2020',
        responsiblity_type='',
        physical_description='1 modelo 3D',
        url='https://example.com/escultura.obj',
    )
    with pytest.raises(
        ValueError,
        match='data de acesso para documentos tridimensionais on-line',
    ):
        ThreeDimensionalFormatter.formatter(missing_access_date)


def test_three_dimensional_form_and_controller_dispatch():
    spec = next(
        item for item in WORK_TYPES
        if item.key == 'three_dimensional_document'
    )
    fields = {field.key: field for field in spec.fields}
    assert fields['title'].required
    assert 'entre colchetes' in (fields['title'].hint or '')
    assert not fields['authors'].required
    assert fields['physical_description'].required

    form_data = {
        'work_type': 'three_dimensional_document',
        'title': '[Cadeira de carvalho]',
        'authors': [],
        'date_anchor': '1470',
        'manufacturing_place': 'Portugal',
        'physical_description': '1 cadeira em madeira de carvalho',
    }
    assert WorkSubmissionController._missing_required_fields(form_data) == []
    payload = WorkFormService().prepare_payload(form_data)
    work = ThreeDimensionalDocument(**payload['work_data'])
    resource = BibliographicResource(three_dimensional_document=work)

    reference = CoreController.format_reference(resource)
    assert reference is not None
    assert ''.join(part.content for part in reference.parts).startswith(
        '[CADEIRA de carvalho]. Portugal, 1470. '
        '1 cadeira em madeira de carvalho.'
    )


def test_existing_three_dimensional_table_gets_description_columns(
    monkeypatch,
):
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'CREATE TABLE three_dimensional_documents ('
            'id INTEGER PRIMARY KEY, bib_res_id INTEGER NOT NULL, '
            'title VARCHAR(150) NOT NULL, '
            'responsiblity_type VARCHAR(15) NOT NULL)'
        )
    monkeypatch.setattr(db_module, 'engine', engine)

    try:
        db_module._ensure_legacy_columns()
        with engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    text('PRAGMA table_info("three_dimensional_documents")')
                )
            }
        assert {
            'physical_description',
            'additional_notes',
        } <= columns
    finally:
        engine.dispose()
