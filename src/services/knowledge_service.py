"""Serviço de conhecimento: orquestração de embeddings, ressonâncias, clusters e dados do grafo."""

from collections import Counter
import math
import random
import re
from typing import cast
import numpy as np

from src.db.db import SessionLocal
from src.domains.core_domain import Fragment, BibliographicResource
from src.repositories.knowledge_repository import (
    KnowledgeRepository,
    compute_text_hash,
    compute_work_signature,
    is_magazine_resource,
)
from src.services.semantic_engine import (
    SemanticEngineManager,
    bytes_to_vector,
    cosine_similarity,
    vector_to_bytes,
)

from src.configs.settings import CLUSTER_PALETTE_LIGHT

PALETTE_COLORS = CLUSTER_PALETTE_LIGHT or [
    "#7A5C00",  # Ouro / Bronze Nobre
    "#3D5A73",  # Ardósia Clássico
    "#7A4E48",  # Terracota Antigo
    "#3E6657",  # Verde Sálvia Profundo
    "#684E72",  # Púrpura Sideral
    "#8E7234",  # Âmbar Dourado
    "#3B5C6C",  # Azul Oceano Profundo
    "#665749",  # Bronze Escuro
]


class KnowledgeService:
    """Gerencia a inteligência da malha de saberes, similaridades e estrutura do grafo."""

    def __init__(self, engine_manager: SemanticEngineManager | None = None):
        self.engine_manager = engine_manager or SemanticEngineManager.get_instance()

    def compute_work_composite_vector(
        self,
        work: BibliographicResource,
        repo: KnowledgeRepository,
    ) -> tuple[np.ndarray, str]:
        """Calcula o vetor semântico composto da obra ponderado com a essência de seus fragmentos."""
        sw = work.specific_work
        title = (getattr(sw, 'title', '') or '').strip() if sw else ''
        subtitle = (getattr(sw, 'subtitle', '') or '').strip() if sw else ''
        desc = (work.effective_description or '').strip()
        parts = [p for p in (title, subtitle, desc) if p]
        text = " ".join(parts)
        dim = getattr(self.engine_manager.engine, 'DIMENSION', 128)
        base_vec = self.engine_manager.engine.encode(text) if text else np.zeros(dim, dtype=np.float32)

        frag_vecs: list[np.ndarray] = []
        for frag in (work.fragments or []):
            f_text = (frag.excerpt or '').strip()
            if not f_text:
                continue
            f_emb = repo.get_embedding('fragment', frag.id)
            if f_emb:
                frag_vecs.append(bytes_to_vector(f_emb.vector))
            else:
                f_v = self.engine_manager.engine.encode(f_text)
                frag_vecs.append(f_v)

        if frag_vecs:
            mean_frag_vec = np.mean(frag_vecs, axis=0)
            composite_vec = 0.4 * base_vec + 0.6 * mean_frag_vec
        else:
            composite_vec = base_vec

        norm = float(np.linalg.norm(composite_vec))
        if norm > 0:
            composite_vec = composite_vec / norm

        composite_signature = compute_work_signature(work)
        return composite_vec, composite_signature

    def sync_pending_embeddings(self) -> int:
        """Vetoriza de forma incremental todos os fragmentos e obras elegíveis (não-revistas)."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)

            # Purga quaisquer embeddings antigos de obras que sejam Revista
            for emb in repo.list_embeddings('work'):
                w = session.get(BibliographicResource, emb.entity_id)
                if w and is_magazine_resource(w):
                    repo.delete_embedding('work', emb.entity_id)

            unvectorized_frags = repo.get_unvectorized_fragments()
            unvectorized_works = repo.get_unvectorized_works()
            count = 0

            # 1. Vetoriza fragmentos
            for frag in unvectorized_frags:
                text = (frag.excerpt or '').strip()
                if not text:
                    continue
                vec = self.engine_manager.engine.encode(text)
                repo.save_embedding(
                    entity_type='fragment',
                    entity_id=frag.id,
                    text_hash=compute_text_hash(text),
                    vector_bytes=vector_to_bytes(vec),
                )
                count += 1

            # 2. Vetoriza obras elegíveis com vetor composto
            for work in unvectorized_works:
                if is_magazine_resource(work):
                    continue
                comp_vec, signature = self.compute_work_composite_vector(work, repo)
                repo.save_embedding(
                    entity_type='work',
                    entity_id=work.id,
                    text_hash=compute_text_hash(signature),
                    vector_bytes=vector_to_bytes(comp_vec),
                )
                count += 1

            session.commit()
            return count

    def revectorize_work(self, work_id: int) -> bool:
        """Re-vetoriza uma obra após atualização de sua síntese conceitual ou fragmentos."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            work = session.get(BibliographicResource, work_id)
            if not work or is_magazine_resource(work):
                return False

            comp_vec, signature = self.compute_work_composite_vector(work, repo)
            repo.save_embedding(
                entity_type='work',
                entity_id=work.id,
                text_hash=compute_text_hash(signature),
                vector_bytes=vector_to_bytes(comp_vec),
            )
            session.commit()

        # Recalcula clusters para reorganizar a constelação
        try:
            self.clusterize_mesh()
        except Exception:
            pass

        return True

    def get_resonances(
        self,
        entity_type: str,
        entity_id: int,
        top_k: int = 5,
        min_similarity: float = 0.10,
    ) -> list[dict[str, object]]:
        """Calcula as obras mais semanticamente ressonantes com a entidade consultada."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            target_emb = repo.get_embedding(entity_type, entity_id)
            if target_emb is None:
                return []

            target_vec = bytes_to_vector(target_emb.vector)
            all_work_embs = repo.list_embeddings('work')

            scores: list[tuple[int, float]] = []
            for emb in all_work_embs:
                if entity_type == 'work' and emb.entity_id == entity_id:
                    continue
                work = session.get(BibliographicResource, emb.entity_id)
                if not work or is_magazine_resource(work):
                    continue
                vec = bytes_to_vector(emb.vector)
                sim = cosine_similarity(target_vec, vec)
                if sim >= min_similarity:
                    scores.append((emb.entity_id, sim))

            scores.sort(key=lambda item: item[1], reverse=True)
            top_matches = scores[:top_k]

            results: list[dict[str, object]] = []
            for w_id, score in top_matches:
                work = session.get(BibliographicResource, w_id)
                if work is not None:
                    sw = work.specific_work
                    title = getattr(sw, 'title', '') or 'Obra'
                    authors = [
                        f"{getattr(a, 'given_names', '')} {getattr(a, 'last_name', '')}".strip()
                        for a in (work.authors or [])
                    ] if hasattr(work, 'authors') else []
                    author_str = ", ".join(authors) if authors else ""
                    node_dict = {
                        'id': f'work_{w_id}',
                        'type': 'work',
                        'entity_type': 'work',
                        'entity_id': w_id,
                        'title': title,
                        'work_title': title,
                        'label': title,
                        'author': author_str,
                        'doc_type': sw.__class__.__name__ if sw else 'Obra',
                        'fragment_count': len(work.fragments) if work.fragments else 0,
                        'excerpt': work.effective_description,
                        'full_text': work.effective_description,
                        'location': str(getattr(sw, 'date_anchor', '') or ''),
                        'similarity': round(score, 3),
                        'similarity_pct': int(round(score * 100)),
                        'weight': round(score, 3),
                    }
                    node_dict['target_node'] = node_dict
                    results.append(node_dict)

            return results

    def clusterize_mesh(
        self,
        target_clusters: int | None = None,
    ) -> list[dict[str, object]]:
        """Executa clusterização adaptativa por similaridade de cosseno restrita a Obras elegíveis."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            work_embeddings = repo.list_embeddings('work')
            if not work_embeddings:
                return []

            # Mapeia vetores e metadados de texto das obras elegíveis
            items: list[tuple[str, int, np.ndarray, str]] = []
            for emb in work_embeddings:
                work = session.get(BibliographicResource, emb.entity_id)
                if work is None or is_magazine_resource(work):
                    continue
                vec = bytes_to_vector(emb.vector)
                sw = work.specific_work
                title = getattr(sw, 'title', '') or ''
                abstract = work.effective_description
                # Inclui textos dos fragmentos para a extração conceitual de palavras-chave do cluster
                frag_texts = " ".join((f.excerpt or '').strip() for f in (work.fragments or []))
                text = f"{title} {abstract} {frag_texts}".strip()
                items.append(('work', emb.entity_id, vec, text))

            total_items = len(items)
            if total_items == 0:
                return []
            if total_items == 1:
                k = 1
            elif target_clusters is not None:
                k = max(1, min(target_clusters, total_items))
            else:
                k = max(1, min(max(2, total_items // 3), 6))

            # Algoritmo K-Means com métrica de cosseno e inicialização K-Means++
            # K-Means++ dispersa os centróides iniciais maximizando a separação entre as constelações
            first_idx = random.randrange(total_items)
            centroids = [items[first_idx][2]]

            while len(centroids) < k:
                dists = []
                for _, _, vec, _ in items:
                    max_sim = max(cosine_similarity(vec, c) for c in centroids)
                    dists.append(max(0.001, 1.0 - max_sim))
                probs = np.array(dists) / sum(dists)
                next_idx = int(np.random.choice(total_items, p=probs))
                centroids.append(items[next_idx][2])

            assignments = [0] * total_items

            for _ in range(12):
                # Fase de atribuição
                for idx, (_, _, vec, _) in enumerate(items):
                    best_c = 0
                    best_sim = -1.0
                    for c_idx, c_vec in enumerate(centroids):
                        sim = cosine_similarity(vec, c_vec)
                        if sim > best_sim:
                            best_sim = sim
                            best_c = c_idx
                    assignments[idx] = best_c

                # Fase de atualização dos centróides
                for c_idx in range(k):
                    assigned_vecs = [
                        items[i][2] for i in range(total_items) if assignments[i] == c_idx
                    ]
                    if assigned_vecs:
                        new_centroid = np.mean(assigned_vecs, axis=0)
                        norm = float(np.linalg.norm(new_centroid))
                        if norm > 0:
                            new_centroid /= norm
                        centroids[c_idx] = new_centroid

            # Extração de conceitos e nomes representativos
            clusters_payload: list[dict[str, object]] = []
            for c_idx in range(k):
                cluster_items = [
                    (items[i][0], items[i][1])
                    for i in range(total_items) if assignments[i] == c_idx
                ]
                if not cluster_items:
                    continue

                cluster_texts = [
                    items[i][3] for i in range(total_items) if assignments[i] == c_idx
                ]
                all_words = re.findall(r'\b[^\W\d_]{4,}\b', " ".join(cluster_texts).lower(), re.UNICODE)
                from src.services.semantic_engine import StatisticalTFIDFEngine
                filtered = [w for w in all_words if w not in StatisticalTFIDFEngine.STOPWORDS]
                counts = Counter(filtered).most_common(3)
                if counts:
                    keywords = " / ".join(w.capitalize() for w, _ in counts)
                    name = f"Constelação: {keywords}"
                else:
                    name = f"Constelação {c_idx + 1}"

                clusters_payload.append({
                    'name': name,
                    'color': PALETTE_COLORS[c_idx % len(PALETTE_COLORS)],
                    'keywords': ", ".join(w for w, _ in counts),
                    'items': cluster_items,
                })

            repo.replace_clusters(clusters_payload)
            session.commit()
            return clusters_payload

    def get_graph_data(self, min_similarity: float = 0.15) -> dict[str, object]:
        """Gera o payload JSON contendo exclusivamente nós de Obras elegíveis e suas afinidades."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            work_embeddings = repo.list_embeddings('work')
            clusters = repo.list_clusters()
            manual_links = repo.list_links()

            # Mapeamento de pertinência por cluster
            item_cluster_map: dict[tuple[str, int], tuple[int, str, str]] = {}
            cluster_summaries: list[dict[str, object]] = []
            for c in clusters:
                cluster_summaries.append({
                    'id': c.id,
                    'name': c.name,
                    'color': c.color,
                    'keywords': c.keywords or '',
                    'count': len(c.items),
                })
                for item in c.items:
                    item_cluster_map[(item.entity_type, item.entity_id)] = (c.id, c.name, c.color)

            # Construção dos nós do grafo: APENAS Obras elegíveis
            nodes: list[dict[str, object]] = []
            emb_vectors: list[tuple[str, np.ndarray]] = []

            for emb in work_embeddings:
                work = session.get(BibliographicResource, emb.entity_id)
                if work is None or is_magazine_resource(work):
                    continue

                c_info = item_cluster_map.get(('work', emb.entity_id))
                c_id, c_name, c_color = c_info if c_info else (0, 'Sem Constelação', PALETTE_COLORS[0])
                node_id = f"work_{emb.entity_id}"
                vec = bytes_to_vector(emb.vector)
                emb_vectors.append((node_id, vec))

                sw = work.specific_work
                title = getattr(sw, 'title', '') or 'Obra'
                authors = [
                    f"{getattr(a, 'given_names', '')} {getattr(a, 'last_name', '')}".strip()
                    for a in (work.authors or [])
                ] if hasattr(work, 'authors') else []
                author_str = ", ".join(authors) if authors else ""
                frag_count = len(work.fragments) if work.fragments else 0
                node_size = 18 + min(12, int(math.sqrt(frag_count) * 2.5))

                nodes.append({
                    'id': node_id,
                    'type': 'work',
                    'entity_type': 'work',
                    'entity_id': emb.entity_id,
                    'title': title,
                    'work_title': title,
                    'label': title,
                    'author': author_str,
                    'doc_type': sw.__class__.__name__ if sw else 'Obra',
                    'fragment_count': frag_count,
                    'excerpt': work.effective_description,
                    'full_text': work.effective_description,
                    'location': str(getattr(sw, 'date_anchor', '') or ''),
                    'cluster_id': c_id,
                    'cluster_name': c_name,
                    'color': c_color,
                    'size': node_size,
                })

            # Construção das arestas entre obras
            links: list[dict[str, object]] = []
            seen_edges: set[tuple[str, str]] = set()

            # 1. Arestas semânticas calculadas entre obras
            for i in range(len(emb_vectors)):
                src_id, src_vec = emb_vectors[i]
                for j in range(i + 1, len(emb_vectors)):
                    tgt_id, tgt_vec = emb_vectors[j]
                    sim = cosine_similarity(src_vec, tgt_vec)
                    if sim >= min_similarity:
                        seen_edges.add((src_id, tgt_id))
                        seen_edges.add((tgt_id, src_id))
                        links.append({
                            'source': src_id,
                            'target': tgt_id,
                            'value': round(sim, 3),
                            'weight': round(sim, 3),
                            'relation': 'semantic',
                            'note': f'Afinidade Semântica: {int(sim * 100)}%',
                        })

            # 2. Arestas explícitas curadas (se ambas as pontas forem obras visíveis)
            valid_node_ids = {n['id'] for n in nodes}
            for m_link in manual_links:
                src_id = f"{m_link.source_type}_{m_link.source_id}"
                tgt_id = f"{m_link.target_type}_{m_link.target_id}"
                if src_id in valid_node_ids and tgt_id in valid_node_ids and (src_id, tgt_id) not in seen_edges:
                    links.append({
                        'source': src_id,
                        'target': tgt_id,
                        'value': m_link.weight,
                        'weight': m_link.weight,
                        'relation': m_link.relation_type,
                        'note': m_link.note or 'Vínculo Deliberado',
                    })

            return {
                'nodes': nodes,
                'links': links,
                'clusters': cluster_summaries,
            }

    def get_work_fragments(self, work_id: int) -> list[dict[str, object]]:
        """Retorna todos os fragmentos pertencentes a uma obra específica para inspeção."""
        with SessionLocal() as session:
            work = session.get(BibliographicResource, work_id)
            if not work or not work.fragments:
                return []

            frags: list[dict[str, object]] = []
            for f in sorted(work.fragments, key=lambda x: x.id):
                loc = f"{f.location_type or ''} {f.location_value or ''}".strip()
                frags.append({
                    'id': f.id,
                    'excerpt': f.excerpt or '',
                    'comment': getattr(f, 'comment', '') or '',
                    'location_type': f.location_type or '',
                    'location_value': f.location_value or '',
                    'location': loc or 'Sem localização',
                    'fragment_type': getattr(f, 'fragment_type', 'quote') or 'quote',
                })
            return frags

    def create_link(
        self,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        weight: float = 1.0,
        relation_type: str = 'deliberate',
        note: str | None = None,
    ) -> bool:
        """Cria um vínculo explícito entre duas entidades de conhecimento."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            repo.save_link(
                source_type=source_type,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                weight=weight,
                relation_type=relation_type,
                note=note,
            )
            session.commit()
            return True
