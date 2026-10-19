from datetime import date

import pytest
from sqlalchemy import create_engine, text

from src.controllers.core_controller import CoreController
from src.controllers.work_submission_controller import (
    WorkSubmissionController,
)
from src.db import db as db_module
from src.domains import Author, BibliographicResource, CartographicDocument
from src.services.work_form_service import WorkFormService
from src.strategies import CartographicFormatter
from src.views.work_insert_specs import WORK_TYPES


def formatted_text(work: CartographicDocument) -> str:
    return ''.join(
        part.content for part in CartographicFormatter.formatter(work).parts
    )


def test_formats_atlas_with_author_and_physical_description():
    author = Author(
        given_names='Carlos R. S.',
        last_name='MILANI',
        given_names_initials='C. R. S.',
        last_name_initial='M.',
    )
    work = CartographicDocument(
        title='Atlas da política externa brasileira',
        display_year='2015',
        publication_place='Rio de Janeiro',
        publisher='Ed. UERJ; Buenos Aires: CLACSO',
        physical_description='xiv, 135 p., il. col., 30 cm',
    )
    BibliographicResource(authors=[author], cartographic_document=work)

    assert formatted_text(work) == (
        'MILANI, C. R. S. Atlas da política externa brasileira. '
        'Rio de Janeiro: Ed. UERJ; Buenos Aires: CLACSO, 2015. '
        'xiv, 135 p., il. col., 30 cm.'
    )


def test_formats_map_with_subtitle_edition_and_complementary_details():
    work = CartographicDocument(
        title='Mapa do sistema rodoviário',
        subtitle='Espírito Santo',
        edition=2,
        display_year='2016',
        publication_place='[Vitória]',
        publisher='DER-ES',
        physical_description='1 mapa, color.',
        additional_notes='Escala 1:500.000',
    )

    assert formatted_text(work) == (
        'MAPA do sistema rodoviário: Espírito Santo. 2. ed. [Vitória]: '
        'DER-ES, 2016. 1 mapa, color. Escala 1:500.000.'
    )


def test_capitalizes_first_non_particle_word_without_author():
    work = CartographicDocument(
        title='de outro lado',
        display_year='2016',
        publication_place='Vitória',
        publisher='DER-ES',
    )

    assert formatted_text(work).startswith('DE OUTRO lado.')


def test_formats_online_map_and_requires_access_date():
    work = CartographicDocument(
        title='Araguari, Minas Gerais',
        display_year='2019',
        publication_place='São José dos Campos',
        publisher='INPE',
        physical_description='1 imagem de satélite, color.',
        additional_notes='Satélite LANDSAT-8, Sensor OLI. Lat. -18.649.',
        url='https://example.com/mapa',
        viewed_at=date(2019, 8, 15),
    )

    assert formatted_text(work).endswith(
        'Disponível em: https://example.com/mapa. '
        'Acesso em: 15 ago. 2019.'
    )

    missing_access_date = CartographicDocument(
        title='Mapa on-line',
        display_year='2019',
        publication_place='[s.l.]',
        publisher='[s.n.]',
        physical_description='1 mapa.',
        url='https://example.com/mapa',
    )
    with pytest.raises(
        ValueError,
        match='data de acesso para documentos cartográficos on-line',
    ):
        CartographicFormatter.formatter(missing_access_date)


def test_cartographic_form_requires_physical_description_and_access_date():
    spec = next(
        item for item in WORK_TYPES
        if item.key == 'cartographic_document'
    )
    physical_field = next(
        field for field in spec.fields
        if field.key == 'physical_description'
    )
    assert physical_field.required

    form_data = {
        'work_type': 'cartographic_document',
        'title': 'Mapa',
        'authors': ['Instituto Cartográfico'],
        'date_anchor': '2019',
        'physical_description': '1 mapa, color.',
        'url': 'https://example.com/mapa',
    }
    assert WorkSubmissionController._missing_required_fields(form_data) == [
        'Data de acesso'
    ]
    form_data['viewed_at'] = '15/08/2019'
    assert WorkSubmissionController._missing_required_fields(form_data) == []


def test_form_payload_and_controller_dispatch_cartographic_formatter():
    payload = WorkFormService().prepare_payload({
        'work_type': 'cartographic_document',
        'title': 'Mapa',
        'authors': [],
        'date_anchor': '2019',
        'date_precision': 'Data exata',
        'physical_description': '1 mapa, color.',
        'edition': '2',
        'publication_place': 'São Paulo',
        'publisher': 'Editora',
    })
    assert payload['work_data']['edition'] == 2

    work = CartographicDocument(**payload['work_data'])
    resource = BibliographicResource(cartographic_document=work)
    reference = CoreController.format_reference(resource)
    assert reference is not None
    assert ''.join(part.content for part in reference.parts).startswith(
        'MAPA. 2. ed. São Paulo: Editora, 2019. 1 mapa, color.'
    )


def test_existing_cartographic_table_gets_physical_description_column(
    monkeypatch,
):
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'CREATE TABLE cartographic_documents ('
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
                    text('PRAGMA table_info("cartographic_documents")')
                )
            }
        assert {
            'edition',
            'physical_description',
            'additional_notes',
        } <= columns
    finally:
        engine.dispose()
