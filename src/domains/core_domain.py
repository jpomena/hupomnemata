import enum

from src.db import Base
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, cast
from sqlalchemy import (
    Boolean,
    String,
    Text,
    Enum,
    func,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    inspect,
    text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    declared_attr,
    object_mapper
)
from sqlalchemy.ext.associationproxy import association_proxy
from src.utils.error_log import log_exception


if TYPE_CHECKING:
    from .monographs import (
        EditorialMonograph,
        AcademicMonograph,
        CorrespondenceMonograph
    )
    from .periodicals import (
        PeriodicalCollection,
        Magazine,
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
    )
    from .multimedia import (
        AudiovisualDocument,
        AudioDocument,
        VisualDocument,
        ThreeDimensionalDocument,
        CartographicDocument,
        MusicalScore
    )
    from .compilations import CompilationFragment, CompilationWork
    from .digital import MiscDigitalDocument
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
        'EditorialMonograph',
        back_populates='bibliographic_resource',
        foreign_keys='[EditorialMonograph.bib_res_id]',
    )
    academic_monograph: Mapped['AcademicMonograph'] = relationship(
        'AcademicMonograph',
        back_populates='bibliographic_resource',
        foreign_keys='[AcademicMonograph.bib_res_id]',
    )
    correspondence_monograph: Mapped['CorrespondenceMonograph'] = (
        relationship(
            'CorrespondenceMonograph',
            back_populates='bibliographic_resource',
            foreign_keys='[CorrespondenceMonograph.bib_res_id]',
        )
    )
    periodical_collection: Mapped['PeriodicalCollection'] = (
        relationship(
            'PeriodicalCollection',
            back_populates='bibliographic_resource',
            foreign_keys='[PeriodicalCollection.bib_res_id]',
        )
    )
    magazine: Mapped['Magazine'] = relationship(
        'Magazine',
        back_populates='bibliographic_resource',
        foreign_keys='[Magazine.bib_res_id]',
    )
    journal_article: Mapped['JournalArticle'] = relationship(
        'JournalArticle',
        back_populates='bibliographic_resource',
        foreign_keys='[JournalArticle.bib_res_id]',
    )
    newspaper_article: Mapped['NewspaperArticle'] = relationship(
        'NewspaperArticle',
        back_populates='bibliographic_resource',
        foreign_keys='[NewspaperArticle.bib_res_id]',
    )
    monographic_proceeding: Mapped['MonographicProceedings'] = (
        relationship(
            'MonographicProceedings',
            back_populates='bibliographic_resource',
            foreign_keys='[MonographicProceedings.bib_res_id]',
        )
    )
    periodical_proceeding: Mapped['PeriodicalProceedings'] = (
        relationship(
            'PeriodicalProceedings',
            back_populates='bibliographic_resource',
            foreign_keys='[PeriodicalProceedings.bib_res_id]',
        )
    )
    patent: Mapped['Patent'] = relationship(
        'Patent',
        back_populates='bibliographic_resource',
        foreign_keys='[Patent.bib_res_id]',
    )
    statute: Mapped['Statute'] = relationship(
        'Statute',
        back_populates='bibliographic_resource',
        foreign_keys='[Statute.bib_res_id]',
    )
    caselaw: Mapped['CaseLaw'] = relationship(
        'CaseLaw',
        back_populates='bibliographic_resource',
        foreign_keys='[CaseLaw.bib_res_id]',
    )
    audiovisual_document: Mapped['AudiovisualDocument'] = relationship(
        'AudiovisualDocument',
        back_populates='bibliographic_resource',
        foreign_keys='[AudiovisualDocument.bib_res_id]',
    )
    audio_document: Mapped['AudioDocument'] = relationship(
        'AudioDocument',
        back_populates='bibliographic_resource',
        foreign_keys='[AudioDocument.bib_res_id]',
    )
    visual_document: Mapped['VisualDocument'] = relationship(
        'VisualDocument',
        back_populates='bibliographic_resource',
        foreign_keys='[VisualDocument.bib_res_id]',
    )
    three_dimensional_document: Mapped['ThreeDimensionalDocument'] = (
        relationship(
            'ThreeDimensionalDocument',
            back_populates='bibliographic_resource',
            foreign_keys='[ThreeDimensionalDocument.bib_res_id]',
        )
    )
    cartographic_document: Mapped['CartographicDocument'] = relationship(
        'CartographicDocument',
        back_populates='bibliographic_resource',
        foreign_keys='[CartographicDocument.bib_res_id]',
    )
    musical_score: Mapped['MusicalScore'] = relationship(
        'MusicalScore',
        back_populates='bibliographic_resource',
        foreign_keys='[MusicalScore.bib_res_id]',
    )
    miscellaneous_digital_document: Mapped['MiscDigitalDocument'] = (
        relationship(
            'MiscDigitalDocument',
            back_populates='bibliographic_resource',
            foreign_keys='[MiscDigitalDocument.bib_res_id]',
        )
    )
    fragments: Mapped[list['Fragment']] = relationship(
        'Fragment',
        back_populates='bibliographic_resource',
        cascade='all, delete-orphan',
    )
    compilation_items: Mapped[list['CompilationWork']] = relationship(
        'CompilationWork',
        back_populates='bibliographic_resource',
        cascade='all, delete-orphan',
    )

    @property
    def specific_work(self) -> 'WorkMixin | None':
        '''Retorna a obra específica associada ao recurso.

        Quando a instância ainda está ligada à sessão, o SQLAlchemy pode
        carregar o relacionamento on-demand; quando ela já está detached,
        somente retornamos valores que já estiveram carregados. Isso evita
        o erro de lazy-load em objetos fora da sessão.
        '''
        exclude_relations = {
            'parent_work', 'authorships', 'authors', 'fragments'
        }
        mapper = object_mapper(self)
        matches: list[WorkMixin] = []
        state = inspect(self)

        for rel in mapper.relationships:
            if rel.key in exclude_relations or rel.uselist:
                continue

            attr_state = state.attrs.get(rel.key)
            if attr_state is not None:
                value = attr_state.loaded_value
                if isinstance(value, WorkMixin):
                    matches.append(value)
                    continue

            if state.session is not None:
                try:
                    value = getattr(self, rel.key, None)
                except (RuntimeError, AttributeError) as error:
                    log_exception(
                        f"Falha ao carregar relacionamento {rel.key}",
                        error,
                    )
                    value = None
                if isinstance(value, WorkMixin):
                    matches.append(value)

        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError(
                'BibliographicResource possui mais de uma specific_work '
                'associada; o modelo exige um único trabalho específico.'
            )
        return matches[0]


class PartialWorkMixin:
    __abstract__ = True

    is_partial: Mapped[bool] = mapped_column(nullable=False, default=False)
    parent_bibliographic_resource_id: Mapped[int] = mapped_column(
        ForeignKey(
            'bibliographic_resources.id',
            ondelete='CASCADE'
        ), nullable=True
    )
    part_start_page: Mapped[str] = mapped_column(String(6), nullable=True)
    part_end_page: Mapped[str] = mapped_column(String(6), nullable=True)
    part_volume: Mapped[str] = mapped_column(String(15), nullable=True)
    part_chapter: Mapped[str] = mapped_column(String(15), nullable=True)
    consult_start_year: Mapped[int] = mapped_column(
        nullable=True
    )  # Apenas para coleções de periódicos
    consult_end_year: Mapped[int] = mapped_column(
        nullable=True
    )  # Apenas para coleções de periódicos

    @declared_attr
    def parent_bibliographic_resource(
        cls,
    ) -> Mapped['BibliographicResource']:
        return relationship(
            'BibliographicResource',
            foreign_keys=cast(
                Any,
                lambda: [cls.parent_bibliographic_resource_id],
            ),
            remote_side='BibliographicResource.id',
        )


class WorkMixin(Base):
    __abstract__ = True
    __table_args__ = (UniqueConstraint('bib_res_id'),)

    # ---------------------------- Identidade ---------------------------------
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    preserve_title_spelling: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text('0'),
    )
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

    display_year: Mapped[str] = mapped_column(
        String(30), nullable=False, default='[s.d.]'
    )
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
            back_populates=cls.__tablename__.removesuffix('s'),
            foreign_keys=f'{cls.__name__}.bib_res_id',
        )


class Author(Base):
    __tablename__ = 'authors'

    __table_args__ = (
        CheckConstraint(
            '"acronym" IS NULL OR "corporation" IS TRUE'
        ),
        UniqueConstraint('given_names', 'last_name'),
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
    jurisdiction_id: Mapped[int] = mapped_column(
        ForeignKey(
            "authors.id",
            ondelete="SET NULL"
        ), nullable=True
    )

    authorships: Mapped[list['Authorship']] = relationship(
        'Authorship', back_populates='author'
    )
    bibliographic_resources = association_proxy(
        target_collection='authorships', attr='bibliographic_resource',
    )
    jurisdiction: Mapped['Author'] = relationship(
        'Author', remote_side=[id]
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


class Fragment(Base):
    __tablename__ = 'fragments'

    id: Mapped[int] = mapped_column(primary_key=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    fragment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default='quote'
    )
    bib_res_id: Mapped[int] = mapped_column(
        ForeignKey(
            'bibliographic_resources.id',
            ondelete='CASCADE'
        ), nullable=False
    )
    start_page: Mapped[int] = mapped_column(nullable=True)
    end_page: Mapped[int] = mapped_column(nullable=True)
    location_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    location_value: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True, onupdate=func.now()
    )

    bibliographic_resource: Mapped['BibliographicResource'] = relationship(
        'BibliographicResource', back_populates='fragments'
    )
    compilation_items: Mapped[list['CompilationFragment']] = relationship(
        'CompilationFragment',
        back_populates='fragment',
        cascade='all, delete-orphan',
    )
