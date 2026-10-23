from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base

if TYPE_CHECKING:
    from .core_domain import BibliographicResource, Fragment


class Compilation(Base):
    __tablename__ = 'compilations'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        onupdate=func.now(),
    )
    items: Mapped[list['CompilationWork']] = relationship(
        back_populates='compilation',
        cascade='all, delete-orphan',
        order_by='CompilationWork.position',
    )
    fragment_items: Mapped[list['CompilationFragment']] = relationship(
        back_populates='compilation',
        cascade='all, delete-orphan',
    )
    sections: Mapped[list['CompilationSection']] = relationship(
        back_populates='compilation',
        cascade='all, delete-orphan',
        order_by='CompilationSection.position',
    )


class CompilationWork(Base):
    __tablename__ = 'compilation_works'
    __table_args__ = (
        UniqueConstraint(
            'compilation_id',
            'bib_res_id',
            name='uq_compilation_work_resource',
        ),
        UniqueConstraint(
            'compilation_id',
            'position',
            name='uq_compilation_work_position',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    compilation_id: Mapped[int] = mapped_column(
        ForeignKey('compilations.id', ondelete='CASCADE'),
        nullable=False,
    )
    bib_res_id: Mapped[int] = mapped_column(
        ForeignKey('bibliographic_resources.id', ondelete='CASCADE'),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text('0'),
    )
    compilation: Mapped[Compilation] = relationship(
        back_populates='items',
    )
    bibliographic_resource: Mapped['BibliographicResource'] = relationship(
        back_populates='compilation_items',
    )


class CompilationSection(Base):
    __tablename__ = 'compilation_sections'
    __table_args__ = (
        UniqueConstraint(
            'compilation_id',
            'position',
            name='uq_compilation_section_position',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    compilation_id: Mapped[int] = mapped_column(
        ForeignKey('compilations.id', ondelete='CASCADE'),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    central_idea: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text('0'),
    )
    compilation: Mapped[Compilation] = relationship(
        back_populates='sections',
    )


class CompilationFragment(Base):
    __tablename__ = 'compilation_fragments'
    __table_args__ = (
        UniqueConstraint(
            'compilation_id',
            'fragment_id',
            name='uq_compilation_fragment',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    compilation_id: Mapped[int] = mapped_column(
        ForeignKey('compilations.id', ondelete='CASCADE'),
        nullable=False,
    )
    fragment_id: Mapped[int] = mapped_column(
        ForeignKey('fragments.id', ondelete='CASCADE'),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text('0'),
    )
    work_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey('compilation_sections.id', ondelete='SET NULL'),
        nullable=True,
    )
    compilation: Mapped[Compilation] = relationship(
        back_populates='fragment_items',
    )
    section: Mapped[CompilationSection | None] = relationship()
    fragment: Mapped['Fragment'] = relationship(
        back_populates='compilation_items',
    )
