from datetime import date, datetime
from src.db import Base
from .core import Authorship, BibliographicResource
from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

'''Compreende os trabalhos apresentados em um evento (resumos, atas,
anais, proceedings, entre outros).'''


class MonographicProceedings(Base):
    __tablename__ = 'monographic_proceedings'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(
        String(150), nullable=False, default='Anais [...]'
    )
    subtitle: Mapped[str] = mapped_column(String(500), nullable=True)
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
    bib_res_id: Mapped[int] = mapped_column(
        ForeignKey(
            'bibliographic_resources.id',
            ondelete='CASCADE'
        ), nullable=False
    )

    # -------------------------- Infraestrutura -------------------------------
    url: Mapped[str] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=True, onupdate=func.now()
    )

    # -------------------------- Relações -------------------------------
    authors = association_proxy(
        target_collection='authorships',
        attr='author',
        creator=lambda author_obj: Authorship(author=author_obj)
    )

    bibliographic_resource: Mapped['BibliographicResource'] = relationship(
        'BibliographicResource', back_populates='monographic_proceeding'
    )


class PeriodicalProceedings(Base):
    __tablename__ = 'periodical_proceedings'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(
        String(150), nullable=False, default='Anais [...]'
    )
    subtitle: Mapped[str] = mapped_column(String(500), nullable=True)
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
    bib_res_id: Mapped[int] = mapped_column(
        ForeignKey(
            'bibliographic_resources.id',
            ondelete='CASCADE'
        ), nullable=False
    )

    # -------------------------- Infraestrutura -------------------------------
    url: Mapped[str] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=True, onupdate=func.now()
    )

    # -------------------------- Relações -------------------------------
    authors = association_proxy(
        target_collection='authorships',
        attr='author',
        creator=lambda author_obj: Authorship(author=author_obj)
    )

    bibliographic_resource: Mapped['BibliographicResource'] = relationship(
        'BibliographicResource', back_populates='periodical_proceeding'
    )
