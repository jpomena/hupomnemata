from datetime import date

import pytest

from src.controllers.core_controller import CoreController
from src.controllers.work_submission_controller import (
    WorkSubmissionController,
)
from src.domains import AudiovisualDocument, BibliographicResource
from src.strategies import AudiovisualFormatter
from src.utils import TextStyle
from src.views.work_insert_specs import WORK_TYPES


def formatted_text(work: AudiovisualDocument) -> str:
    parts = AudiovisualFormatter.formatter(work).parts
    return ''.join(part.content for part in parts)


def test_formats_film_reference():
    work = AudiovisualDocument(
        title='Bagdad Café',
        responsibilities={'Direção': 'Percy Adlon'},
        publication_place='Alemanha',
        publisher='Paris Vídeo Filmes',
        display_year='1988',
        carrier_type='filme',
        seconds=96 * 60,
        sound=True,
        colorized=True,
    )

    reference = AudiovisualFormatter.formatter(work)

    assert reference.parts[0].content == 'BAGDAD Café'
    assert reference.parts[0].style == TextStyle.NORMAL
    assert formatted_text(work) == (
        'BAGDAD Café. Direção: Percy Adlon. Alemanha: Paris Vídeo Filmes, '
        '1988. 1 filme (96 min), son., color.'
    )


@pytest.mark.parametrize(
    ('title', 'formatted_title'),
    [
        ('O prisioneiro da grade de ferro', 'O PRISIONEIRO da grade de ferro'),
        ('O gato de botas', 'O GATO de botas'),
    ],
)
def test_capitalizes_word_after_initial_particle(title, formatted_title):
    assert AudiovisualFormatter._format_title(title) == formatted_title


def test_formats_subtitle_notes_and_online_reference():
    work = AudiovisualDocument(
        title='Tecnologia para a educação',
        subtitle='uma experiência',
        responsibilities={},
        publication_place='Brasília, DF',
        publisher='UnBTV',
        display_year='2014',
        carrier_type='vídeo',
        seconds=2 * 60 + 43,
        sound=False,
        colorized=False,
        additional_notes='Publicado por UnBTV',
        url='https://example.com/video',
        viewed_at=date(2026, 10, 19),
    )

    assert formatted_text(work) == (
        'TECNOLOGIA para a educação: uma experiência. Brasília, DF: UnBTV, '
        '2014. 1 vídeo (2 min 43 s), p&b. Publicado por UnBTV. '
        'Disponível em: https://example.com/video. Acesso em: 19 out. 2026.'
    )


def test_formats_duration_in_minutes_and_seconds():
    work = AudiovisualDocument(
        title='Currículo Lattes',
        responsibilities={},
        publication_place='Natal',
        publisher='UFRN',
        display_year='2020',
        carrier_type='vídeo',
        seconds=4 * 3600 + 9 * 60 + 23,
        sound=True,
        colorized=True,
    )

    assert '(249 min 23 s)' in formatted_text(work)


def test_controller_selects_multimedia_formatter():
    work = AudiovisualDocument(
        title='Concorrência desleal',
        responsibilities={},
        publication_place='Roma',
        publisher='Warner Bros',
        display_year='2000',
        carrier_type='DVD',
        seconds=106 * 60,
        sound=True,
        colorized=True,
    )
    resource = BibliographicResource(audiovisual_document=work)

    reference = CoreController.format_reference(resource)

    assert reference is not None
    assert ''.join(part.content for part in reference.parts).startswith(
        'CONCORRÊNCIA desleal.'
    )


def test_audiovisual_form_uses_responsibilities_not_generic_authors():
    spec = next(
        item for item in WORK_TYPES
        if item.key == 'audiovisual_document'
    )
    fields = {field.key: field for field in spec.fields}

    assert 'authors' not in fields
    assert fields['responsibilities'].kind == 'responsibilities'
    assert fields['responsibilities'].label.startswith(
        'Responsabilidades (direção'
    )

    assert WorkSubmissionController._missing_required_fields({
        'work_type': 'audiovisual_document',
        'title': 'Filme',
        'date_anchor': '2020',
        'carrier_type': 'DVD',
        'seconds': '3600',
        'publication_place': 'São Paulo',
        'publisher': 'Produtora',
    }) == []


def test_audiovisual_form_requires_access_date_for_online_references():
    missing = WorkSubmissionController._missing_required_fields({
        'work_type': 'audiovisual_document',
        'title': 'Filme',
        'date_anchor': '2020',
        'carrier_type': 'vídeo',
        'seconds': '3600',
        'url': 'https://example.com/filme',
    })

    assert 'Data de acesso' in missing


def test_audiovisual_formatter_rejects_online_reference_without_access_date():
    work = AudiovisualDocument(
        title='Filme',
        display_year='2020',
        responsibilities={},
        publication_place='[s.l.]',
        publisher='[s.n.]',
        carrier_type='vídeo',
        seconds=120,
        sound=True,
        colorized=True,
        url='https://example.com/filme',
    )

    with pytest.raises(ValueError, match='data de acesso'):
        AudiovisualFormatter.formatter(work)
