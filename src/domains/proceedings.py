from datetime import date

from .core import WorkMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

'''Compreende os trabalhos apresentados em um evento (resumos, atas,
anais, proceedings, entre outros).'''


class MonographicProceedings(WorkMixin):
    __tablename__ = 'monographic_proceedings'

    title: Mapped[str] = mapped_column(
        String(150), nullable=False, default='Anais [...]'
    )
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_number: Mapped[int] = mapped_column(nullable=True)
    event_year: Mapped[int] = mapped_column(nullable=False)
    event_place: Mapped[str] = mapped_column(String(25), nullable=True)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    publication_year: Mapped[int] = mapped_column(nullable=False)
    page_quantity: Mapped[int] = mapped_column(nullable=True)
    isbn: Mapped[str] = mapped_column(String(13), nullable=True)
    published: Mapped[bool] = mapped_column(nullable=False, default=True)


class PeriodicalProceedings(WorkMixin):
    __tablename__ = 'periodical_proceedings'

    title: Mapped[str] = mapped_column(
        String(150), nullable=False, default='Anais [...]'
    )
    event_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_number: Mapped[int] = mapped_column(nullable=True)
    event_year: Mapped[int] = mapped_column(nullable=False)
    event_place: Mapped[str] = mapped_column(String(25), nullable=True)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    publication_year: Mapped[int] = mapped_column(nullable=False)
    page_quantity: Mapped[int] = mapped_column(nullable=True)
    vol_or_year: Mapped[int] = mapped_column(nullable=True)
    number: Mapped[int] = mapped_column(nullable=False)
    start_page: Mapped[str] = mapped_column(
        String(4), nullable=False, default='s.p.'
    )
    end_page: Mapped[str] = mapped_column(
        String(4), nullable=False, default='s.p.'
    )
    publication_date: Mapped[date] = mapped_column(nullable=False)
    issn: Mapped[str] = mapped_column(String(9), nullable=True)
