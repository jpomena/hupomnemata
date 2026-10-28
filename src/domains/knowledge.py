"""Modelos de dados para embeddings, clusters e enlaces da malha de conhecimento."""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class KnowledgeEmbedding(Base):
    """Representação vetorial de fragmentos ou obras para similaridade semântica."""

    __tablename__ = 'knowledge_embeddings'
    __table_args__ = (
        UniqueConstraint('entity_type', 'entity_id', name='uq_knowledge_embedding_entity'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        onupdate=func.now(),
    )


class KnowledgeCluster(Base):
    """Agrupamento temático de saberes gerado algorítmica ou manualmente."""

    __tablename__ = 'knowledge_clusters'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    color: Mapped[str] = mapped_column(String(30), nullable=False, default="#896200")
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_custom_name: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    items: Mapped[list['KnowledgeClusterItem']] = relationship(
        back_populates='cluster',
        cascade='all, delete-orphan',
    )


class KnowledgeClusterItem(Base):
    """Vínculo de pertinência de um fragmento ou obra a um cluster."""

    __tablename__ = 'knowledge_cluster_items'
    __table_args__ = (
        UniqueConstraint('cluster_id', 'entity_type', 'entity_id', name='uq_knowledge_cluster_item'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cluster_id: Mapped[int] = mapped_column(
        ForeignKey('knowledge_clusters.id', ondelete='CASCADE'),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    cluster: Mapped['KnowledgeCluster'] = relationship(back_populates='items')


class KnowledgeLink(Base):
    """Aresta explícita curada pelo pesquisador entre duas entidades do grafo."""

    __tablename__ = 'knowledge_links'
    __table_args__ = (
        UniqueConstraint('source_type', 'source_id', 'target_type', 'target_id', name='uq_knowledge_link'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, default='dialogues')
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
