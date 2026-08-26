import enum

from src.db import Base
from datetime import date, datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import (
    String,
    Text,
    Enum,
    func,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    declared_attr,
    object_mapper
)
from sqlalchemy.ext.associationproxy import association_proxy


if TYPE_CHECKING:
    from .monographs import (
        EditorialMonograph,
        AcademicMonograph,
        CorrespondenceMonograph
    )
    from .periodicals import (
        PeriodicalCollection,
        JournalArticle,
        NewspaperArticle
    )
    from .proceedings import (
        MonographicProceedings,
        PeriodicalProceedings
    )
    from .legal_documents import (
        Statute,
        CaseLaw,
        AdministrativeAct
    )
    from .multimedia import (
        AudiovisualDocument,
        AudioDocument,
        VisualDocument,
        ThreeDimensionalDocument,
        CartographicDocument,
        MusicalScore
    )
    from .patent import Patent


class DatePrecision(enum.Enum):
    EXACT = 'exact'  # Ex.: 12 de maio de 1995.
    DECADE = 'decade'  # Ex.: Década de 90.
    CENTURY = 'century'  # Ex.: Século XX.
    MILLENIA = 'millenia'  # Ex.: 2º milênio.
    UNKNOWN = 'unknown'  # Data desconhecida.


class BibliographicResource(Base):
    __tablename__ = 'bibliographic_resources'

    id: Mapped[int] = mapped_column(primary_key=True)
    is_partial: Mapped[bool] = mapped_column(nullable=False, default=False)
    parent_work_id: Mapped[int] = mapped_column(
        ForeignKey(
            'bibliographic_resources.id',
            ondelete='RESTRICT'
        ), nullable=True
    )
    part_title: Mapped[str] = mapped_column(String(150), nullable=True)
    part_subtitle: Mapped[str] = mapped_column(String(500), nullable=True)
    part_start_page: Mapped[str] = mapped_column(String(6), nullable=True)
    part_end_page: Mapped[str] = mapped_column(String(6), nullable=True)
    part_volume: Mapped[str] = mapped_column(String(15), nullable=True)
    part_chapter: Mapped[str] = mapped_column(String(15), nullable=True)
    consult_start_year: Mapped[int] = mapped_column(nullable=True)
    consult_end_year: Mapped[int] = mapped_column(nullable=True)

    parent_work: Mapped['BibliographicResource'] = relationship(
        'BibliographicResource', remote_side=[id]
    )
    authorships: Mapped[list['Authorship']] = relationship(
        'Authorship',
        back_populates='bibliographic_resource',
        cascade='all, delete-orphan'
    )
    authors = association_proxy(
        target_collection='authorships',
        attr='author',
        creator=lambda author_obj: Authorship(author=author_obj)
    )

    editorial_monograph: Mapped['EditorialMonograph'] = relationship(
        'EditorialMonograph', back_populates='bibliographic_resource'
    )
    academic_monograph: Mapped['AcademicMonograph'] = relationship(
        'AcademicMonograph', back_populates='bibliographic_resource'
    )
    correspondence_monograph: Mapped['CorrespondenceMonograph'] = (
        relationship(
            'CorrespondenceMonograph', back_populates='bibliographic_resource'
        )
    )
    periodical_collection: Mapped['PeriodicalCollection'] = (
        relationship(
            'PeriodicalCollection', back_populates='bibliographic_resource'
        )
    )
    journal_article: Mapped['JournalArticle'] = relationship(
        'JournalArticle', back_populates='bibliographic_resource'
    )
    newspaper_article: Mapped['NewspaperArticle'] = relationship(
        'NewspaperArticle', back_populates='bibliographic_resource'
    )
    monographic_proceeding: Mapped['MonographicProceedings'] = (
        relationship(
            'MonographicProceedings', back_populates='bibliographic_resource'
        )
    )
    periodical_proceeding: Mapped['PeriodicalProceedings'] = (
        relationship(
            'PeriodicalProceedings', back_populates='bibliographic_resource'
        )
    )
    patent: Mapped['Patent'] = relationship(
        'Patent', back_populates='bibliographic_resource'
    )
    statute: Mapped['Statute'] = relationship(
        'Statute', back_populates='bibliographic_resource'
    )
    caselaw: Mapped['CaseLaw'] = relationship(
        'CaseLaw', back_populates='bibliographic_resource'
    )
    administrative_act: Mapped['AdministrativeAct'] = relationship(
        'AdministrativeAct', back_populates='bibliographic_resource'
    )
    audiovisual_document: Mapped['AudiovisualDocument'] = relationship(
        'AudiovisualDocument', back_populates='bibliographic_resource'
    )
    audio_document: Mapped['AudioDocument'] = relationship(
        'AudioDocument', back_populates='bibliographic_resource'
    )
    visual_document: Mapped['VisualDocument'] = relationship(
        'VisualDocument', back_populates='bibliographic_resource'
    )
    three_dimensional_document: Mapped['ThreeDimensionalDocument'] = (
        relationship(
            'ThreeDimensionalDocument', back_populates='bibliographic_resource'
        )
    )
    cartographic_document: Mapped['CartographicDocument'] = relationship(
        'CartographicDocument', back_populates='bibliographic_resource'
    )
    musical_score: Mapped['MusicalScore'] = relationship(
        'MusicalScore', back_populates='bibliographic_resource'
    )
    citations: Mapped[List[Citation]] = relationship(
        'Citation', back_populates='bibliographic_resource'
    )

    @property
    def specific_work(self):
        '''Descobre a obra dinamicamente lendo os metadados do SQLAlchemy.'''
        exclude_relations = {'parent_work', 'authorships', 'authors'}
        mapper = object_mapper(self)

        for rel in mapper.relationships:
            if rel.key not in exclude_relations:
                work = getattr(self, rel.key)
                if work is not None:
                    return work
        return None


class WorkMixin(Base):
    __abstract__ = True

    # ---------------------------- Identidade ---------------------------------
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(500), nullable=True)
    abstract: Mapped[str] = mapped_column(Text, nullable=True)
    bib_res_id: Mapped[int] = mapped_column(
        ForeignKey(
            'bibliographic_resources.id',
            ondelete='CASCADE'
        ), nullable=False
    )

    # ------------------------- Situação Temporal -----------------------------

    # NOTA: chronological_date_anchor é usado apenas para ordenação cronológica
    # técnica (SQL). Quando a data for imprecisa (ano, década, s.d.), usamos
    # 01-01 como âncora.
    date_anchor: Mapped[date] = mapped_column(nullable=True)

    display_year: Mapped[str] = mapped_column(String(10), nullable=False)
    date_precision: Mapped[DatePrecision] = mapped_column(
        Enum(DatePrecision),
        default=DatePrecision.EXACT,
        nullable=False
    )

    # -------------------------- Infraestrutura -------------------------------
    url: Mapped[str] = mapped_column(String(1000), nullable=True)
    viewed_at: Mapped[datetime] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=True, onupdate=func.now()
    )

    # -------------------------- Relações -------------------------------
    authors = association_proxy(
        target_collection='bibliographic_resource',
        attr='authors',
        creator=lambda author_obj: Authorship(author=author_obj)
    )

    @declared_attr
    def bibliographic_resource(cls) -> Mapped['BibliographicResource']:
        return relationship(
            'BibliographicResource',
            back_populates=cls.__tablename__.removesuffix('s')
        )


class Author(Base):
    __tablename__ = 'authors'

    __table_args__ = (
        CheckConstraint(
            '"acronym" IS NULL OR "corporation" IS TRUE'
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    given_names: Mapped[str] = mapped_column(String(150), nullable=False)
    last_name: Mapped[str] = mapped_column(String(150), nullable=False)
    given_names_initials: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    last_name_initial: Mapped[str] = mapped_column(String(10), nullable=False)
    corporation: Mapped[bool] = mapped_column(nullable=False, default=False)
    acronym: Mapped[str] = mapped_column(String(10), nullable=True)
    jurisdiction: Mapped[str] = mapped_column(
        String(150), nullable=True
    )

    authorships: Mapped[list['Authorship']] = relationship(
        'Authorship', back_populates='author'
    )
    bibliographic_resources = association_proxy(
        target_collection='authorships', attr='bibliographic_resource',
    )


class Authorship(Base):
    __tablename__ = 'authorships'

    __table_args__ = (
        UniqueConstraint(
            'author_id', 'bib_res_id'
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(
        ForeignKey(
            'authors.id',
            ondelete='CASCADE'
        ), nullable=False
    )
    bib_res_id: Mapped[int] = mapped_column(
        ForeignKey(
            'bibliographic_resources.id',
            ondelete='CASCADE'
        ), nullable=False
    )

    author: Mapped['Author'] = relationship(
        'Author', back_populates='authorships'
    )
    bibliographic_resource: Mapped['BibliographicResource'] = relationship(
        'BibliographicResource', back_populates='authorships'
    )


class Citation(Base):
    __tablename__ = 'citations'

    id: Mapped[int] = mapped_column(primary_key=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    bib_res_id: Mapped[int] = mapped_column(
        ForeignKey(
            'bibliographic_resources.id',
            ondelete='CASCADE'
        ), nullable=False
    )
    start_page: Mapped[int] = mapped_column(nullable=True)
    end_page: Mapped[int] = mapped_column(nullable=True)

    bibliographic_resource: Mapped[BibliographicResource] = relationship(
        'BibliographicResource', back_populates='citations'
    )
