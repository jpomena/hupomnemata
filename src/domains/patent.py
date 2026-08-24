from datetime import date, datetime
from src.db import Base
from .core import Authorship, BibliographicResource
from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

"""Patente é o registro do direito do inventor, concedido através de
um documento oficial outorgado pelo Estado chamado carta-patente,
que garante o uso exclusivo, durante certo período, de algo inédito que
ele tenha inventado, criado ou aperfeiçoado."""


class Patent(Base):
    __tablename__ = 'patents'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(
        String(150), nullable=False, default='Patente [...]'
    )
    applicant: Mapped[str] = mapped_column(String(100), nullable=False)
    representative: Mapped[str] = mapped_column(String(100), nullable=True)
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    filing_date: Mapped[date] = mapped_column(nullable=False)
    grant_date: Mapped[date] = mapped_column(nullable=True)
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
        'BibliographicResource', back_populates='patent'
    )
