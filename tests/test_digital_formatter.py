from datetime import datetime

from src.domains import Author, BibliographicResource, MiscDigitalDocument
from src.strategies import DigitalFormatter
from src.utils import TextStyle


def test_digital_formatter_without_author():
    work = MiscDigitalDocument(
        title='Python Software Foundation Documentation',
        publication_place='Wilmington',
        display_year='2024',
    )
    BibliographicResource(miscellaneous_digital_document=work)
    ref = DigitalFormatter.formatter(work)
    parts = ref.parts
    formatted_text = ''.join(p.content for p in parts)

    assert formatted_text == (
        'PYTHON Software Foundation Documentation. Wilmington, 2024.'
    )
    # Títulos de documentos digitais não recebem realce tipográfico (ABNT)
    title_part = next(
        p for p in parts if 'Documentation' in p.content
    )
    assert title_part.style == TextStyle.NORMAL


def test_digital_formatter_with_author_and_subtitle():
    author = Author(
        given_names='Guido',
        last_name='van Rossum',
        given_names_initials='G.',
        last_name_initial='R',
    )
    work = MiscDigitalDocument(
        title='Tutorial Python',
        subtitle='uma introdução prática',
        publication_place='Amsterdã',
        display_year='2023',
    )
    BibliographicResource(
        authors=[author],
        miscellaneous_digital_document=work,
    )

    ref = DigitalFormatter.formatter(work)
    formatted_text = ''.join(p.content for p in ref.parts)

    assert formatted_text == (
        'VAN ROSSUM, G. Tutorial Python: uma introdução prática. '
        'Amsterdã, 2023.'
    )
    title_part = next(p for p in ref.parts if 'Tutorial Python' in p.content)
    assert title_part.style == TextStyle.NORMAL


def test_digital_formatter_full_options():
    work = MiscDigitalDocument(
        title='Base de Dados Bibliográficos',
        version='Versão 2.1',
        publication_place='Brasília',
        display_year='2025',
        additional_notes='Base de dados em acesso aberto',
        url='https://example.org/base',
        viewed_at=datetime(2025, 6, 15, 10, 0),
    )
    BibliographicResource(miscellaneous_digital_document=work)

    ref = DigitalFormatter.formatter(work)
    formatted_text = ''.join(p.content for p in ref.parts)

    assert formatted_text == (
        'BASE de Dados Bibliográficos. Versão 2.1. Brasília, 2025. '
        'Base de dados em acesso aberto. '
        'Disponível em: https://example.org/base. Acesso em: 15 jun. 2025.'
    )


def test_digital_formatter_preserves_title_spelling_when_enabled():
    work = MiscDigitalDocument(
        title='e-Gov: portal de serviços',
        preserve_title_spelling=True,
        publication_place='Brasília',
        display_year='2024',
    )
    BibliographicResource(miscellaneous_digital_document=work)

    ref = DigitalFormatter.formatter(work)
    formatted_text = ''.join(p.content for p in ref.parts)

    assert formatted_text.startswith('E-GOV: portal de serviços.')
