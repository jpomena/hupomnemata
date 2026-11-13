from datetime import datetime
from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class PdfAnnotation(Base):
    """Anotação ou grifo de leitura vinculado a uma página de um arquivo PDF."""

    __tablename__ = 'pdf_annotations'

    id: Mapped[int] = mapped_column(primary_key=True)
    bib_res_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('bibliographic_resources.id', ondelete='CASCADE'),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_text: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(30), nullable=False, default='#D97706')
    rect_json: Mapped[str] = mapped_column(Text, nullable=False, default='[]')
    fragment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey('fragments.id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True, onupdate=func.now()
    )

    bibliographic_resource: Mapped['BibliographicResource'] = relationship(  # noqa: F821
        'BibliographicResource', back_populates='pdf_annotations'
    )
    fragment: Mapped['Fragment | None'] = relationship('Fragment')  # noqa: F821
