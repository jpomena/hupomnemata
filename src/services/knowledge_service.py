"""Serviço de conhecimento: orquestração de embeddings, ressonâncias, clusters e dados do grafo."""

from collections import Counter
import random
import re
from typing import cast
import numpy as np

from src.db.db import SessionLocal
from src.domains.core_domain import Fragment, BibliographicResource
from src.repositories.knowledge_repository import KnowledgeRepository, compute_text_hash
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

    def sync_pending_embeddings(self) -> int:
        """Vetoriza de forma incremental todos os fragmentos e obras ainda não processados."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            unvectorized_frags = repo.get_unvectorized_fragments()
            unvectorized_works = repo.get_unvectorized_works()
            count = 0

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

            for work in unvectorized_works:
                sw = work.specific_work
                if sw is None:
                    continue
                text = f"{getattr(sw, 'title', '') or ''} {getattr(sw, 'subtitle', '') or ''} {work.effective_description}".strip()
                if not text:
                    continue
                vec = self.engine_manager.engine.encode(text)
                repo.save_embedding(
                    entity_type='work',
                    entity_id=work.id,
                    text_hash=compute_text_hash(text),
                    vector_bytes=vector_to_bytes(vec),
                )
                count += 1

            session.commit()
            return count

    def revectorize_work(self, work_id: int) -> bool:
        """Re-vetoriza uma obra após atualização de sua síntese conceitual (IA ou manual)."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            work = session.get(BibliographicResource, work_id)
            if not work:
                return False
            sw = work.specific_work
            title = getattr(sw, 'title', '') if sw else ''
            subtitle = getattr(sw, 'subtitle', '') if sw else ''
            text = f"{title} {subtitle} {work.effective_description}".strip()
            if not text:
                return False

            vec = self.engine_manager.engine.encode(text)
            repo.save_embedding(
                entity_type='work',
                entity_id=work.id,
                text_hash=compute_text_hash(text),
                vector_bytes=vector_to_bytes(vec),
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
        min_similarity: float = 0.20,
    ) -> list[dict[str, object]]:
        """Calcula os nós mais semanticamente ressonantes com a entidade consultada."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            target_emb = repo.get_embedding(entity_type, entity_id)
            if target_emb is None:
                return []

            target_vec = bytes_to_vector(target_emb.vector)
            all_embs = repo.list_embeddings()

            scores: list[tuple[str, int, float]] = []
            for emb in all_embs:
                if emb.entity_type == entity_type and emb.entity_id == entity_id:
                    continue
                vec = bytes_to_vector(emb.vector)
                sim = cosine_similarity(target_vec, vec)
                if sim >= min_similarity:
                    scores.append((emb.entity_type, emb.entity_id, sim))

            scores.sort(key=lambda item: item[2], reverse=True)
            top_matches = scores[:top_k]

            results: list[dict[str, object]] = []
            for e_type, e_id, score in top_matches:
                if e_type == 'fragment':
                    frag = session.get(Fragment, e_id)
                    if frag is not None:
                        b_res = session.get(BibliographicResource, frag.bib_res_id) if frag.bib_res_id else None
                        sw = b_res.specific_work if b_res else None
                        work_title = getattr(sw, 'title', '') if sw else 'Obra'
                        label = (frag.excerpt[:45] + '…') if len(frag.excerpt or '') > 45 else (frag.excerpt or 'Fragmento')
                        node_dict = {
                            'id': f'fragment_{e_id}',
                            'type': 'fragment',
                            'entity_type': 'fragment',
                            'entity_id': e_id,
                            'title': work_title,
                            'work_title': work_title,
                            'label': label,
                            'excerpt': frag.excerpt or '',
                            'full_text': frag.excerpt or '',
                            'location': f"{frag.location_type or ''} {frag.location_value or ''}".strip(),
                            'similarity': round(score, 3),
                            'similarity_pct': int(round(score * 100)),
                            'weight': round(score, 3),
                        }
                        node_dict['target_node'] = node_dict
                        results.append(node_dict)
                elif e_type == 'work':
                    work = session.get(BibliographicResource, e_id)
                    if work is not None:
                        sw = work.specific_work
                        title = getattr(sw, 'title', '') or 'Obra'
                        node_dict = {
                            'id': f'work_{e_id}',
                            'type': 'work',
                            'entity_type': 'work',
                            'entity_id': e_id,
                            'title': title,
                            'work_title': title,
                            'label': title,
                            'excerpt': getattr(sw, 'abstract', '') or getattr(sw, 'subtitle', '') or '',
                            'full_text': getattr(sw, 'abstract', '') or getattr(sw, 'subtitle', '') or '',
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
        """Executa clusterização adaptativa por similaridade de cosseno e gera nomes de conceitos."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            embeddings = repo.list_embeddings()
            if not embeddings:
                return []

            # Mapeia vetores e metadados de texto
            items: list[tuple[str, int, np.ndarray, str]] = []
            for emb in embeddings:
                vec = bytes_to_vector(emb.vector)
                text = ""
                if emb.entity_type == 'fragment':
                    frag = session.get(Fragment, emb.entity_id)
                    if frag is not None:
                        text = (frag.excerpt or '').strip()
                else:
                    work = session.get(BibliographicResource, emb.entity_id)
                    if work is not None:
                        sw = work.specific_work
                        text = f"{getattr(sw, 'title', '') or ''} {getattr(sw, 'abstract', '') or ''}"
                items.append((emb.entity_type, emb.entity_id, vec, text))

            total_items = len(items)
            if total_items == 1:
                k = 1
            elif target_clusters is not None:
                k = max(1, min(target_clusters, total_items))
            else:
                k = max(1, min(max(2, total_items // 3), 6))

            # Algoritmo K-Means com métrica de cosseno
            centroids = [items[i][2] for i in random.sample(range(total_items), k)]
            assignments = [0] * total_items

            for _ in range(8):
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
                    name = f"Cluster: {keywords}"
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

    def get_graph_data(self, min_similarity: float = 0.35) -> dict[str, object]:
        """Gera o payload JSON completo para consumo dos visualizadores interativos."""
        with SessionLocal() as session:
            repo = KnowledgeRepository(session)
            embeddings = repo.list_embeddings()
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

            # Construção dos nós do grafo
            nodes: list[dict[str, object]] = []
            emb_vectors: list[tuple[str, np.ndarray]] = []

            for emb in embeddings:
                c_info = item_cluster_map.get((emb.entity_type, emb.entity_id))
                c_id, c_name, c_color = c_info if c_info else (0, 'Sem Constelação', PALETTE_COLORS[0])
                node_id = f"{emb.entity_type}_{emb.entity_id}"
                vec = bytes_to_vector(emb.vector)
                emb_vectors.append((node_id, vec))

                if emb.entity_type == 'fragment':
                    frag = session.get(Fragment, emb.entity_id)
                    if frag is not None:
                        b_res = session.get(BibliographicResource, frag.bib_res_id) if frag.bib_res_id else None
                        sw = b_res.specific_work if b_res else None
                        work_title = getattr(sw, 'title', '') if sw else 'Obra'
                        nodes.append({
                            'id': node_id,
                            'type': 'fragment',
                            'entity_type': 'fragment',
                            'entity_id': emb.entity_id,
                            'title': work_title,
                            'work_title': work_title,
                            'label': (frag.excerpt[:45] + '…') if len(frag.excerpt or '') > 45 else frag.excerpt,
                            'excerpt': frag.excerpt or '',
                            'full_text': frag.excerpt or '',
                            'location': f"{frag.location_type or ''} {frag.location_value or ''}".strip(),
                            'cluster_id': c_id,
                            'cluster_name': c_name,
                            'color': c_color,
                            'size': 14,
                        })
                elif emb.entity_type == 'work':
                    work = session.get(BibliographicResource, emb.entity_id)
                    if work is not None:
                        sw = work.specific_work
                        title = getattr(sw, 'title', '') or 'Obra'
                        nodes.append({
                            'id': node_id,
                            'type': 'work',
                            'entity_type': 'work',
                            'entity_id': emb.entity_id,
                            'title': title,
                            'work_title': title,
                            'label': title,
                            'excerpt': getattr(sw, 'abstract', '') or getattr(sw, 'subtitle', '') or '',
                            'full_text': getattr(sw, 'abstract', '') or getattr(sw, 'subtitle', '') or '',
                            'location': str(getattr(sw, 'date_anchor', '') or ''),
                            'cluster_id': c_id,
                            'cluster_name': c_name,
                            'color': c_color,
                            'size': 18,
                        })

            # Construção das arestas (afinidades semânticas acima de threshold + links manuais)
            links: list[dict[str, object]] = []
            seen_edges: set[tuple[str, str]] = set()

            # 1. Arestas semânticas calculadas
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

            # 2. Arestas explícitas curadas
            for m_link in manual_links:
                src_id = f"{m_link.source_type}_{m_link.source_id}"
                tgt_id = f"{m_link.target_type}_{m_link.target_id}"
                if (src_id, tgt_id) not in seen_edges:
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
