"""Handler e Mixin de inteligência de conhecimento e malha de saberes."""

from typing import Any, Dict, List, Optional


class KnowledgeControllerMixin:
    """Mixin para operações da Malha de Conhecimento e Estruturas de Saber."""

    def sync_knowledge_mesh(self) -> Dict[str, int]:
        """Sincroniza embeddings pendentes e recalcula clusters semânticos da malha."""
        vec_count = self.knowledge_service.sync_pending_embeddings()
        clusters = self.knowledge_service.clusterize_mesh()
        return {
            "vectorized": vec_count,
            "clusters": len(clusters),
        }

    def get_knowledge_graph(self, min_similarity: float = 0.40) -> Dict[str, Any]:
        """Retorna os dados estruturados do grafo (nós, arestas e clusters)."""
        return self.knowledge_service.get_graph_data(min_similarity=min_similarity)

    def get_knowledge_resonances(
        self,
        source_type: str,
        source_id: int,
        min_similarity: float = 0.30,
        top_k: int = 8,
    ) -> List[Dict[str, Any]]:
        """Retorna os nós mais semanticamente ressonantes com o nó consultado."""
        return self.knowledge_service.get_resonances(
            entity_type=source_type,
            entity_id=source_id,
            min_similarity=min_similarity,
            top_k=top_k,
        )

    def create_knowledge_link(
        self,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        weight: float = 1.0,
        relation_type: str = "deliberate",
        note: Optional[str] = None,
    ) -> bool:
        """Cria e persiste um vínculo deliberado entre duas entidades."""
        return self.knowledge_service.create_link(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            weight=weight,
            relation_type=relation_type,
            note=note,
        )

    def add_knowledge_fragment_to_compilation(
        self,
        fragment_id: int,
        compilation_id: int,
    ) -> bool:
        """Adiciona um fragmento da malha a uma compilação existente."""
        if hasattr(self, "set_compilation_fragment_membership"):
            return self.set_compilation_fragment_membership(
                compilation_id=compilation_id,
                fragment_id=fragment_id,
                included=True,
            )
        return False
