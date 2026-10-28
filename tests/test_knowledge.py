"""Testes unitários para o módulo de conhecimento e Estruturas de Saber."""

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.db import Base
from src.domains import (
    BibliographicResource,
    EditorialMonograph,
    Fragment,
    Author,
    Authorship,
    KnowledgeCluster,
    KnowledgeClusterItem,
    KnowledgeEmbedding,
    KnowledgeLink,
)
from src.repositories.knowledge_repository import (
    KnowledgeRepository,
    compute_text_hash,
)
from src.services.semantic_engine import (
    StatisticalTFIDFEngine,
    bytes_to_vector,
    cosine_similarity,
    vector_to_bytes,
)
from src.services.knowledge_service import KnowledgeService
from src.views.knowledge.graph_template import generate_graph_html
from src.views.knowledge.knowledge_composer import compute_graph_layout


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_vector_serialization_and_similarity():
    """Valida conversão de vetores numpy para bytes e cálculo de cosseno."""
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    raw_bytes = vector_to_bytes(v1)
    restored = bytes_to_vector(raw_bytes)
    assert np.allclose(v1, restored)

    assert pytest.approx(cosine_similarity(v1, v2), 0.001) == 1.0
    assert pytest.approx(cosine_similarity(v1, v3), 0.001) == 0.0


def test_tfidf_engine():
    """Valida que o motor estatístico TF-IDF codifica textos de forma determinística."""
    engine = StatisticalTFIDFEngine()
    v1 = engine.encode("fenomenologia da percepção corpórea")
    v2 = engine.encode("fenomenologia e percepção")
    v3 = engine.encode("cálculo diferencial e álgebra linear")

    assert v1.shape == (128,)
    # Textos do mesmo campo semântico devem ter maior similaridade
    sim_related = cosine_similarity(v1, v2)
    sim_unrelated = cosine_similarity(v1, v3)
    assert sim_related > sim_unrelated


def test_knowledge_repository(memory_db):
    """Valida métodos CRUD do repositório de conhecimento."""
    repo = KnowledgeRepository(memory_db)

    # 1. Embeddings
    v = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    raw = vector_to_bytes(v)
    thash = compute_text_hash("texto de teste")

    emb = repo.save_embedding("fragment", 1, thash, raw)
    assert emb.id is not None
    memory_db.commit()

    fetched = repo.get_embedding("fragment", 1)
    assert fetched is not None
    assert fetched.text_hash == thash

    all_embs = repo.list_embeddings()
    assert len(all_embs) == 1

    # 2. Clusters
    clusters_payload = [
        {
            "name": "Fenomenologia",
            "color": "#896200",
            "keywords": "percepção, corpo",
            "items": [("fragment", 1)],
        }
    ]
    repo.replace_clusters(clusters_payload)
    memory_db.commit()

    clusters = repo.list_clusters()
    assert len(clusters) == 1
    assert clusters[0].name == "Fenomenologia"
    assert len(clusters[0].items) == 1

    # 3. Links manuais
    link = repo.save_link("fragment", 1, "work", 10, weight=0.9, relation_type="deliberate", note="Ponte de teste")
    memory_db.commit()

    links = repo.list_links()
    assert len(links) == 1
    assert links[0].note == "Ponte de teste"


def test_generate_graph_html():
    """Valida que o template HTML do grafo D3.js é gerado com dados e estrutura adequados."""
    sample_data = {
        "nodes": [
            {
                "id": "fragment_1",
                "type": "fragment",
                "label": "Trecho de teste",
                "work_title": "Obra Alfa",
                "color": "#896200",
                "size": 14,
            }
        ],
        "links": [
            {
                "source": "fragment_1",
                "target": "fragment_1",
                "weight": 0.85,
            }
        ],
        "clusters": [
            {
                "id": 1,
                "name": "Cluster de Teste",
                "color": "#896200",
            }
        ],
    }

    html = generate_graph_html(sample_data, theme_mode="dark", scale=1.0)
    assert "<!DOCTYPE html>" in html
    assert "d3" in html.lower()
    assert "fragment_1" in html
    assert "Estruturas de Saber" in html


def test_compute_graph_layout():
    """Valida o algoritmo de posicionamento 2D dos nós por forças e clusters."""
    nodes = [
        {"id": f"node_{i}", "cluster_id": i % 3}
        for i in range(12)
    ]
    links = [
        {"source": "node_0", "target": "node_1", "weight": 0.8},
        {"source": "node_1", "target": "node_2", "weight": 0.6},
    ]

    compute_graph_layout(nodes, links, width=1200.0, height=800.0)

    for n in nodes:
        assert "x" in n and "y" in n
        assert 60.0 <= n["x"] <= 1140.0
        assert 60.0 <= n["y"] <= 740.0


def test_knowledge_service_graph_and_resonances(memory_db, monkeypatch):
    """Valida o KnowledgeService gerando dados do grafo e ressonâncias."""
    # Monkeypatch SessionLocal to use memory_db
    from src.services import knowledge_service as ks_module
    from contextlib import contextmanager

    @contextmanager
    def mock_session_local():
        yield memory_db

    monkeypatch.setattr(ks_module, "SessionLocal", mock_session_local)

    # Cria dados de teste no memory_db
    res = BibliographicResource()
    memory_db.add(res)
    memory_db.flush()

    monograph = EditorialMonograph(
        id=res.id,
        bib_res_id=res.id,
        title="Fenomenologia da Percepção",
        abstract="Ensaio sobre a estrutura corporal da consciência.",
    )
    memory_db.add(monograph)

    frag1 = Fragment(
        excerpt="O corpo e a percepção são o veículo da consciência.",
        fragment_type="quote",
        bib_res_id=res.id,
        location_type="página",
        location_value="82",
    )
    frag2 = Fragment(
        excerpt="A percepção do corpo é a base originária da consciência.",
        fragment_type="quote",
        bib_res_id=res.id,
        location_type="página",
        location_value="145",
    )
    memory_db.add_all([frag1, frag2])
    memory_db.commit()

    service = KnowledgeService()
    # 1. Sincroniza embeddings
    count = service.sync_pending_embeddings()
    assert count == 3  # 1 obra + 2 fragmentos

    # 2. Clusterização
    clusters = service.clusterize_mesh()
    assert len(clusters) >= 1

    # 3. Grafo
    graph_data = service.get_graph_data(min_similarity=0.10)
    assert "nodes" in graph_data
    assert "links" in graph_data
    assert "clusters" in graph_data
    assert len(graph_data["nodes"]) == 3

    # 4. Ressonâncias de um fragmento
    resonances = service.get_resonances("fragment", frag1.id, top_k=5, min_similarity=0.01)
    assert len(resonances) >= 1
    # Deve ressoar com o frag2 e/ou a obra
    first_res = resonances[0]
    assert "target_node" in first_res
    assert "similarity_pct" in first_res


def test_core_controller_knowledge_mixin():
    """Valida a integração do KnowledgeControllerMixin com o CoreController."""
    from src.controllers.handlers import KnowledgeControllerMixin

    class DummyController(KnowledgeControllerMixin):
        def __init__(self, service):
            self.knowledge_service = service
            self.added_fragment = None

        def set_compilation_fragment_membership(self, compilation_id, fragment_id, included):
            self.added_fragment = (compilation_id, fragment_id, included)
            return True

    class DummyService:
        def sync_pending_embeddings(self):
            return 5

        def clusterize_mesh(self):
            return [{"id": 1, "name": "Cluster 1"}]

        def get_graph_data(self, min_similarity=0.4):
            return {"nodes": [{"id": "frag_1"}], "links": [], "clusters": []}

        def get_resonances(self, entity_type, entity_id, min_similarity=0.3, top_k=8):
            return [{"id": "frag_2", "similarity": 0.85}]

        def create_link(self, **kwargs):
            return True

    ctrl = DummyController(DummyService())
    sync_res = ctrl.sync_knowledge_mesh()
    assert sync_res["vectorized"] == 5
    assert sync_res["clusters"] == 1

    graph = ctrl.get_knowledge_graph(0.4)
    assert len(graph["nodes"]) == 1

    resonances = ctrl.get_knowledge_resonances("fragment", 1)
    assert len(resonances) == 1

    link_res = ctrl.create_knowledge_link("fragment", 1, "fragment", 2)
    assert link_res is True

    comp_res = ctrl.add_knowledge_fragment_to_compilation(fragment_id=42, compilation_id=7)
    assert comp_res is True
    assert ctrl.added_fragment == (7, 42, True)


def test_knowledge_composer_compose_with_nodes():
    """Valida renderização completa do KnowledgeComposer contendo nós, arestas e clusters."""
    from src.configs.settings import (
        COLORS_LIGHT,
        FONT_FAMILIES,
        FONT_SIZES,
        FONT_WEIGHTS,
        ICON_SIZES,
        MAIN_VIEW_CARDS,
        PAGE_FONTS,
        TEXTS,
        UI,
    )
    from src.utils.types import ViewConfig
    from src.views.knowledge.knowledge_composer import KnowledgeComposer

    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={},
        main_view_cards=MAIN_VIEW_CARDS,
    )

    mock_graph_data = {
        "nodes": [
            {
                "id": "work_1",
                "label": "Crítica da Razão Pura",
                "type": "work",
                "cluster_id": 1,
                "cluster_name": "Idealismo Transcendental",
                "color": "#896200",
                "work_title": "Crítica da Razão Pura",
            },
            {
                "id": "frag_1",
                "label": "Estética Transcendental",
                "type": "fragment",
                "cluster_id": 1,
                "cluster_name": "Idealismo Transcendental",
                "color": "#896200",
                "work_title": "Crítica da Razão Pura",
            },
        ],
        "links": [
            {
                "source": "work_1",
                "target": "frag_1",
                "weight": 0.88,
            }
        ],
        "clusters": [
            {
                "id": 1,
                "name": "Idealismo Transcendental",
                "color": "#896200",
                "keywords": "tempo, espaço, a priori",
            }
        ],
    }

    composer = KnowledgeComposer(
        page=None,
        config=config,
        scale=1.0,
        on_navigate=lambda _: None,
        get_graph_data=lambda _: mock_graph_data,
        sync_mesh=lambda: {"vectorized": 0, "clusters": 1},
        get_resonances=lambda *_: [{"id": "frag_1", "label": "Estética", "similarity": 0.88}],
        list_compilations=lambda: [{"id": 1, "title": "Compilação de Filosofia"}],
    )

    control = composer.compose()
    assert control is not None
    assert len(composer.node_containers) == 2
    assert "work_1" in composer.node_containers
    assert "frag_1" in composer.node_containers

    composer._handle_node_clicked(mock_graph_data["nodes"][0])
    assert composer.panel.panel_container.visible is True


def test_armillary_sphere_3d_centering_and_dimensions():
    """Valida o centramento matemático exato da Esfera Armilar 3D em modo comum e maximizado."""
    from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
    from src.utils.types import ViewConfig

    dummy_config = ViewConfig(
        colors={"gold": "#D4AF37", "surface": "#FFFFFF", "text": "#000000", "bg": "#F5F5F7", "muted": "#888888", "border": "#E0E0E0"},
        page_fonts={},
        font_families={"cormorant": "Cormorant", "montserrat": "Montserrat"},
        font_sizes={"cormorant_medium": 18},
        icon_sizes={},
        font_weights={"cormorant_bold": 700},
        ui={},
        texts={},
        core_menus={},
        main_view_cards={},
    )

    # 1. Modo Normal (ex: 1050x780 de viewport útil)
    sphere = ArmillaryConstellation3D(
        config=dummy_config,
        scale=1.0,
        on_select_node=lambda _: None,
        canvas_width=1050.0,
        canvas_height=780.0,
    )
    assert sphere._cx == 525.0
    assert sphere._cy == 390.0
    assert pytest.approx(sphere.sphere_radius, 0.1) == 780.0 * 0.36

    # 2. Transição para Modo Maximizado (ex: 1570x964 de viewport útil)
    sphere.update_dimensions(1570.0, 964.0)
    assert sphere._cx == 785.0
    assert sphere._cy == 482.0
    assert pytest.approx(sphere.sphere_radius, 0.1) == 964.0 * 0.36


def test_armillary_sphere_3d_filter_mode():
    """Valida a separação celeste entre Todas as Estrelas, Obras (Macro) e Fragmentos (Micro)."""
    from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
    from src.utils.types import ViewConfig

    dummy_config = ViewConfig(
        colors={"gold": "#D4AF37", "surface": "#FFFFFF", "text": "#000000", "bg": "#F5F5F7", "muted": "#888888", "border": "#E0E0E0"},
        page_fonts={},
        font_families={"cormorant": "Cormorant", "montserrat": "Montserrat"},
        font_sizes={"cormorant_medium": 18},
        icon_sizes={},
        font_weights={"cormorant_bold": 700},
        ui={},
        texts={},
        core_menus={},
        main_view_cards={},
    )

    sphere = ArmillaryConstellation3D(
        config=dummy_config,
        scale=1.0,
        on_select_node=lambda _: None,
        canvas_width=800.0,
        canvas_height=600.0,
    )

    nodes = [
        {"id": "work_1", "type": "work", "label": "Obra Alfa", "cluster_id": 1},
        {"id": "frag_1", "type": "fragment", "label": "Trecho 1", "cluster_id": 1},
        {"id": "frag_2", "type": "fragment", "label": "Trecho 2", "cluster_id": 1},
    ]
    links = [
        {"source": "work_1", "target": "frag_1", "weight": 0.8},
        {"source": "frag_1", "target": "frag_2", "weight": 0.6},
    ]

    sphere.set_data(nodes, links, [{"id": 1, "name": "Cluster 1"}])

    # 1. Modo Padrão: Todas
    sphere.set_filter_mode("all")
    assert sphere.filter_mode == "all"
    assert len(sphere.projected_nodes) == 3

    # 2. Modo Obras: Apenas 1 nó visível
    sphere.set_filter_mode("works")
    assert sphere.filter_mode == "works"
    assert "work_1" in sphere.projected_nodes
    assert "frag_1" not in sphere.projected_nodes
    assert len(sphere.projected_nodes) == 1

    # 3. Modo Fragmentos: Apenas 2 nós visíveis
    sphere.set_filter_mode("fragments")
    assert sphere.filter_mode == "fragments"
    assert "work_1" not in sphere.projected_nodes
    assert "frag_1" in sphere.projected_nodes
    assert "frag_2" in sphere.projected_nodes
    assert len(sphere.projected_nodes) == 2


def test_armillary_sphere_3d_celestial_grid_and_starfield():
    """Valida grade cartográfica de coordenadas celestes, ticks de astrolábio e poeira estelar."""
    from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
    from src.utils.types import ViewConfig

    dummy_config = ViewConfig(
        colors={
            "gold": "#D4AF37",
            "surface": "#FFFFFF",
            "text": "#000000",
            "bg": "#F5F5F7",
            "muted": "#888888",
            "border": "#E0E0E0",
            "constellation_ring": "#7A5C00",
            "constellation_grid": "#8C733E",
            "constellation_grid_tick": "#7A5C00",
            "constellation_node_work": "#5C4600",
            "constellation_node_fragment": "#3D5A73",
            "constellation_filament": "#8C733E",
            "star_dust": "#86868F",
        },
        page_fonts={},
        font_families={"cormorant": "Cormorant", "montserrat": "Montserrat"},
        font_sizes={"cormorant_medium": 18},
        icon_sizes={},
        font_weights={"cormorant_bold": 700},
        ui={},
        texts={},
        core_menus={},
        main_view_cards={},
    )

    sphere = ArmillaryConstellation3D(
        config=dummy_config,
        scale=1.0,
        on_select_node=lambda _: None,
        canvas_width=800.0,
        canvas_height=600.0,
    )

    # 1. Grade cartográfica celestial padrão ativa
    assert sphere.show_celestial_grid is True
    assert len(sphere._precomputed_grid) == 12  # 4 paralelos + 8 meridianos de ascensão reta
    assert len(sphere._precomputed_ticks) == 36  # 24 equatoriais + 12 zodiacais

    # 2. Alternância de exibição (Toggle)
    is_shown = sphere.toggle_celestial_grid()
    assert is_shown is False
    assert sphere.show_celestial_grid is False

    is_shown = sphere.toggle_celestial_grid()
    assert is_shown is True
    assert sphere.show_celestial_grid is True

    # 3. Poeira estelar com 3 magnitudes cósmicas
    assert len(sphere.starfield) == 72
    magnitudes = {dust[5] for dust in sphere.starfield}
    assert magnitudes == {1, 2, 3}


def test_params_constellation_colors_centralization():
    """Valida que todos os parâmetros de cor astronômicos estão centralizados em params.json."""
    from src.configs.settings import COLORS_LIGHT, COLORS_DARK, CLUSTER_PALETTE_LIGHT, CLUSTER_PALETTE_DARK
    from src.services.knowledge_service import PALETTE_COLORS

    keys = [
        "constellation_ring",
        "constellation_grid",
        "constellation_grid_tick",
        "constellation_node_work",
        "constellation_node_fragment",
        "constellation_filament",
        "star_dust",
        "cluster_palette",
    ]

    for k in keys:
        assert k in COLORS_LIGHT, f"Chave {k} ausente em COLORS_LIGHT"
        assert k in COLORS_DARK, f"Chave {k} ausente em COLORS_DARK"

    # Valida ausência do tom grená (#896200) na poeira estelar clara
    assert COLORS_LIGHT["star_dust"] != "#896200"
    assert COLORS_LIGHT["star_dust"] == "#86868F"

    # Valida que knowledge_service consome a paleta de params.json
    assert PALETTE_COLORS == CLUSTER_PALETTE_LIGHT
    assert len(CLUSTER_PALETTE_LIGHT) == 8
    assert len(CLUSTER_PALETTE_DARK) == 8
