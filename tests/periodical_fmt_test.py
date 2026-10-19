import sys
from datetime import date, datetime
from pathlib import Path

projeto_raiz = str(Path(__file__).parent.parent)
if projeto_raiz not in sys.path:
    sys.path.insert(0, projeto_raiz)

from src.domains import (  # noqa
    Author,
    Magazine,
    PeriodicalCollection,
    JournalArticle,
    NewspaperArticle,
    BibliographicResource
)
from src.strategies import PeriodicalFormatter  # noqa
from src.utils import TextStyle  # noqa


def run_test():
    # Autor do artigo de periódico
    author_1 = Author(last_name='SILVA', given_names_initials='J. M.')
    author_2 = Author(last_name='SANTOS', given_names_initials='A. B.')
    author_3 = Author(last_name='OLIVEIRA', given_names_initials='C. R.')

    authors = [author_1, author_2, author_3]

    # Cenário: Artigo de Revista Científica (JournalArticle)
    magazine_resource = BibliographicResource(
        magazine=Magazine(
            title='Revista Brasileira de História',
            publication_place='São Paulo',
        )
    )
    article = JournalArticle(
        title='A história econômica do período colonial',
        parent_bibliographic_resource=magazine_resource,
        is_partial=True,
        publication_place='São Paulo',
        publisher='ANPUH',
        volume=40,
        number=85,
        year_season=2020,
        date_anchor=date(2020, 5, 15),
        issn='0102-0188',
        url='https://example.com/artigo',
        viewed_at=datetime(2026, 6, 1),
        part_start_page='120',
        part_end_page='135',
    )

    resource = BibliographicResource(
        authors=authors,
        journal_article=article,
    )

    # Executa o formatador de periódicos
    view_reference = PeriodicalFormatter.formatter(resource)

    # Imprime o resultado simulando a renderização no terminal
    print('\n=== RESULTADO DA REFERÊNCIA (PERIÓDICO) ===')

    texto_final = ''
    for part in view_reference.parts:
        texto = part.content

        if part.style == TextStyle.BOLD:
            texto_final += f'\033[1m{texto}\033[0m'  # Negrito no terminal
        elif part.style == TextStyle.ITALIC:
            texto_final += f'\033[3m{texto}\033[0m'  # Itálico no terminal
        else:
            texto_final += texto

    print(texto_final)
    print('===========================================\n')


if __name__ == '__main__':
    run_test()
