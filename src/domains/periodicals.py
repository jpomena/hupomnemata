from .core_domain import WorkMixin, PartialWorkMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

'''Uma publicação periódica é uma obra editada em qualquer tipo
de suporte, em unidades físicas sequenciais, com identificações
numéricas e/ou cronológicas, elaborada sob a responsabilidade de um
grupo editorial. As publicações periódicas mais comuns são jornais e
revistas. São constituídas de fascículos, números ou partes, e tratam de
assuntos variados, de acordo com um plano definido.
'''


class PeriodicalCollection(PartialWorkMixin, WorkMixin):
    '''Coleção completa ou parcial de uma publicação periódica.'''

    __tablename__ = 'periodical_collections'

    first_volume_year: Mapped[int] = mapped_column(nullable=False)
    last_volume_year: Mapped[int] = mapped_column(nullable=True)
    journal_title: Mapped[str] = mapped_column(String(150), nullable=False)
    journal_subtitle: Mapped[str] = mapped_column(String(500), nullable=True)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    issn: Mapped[str] = mapped_column(String(9), nullable=True)
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)


class JournalArticle(PartialWorkMixin, WorkMixin):
    '''Compreende partes de uma publicação periódica, como artigo,
    comunicação, editorial, suplemento, entrevista, recensão, resenha,
    reportagem, entre outras.'''

    __tablename__ = 'journal_articles'

    journal_title: Mapped[str] = mapped_column(String(150), nullable=False)
    journal_subtitle: Mapped[str] = mapped_column(String(500), nullable=True)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    issn: Mapped[str] = mapped_column(String(9), nullable=True)
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)
    volume: Mapped[int] = mapped_column(nullable=True)
    year_season: Mapped[int] = mapped_column(nullable=True)
    number: Mapped[int] = mapped_column(nullable=False)


class NewspaperArticle(PartialWorkMixin, WorkMixin):
    '''Compreende partes de um jornal, como reportagem, entrevista,
    editorial, entre outras.'''

    __tablename__ = 'newspaper_articles'

    journal_title: Mapped[str] = mapped_column(String(150), nullable=False)
    journal_subtitle: Mapped[str] = mapped_column(String(500), nullable=True)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    issn: Mapped[str] = mapped_column(String(9), nullable=True)
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)
    volume: Mapped[int] = mapped_column(nullable=True)
    year_season: Mapped[int] = mapped_column(nullable=True)
    number: Mapped[int] = mapped_column(nullable=True)
    section: Mapped[str] = mapped_column(String(50), nullable=True)
    start_page: Mapped[str] = mapped_column(
        String(4), nullable=False, default='s.p.'
    )
    end_page: Mapped[str] = mapped_column(
        String(4), nullable=False, default='s.p.'
    )
