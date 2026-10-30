"""Repositório de persistência e consulta da malha de conhecimento (embeddings, clusters e links)."""

import hashlib
from typing import cast
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.domains.core_domain import Fragment, BibliographicResource
from src.domains.knowledge import (
    KnowledgeCluster,
    KnowledgeClusterItem,
    KnowledgeEmbedding,
    KnowledgeLink,
)


def compute_text_hash(text: str) -> str:
    """Gera hash SHA-256 normalizado para identificação de mudanças no texto."""
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()


def compute_work_signature(resource: BibliographicResource) -> str:
    """Gera a assinatura de texto canônica da obra e de seus fragmentos para hashing."""
    sw = resource.specific_work
    title = (getattr(sw, 'title', '') or '').strip() if sw else ''
    subtitle = (getattr(sw, 'subtitle', '') or '').strip() if sw else ''
    desc = (resource.effective_description or '').strip()
    parts = [p for p in (title, subtitle, desc) if p]
    text = " ".join(parts)
    frag_texts = sorted((f.excerpt or '').strip() for f in (resource.fragments or []))
    frag_part = "||".join(frag_texts)
    return f"{text}||{frag_part}"


def is_magazine_resource(resource: BibliographicResource) -> bool:
    """Identifica se o recurso bibliográfico é especificamente uma Revista (Magazine)."""
    if getattr(resource, 'magazine', None) is not None:
        return True
    sw = resource.specific_work
    if sw is not None:
        return getattr(sw, '__tablename__', '') == 'magazines' or sw.__class__.__name__ == 'Magazine'
    return False


class KnowledgeRepository:
    """Gerencia operações de persistência e consulta para a camada de conhecimento e grafos."""

    def __init__(self, session: Session):
        self.session = session

    def get_embedding(
        self,
        entity_type: str,
        entity_id: int,
    ) -> KnowledgeEmbedding | None:
        stmt = select(KnowledgeEmbedding).where(
            KnowledgeEmbedding.entity_type == entity_type,
            KnowledgeEmbedding.entity_id == entity_id,
        )
        return self.session.scalars(stmt).first()

    def save_embedding(
        self,
        entity_type: str,
        entity_id: int,
        text_hash: str,
        vector_bytes: bytes,
    ) -> KnowledgeEmbedding:
        existing = self.get_embedding(entity_type, entity_id)
        if existing is not None:
            existing.text_hash = text_hash
            existing.vector = vector_bytes
            self.session.flush()
            return existing

        embedding = KnowledgeEmbedding(
            entity_type=entity_type,
            entity_id=entity_id,
            text_hash=text_hash,
            vector=vector_bytes,
        )
        self.session.add(embedding)
        self.session.flush()
        return embedding

    def list_embeddings(
        self,
        entity_type: str | None = None,
    ) -> list[KnowledgeEmbedding]:
        stmt = select(KnowledgeEmbedding)
        if entity_type is not None:
            stmt = stmt.where(KnowledgeEmbedding.entity_type == entity_type)
        return list(self.session.scalars(stmt).all())

    def delete_embedding(self, entity_type: str, entity_id: int) -> bool:
        stmt = delete(KnowledgeEmbedding).where(
            KnowledgeEmbedding.entity_type == entity_type,
            KnowledgeEmbedding.entity_id == entity_id,
        )
        result = self.session.execute(stmt)
        self.session.flush()
        return result.rowcount > 0

    def get_unvectorized_fragments(self) -> list[Fragment]:
        """Retorna fragmentos que ainda não possuem embedding ou cujo texto foi alterado."""
        fragments = list(self.session.scalars(select(Fragment)).all())
        unvectorized: list[Fragment] = []
        for frag in fragments:
            text = (frag.excerpt or '').strip()
            if not text:
                continue
            current_hash = compute_text_hash(text)
            embedding = self.get_embedding('fragment', frag.id)
            if embedding is None or embedding.text_hash != current_hash:
                unvectorized.append(frag)
        return unvectorized

    def get_unvectorized_works(self) -> list[BibliographicResource]:
        """Retorna obras elegíveis (não-revistas) que ainda não possuem embedding ou foram alteradas."""
        resources = list(self.session.scalars(select(BibliographicResource)).all())
        unvectorized: list[BibliographicResource] = []
        for resource in resources:
            sw = resource.specific_work
            if sw is None:
                continue
            if is_magazine_resource(resource):
                continue
            composite_signature = compute_work_signature(resource)
            if not composite_signature.strip('|'):
                continue
            current_hash = compute_text_hash(composite_signature)
            embedding = self.get_embedding('work', resource.id)
            if embedding is None or embedding.text_hash != current_hash:
                unvectorized.append(resource)
        return unvectorized

    def replace_clusters(
        self,
        clusters_data: list[dict[str, object]],
    ) -> list[KnowledgeCluster]:
        """Substitui os clusters automáticos recalculados, preservando clusters customizados."""
        # Remove itens e clusters não-customizados
        existing_clusters = list(self.session.scalars(select(KnowledgeCluster)).all())
        for c in existing_clusters:
            if not c.is_custom_name:
                self.session.delete(c)
        self.session.flush()

        created: list[KnowledgeCluster] = []
        for data in clusters_data:
            cluster = KnowledgeCluster(
                name=cast(str, data.get('name', 'Cluster sem título')),
                color=cast(str, data.get('color', '#896200')),
                keywords=cast(str, data.get('keywords', '')),
                is_custom_name=False,
            )
            items = cast(list[tuple[str, int]], data.get('items', []))
            for entity_type, entity_id in items:
                cluster.items.append(
                    KnowledgeClusterItem(
                        entity_type=entity_type,
                        entity_id=entity_id,
                    )
                )
            self.session.add(cluster)
            created.append(cluster)

        self.session.flush()
        return created

    def list_clusters(self) -> list[KnowledgeCluster]:
        stmt = select(KnowledgeCluster).order_by(KnowledgeCluster.id)
        return list(self.session.scalars(stmt).all())

    def update_cluster_name(self, cluster_id: int, new_name: str) -> bool:
        cluster = self.session.get(KnowledgeCluster, cluster_id)
        if cluster is None:
            return False
        cluster.name = new_name.strip()
        cluster.is_custom_name = True
        self.session.flush()
        return True

    def create_link(
        self,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        relation_type: str = 'dialogues',
        note: str | None = None,
        weight: float = 1.0,
    ) -> KnowledgeLink:
        stmt = select(KnowledgeLink).where(
            KnowledgeLink.source_type == source_type,
            KnowledgeLink.source_id == source_id,
            KnowledgeLink.target_type == target_type,
            KnowledgeLink.target_id == target_id,
        )
        existing = self.session.scalars(stmt).first()
        if existing is not None:
            existing.relation_type = relation_type
            existing.note = note
            existing.weight = weight
            self.session.flush()
            return existing

        link = KnowledgeLink(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relation_type=relation_type,
            note=note,
            weight=weight,
        )
        self.session.add(link)
        self.session.flush()
        return link

    save_link = create_link

    def list_links(self) -> list[KnowledgeLink]:
        stmt = select(KnowledgeLink).order_by(KnowledgeLink.id)
        return list(self.session.scalars(stmt).all())

    def delete_link(self, link_id: int) -> bool:
        link = self.session.get(KnowledgeLink, link_id)
        if link is None:
            return False
        self.session.delete(link)
        self.session.flush()
        return True
