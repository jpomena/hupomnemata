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

    # 3. Grafo (Renderização estrita de Obras)
    graph_data = service.get_graph_data(min_similarity=0.10)
    assert "nodes" in graph_data
    assert "links" in graph_data
    assert "clusters" in graph_data
    assert len(graph_data["nodes"]) == 1
    assert graph_data["nodes"][0]["type"] == "work"
    assert graph_data["nodes"][0]["fragment_count"] == 2

    # 4. Fragmentos da obra para o painel de inspeção
    work_frags = service.get_work_fragments(res.id)
    assert len(work_frags) == 2
    assert work_frags[0]["location"] == "página 82"


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

    # Valida padronização visual com as demais páginas (Acervo, Fragmentos, Compilações)
    assert composer.root_container.padding.top == config.ui["content_top_padding"]
    assert composer.root_container.bgcolor == config.colors["surface"]
    assert composer.toolbar.padding.left == config.ui["header_horizontal_padding"]
    assert composer.toolbar.padding.right == config.ui["header_horizontal_padding"]
    assert composer.toolbar.padding.top == config.ui["header_top_padding"]
    assert composer.toolbar.padding.bottom == config.ui["header_bottom_padding"]
    assert composer.toolbar.bgcolor is None

    # Valida tipografia do título padronizada
    title_text = composer.toolbar.content.controls[0].controls[0]
    assert title_text.value == "Estruturas de Saber"
    assert title_text.size == config.font_sizes["cormorant_big"]
    assert title_text.font_family == config.font_families["cormorant"]
    assert title_text.weight == config.font_weights["cormorant_semibold"]

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


def test_magazine_strictly_excluded_from_knowledge_mesh(memory_db, monkeypatch):
    """Valida que o tipo Revista (Magazine) é estritamente excluído da malha e da clusterização,
    enquanto artigos de periódico (JournalArticle) e monografias permanecem integrados.
    """
    from contextlib import contextmanager
    from src.services import knowledge_service as ks_module
    from src.domains import Magazine, JournalArticle

    @contextmanager
    def mock_session_local():
        yield memory_db

    monkeypatch.setattr(ks_module, "SessionLocal", mock_session_local)

    # 1. Cria uma Revista (Magazine)
    res_mag = BibliographicResource()
    memory_db.add(res_mag)
    memory_db.flush()
    mag = Magazine(
        id=res_mag.id,
        bib_res_id=res_mag.id,
        title="Revista Brasileira de Filosofia",
        publication_place="São Paulo",
    )
    memory_db.add(mag)

    # 2. Cria um Artigo de Periódico (JournalArticle)
    res_art = BibliographicResource()
    memory_db.add(res_art)
    memory_db.flush()
    art = JournalArticle(
        id=res_art.id,
        bib_res_id=res_art.id,
        title="Ontologia Fundamental",
        number=4,
    )
    memory_db.add(art)

    # 3. Adiciona fragmento ao artigo
    frag_art = Fragment(
        excerpt="O ser é a questão central da analítica existencial.",
        fragment_type="quote",
        bib_res_id=res_art.id,
    )
    memory_db.add(frag_art)
    memory_db.commit()

    service = KnowledgeService()

    # Sincroniza embeddings
    service.sync_pending_embeddings()
    clusters = service.clusterize_mesh()

    graph = service.get_graph_data(min_similarity=0.01)
    node_ids = {n["id"] for n in graph["nodes"]}

    # A Revista NÃO pode estar nos nós do grafo
    assert f"work_{res_mag.id}" not in node_ids
    # O Artigo DEVE estar nos nós do grafo
    assert f"work_{res_art.id}" in node_ids
    # Todos os nós do grafo devem ser obras
    for node in graph["nodes"]:
        assert node["type"] == "work"

    # Clusters não devem conter a Revista
    for c in clusters:
        for item_type, item_id in c["items"]:
            assert not (item_type == "work" and item_id == res_mag.id)


def test_composite_vector_influences_similarity(memory_db, monkeypatch):
    """Valida que os fragmentos vinculados alteram o vetor composto da obra
    e direcionam seu posicionamento/ressonância semântica.
    """
    from contextlib import contextmanager
    from src.services import knowledge_service as ks_module

    @contextmanager
    def mock_session_local():
        yield memory_db

    monkeypatch.setattr(ks_module, "SessionLocal", mock_session_local)

    # Obra com título genérico
    res = BibliographicResource()
    memory_db.add(res)
    memory_db.flush()
    mono = EditorialMonograph(
        id=res.id,
        bib_res_id=res.id,
        title="Caderno de Anotações",
    )
    memory_db.add(mono)

    # Fragmento com vocabulário estritamente astronômico
    frag = Fragment(
        excerpt="A rotação dos planetas e a mecânica celeste dos astrolábios e esferas armilares.",
        fragment_type="quote",
        bib_res_id=res.id,
    )
    memory_db.add(frag)
    memory_db.commit()

    service = KnowledgeService()
    service.sync_pending_embeddings()

    repo = KnowledgeRepository(memory_db)
    emb = repo.get_embedding("work", res.id)
    assert emb is not None

    # Valida que o vetor composto da obra incorpora substancialmente o vetor do fragmento
    vec = bytes_to_vector(emb.vector)
    frag_vec = service.engine_manager.engine.encode(frag.excerpt)
    base_title_vec = service.engine_manager.engine.encode("Caderno de Anotações")

    sim_with_frag = cosine_similarity(vec, frag_vec)
    assert sim_with_frag > 0.60  # O vetor da obra é fortemente moldado pelo fragmento
    assert not np.allclose(vec, base_title_vec)  # O vetor diverge do título isolado


def test_armillary_sphere_lines_only_on_selection():
    """Valida que a constelação 3D não renderiza filamentos gerais sem seleção ativa."""
    from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
    from src.utils.types import ViewConfig
    import flet.canvas as cv

    dummy_config = ViewConfig(
        colors={
            "gold": "#D4AF37", "surface": "#FFFFFF", "text": "#000000", "bg": "#F5F5F7",
            "muted": "#888888", "border": "#E0E0E0", "constellation_ring": "#7A5C00",
            "constellation_grid": "#8C733E", "constellation_grid_tick": "#7A5C00",
            "constellation_node_work": "#5C4600", "constellation_filament": "#8C733E",
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

    nodes = [
        {"id": "work_1", "type": "work", "label": "Obra 1", "cluster_id": 1, "x3": 0.0, "y3": 0.0, "z3": 0.0},
        {"id": "work_2", "type": "work", "label": "Obra 2", "cluster_id": 1, "x3": 50.0, "y3": 0.0, "z3": 0.0},
        {"id": "work_3", "type": "work", "label": "Obra 3", "cluster_id": 2, "x3": -50.0, "y3": 0.0, "z3": 0.0},
    ]
    links = [
        {"source": "work_1", "target": "work_2", "weight": 0.9},
    ]

    sphere.set_data(nodes, links, [{"id": 1, "name": "Cluster 1"}, {"id": 2, "name": "Cluster 2"}])

    # 1. Sem seleção: Nenhuma linha de filamento de nó deve ser desenhada e nenhum nó fica translúcido
    sphere.select_node_id(None)
    node_lines = [
        s for s in sphere.canvas.shapes
        if isinstance(s, cv.Line) and s.data == "filament"
    ]
    assert len(node_lines) == 0
    dimmed_nodes = [
        s for s in sphere.canvas.shapes
        if isinstance(s, cv.Circle) and s.data == "node_dimmed"
    ]
    assert len(dimmed_nodes) == 0

    # 2. Com seleção ativa em work_1:
    # - Filamento conectando work_1 a work_2 é desenhado
    # - work_3 (não relacionado) fica translúcido (data="node_dimmed")
    # - work_1 e work_2 permanecem opacos e focados (data="node_core")
    sphere.select_node_id("work_1")
    node_lines_sel = [
        s for s in sphere.canvas.shapes
        if isinstance(s, cv.Line) and s.data == "filament"
    ]
    assert len(node_lines_sel) >= 1

    dimmed_nodes_sel = [
        s for s in sphere.canvas.shapes
        if isinstance(s, cv.Circle) and s.data == "node_dimmed"
    ]
    assert len(dimmed_nodes_sel) == 1

    core_nodes_sel = [
        s for s in sphere.canvas.shapes
        if isinstance(s, cv.Circle) and s.data == "node_core"
    ]
    assert len(core_nodes_sel) == 2  # work_1 (selecionado) e work_2 (conexo)

    # Rótulos de texto: nós selecionado e conexo exibem títulos; o nó translúcido tem rótulo suprimido
    text_labels = [
        s.value for s in sphere.canvas.shapes
        if isinstance(s, cv.Text)
    ]
    assert "Obra 1" in text_labels
    assert "Obra 2" in text_labels
    assert "Obra 3" not in text_labels

    # 3. Ao desmarcar a seleção, todos os nós retornam à visibilidade total
    sphere.select_node_id(None)
    dimmed_nodes_cleared = [
        s for s in sphere.canvas.shapes
        if isinstance(s, cv.Circle) and s.data == "node_dimmed"
    ]
    assert len(dimmed_nodes_cleared) == 0


def test_work_signature_canonical_and_sync_idempotency():
    """Valida que compute_work_signature trata None e campos opcionais identicamente, garantindo sincronização idempotente."""
    from src.repositories.knowledge_repository import compute_work_signature, compute_text_hash
    from src.domains.core_domain import BibliographicResource
    from src.domains.monographs import EditorialMonograph

    work = BibliographicResource(
        id=999,
        custom_description="Descrição detalhada da obra",
        fragments=[],
    )
    sw = EditorialMonograph(
        id=999,
        title="Título Canônico",
        subtitle=None,
    )
    work.editorial_monograph = sw

    sig1 = compute_work_signature(work)
    hash1 = compute_text_hash(sig1)

    assert "None" not in sig1
    assert sig1 == "Título Canônico Descrição detalhada da obra||"

    # Segunda chamada garante determinismo estrito
    sig2 = compute_work_signature(work)
    assert sig1 == sig2
    assert hash1 == compute_text_hash(sig2)


def test_armillary_sphere_constellations_spatial_separation():
    """Valida que constelações são posicionadas com separação celeste angular real, impedindo colapso em supercluster."""
    from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
    from src.utils.types import ViewConfig

    dummy_config = ViewConfig(
        colors={
            "gold": "#D4AF37", "surface": "#FFFFFF", "text": "#000000", "bg": "#F5F5F7",
            "muted": "#888888", "border": "#E0E0E0", "constellation_ring": "#7A5C00",
            "constellation_grid": "#8C733E", "constellation_grid_tick": "#7A5C00",
            "constellation_node_work": "#5C4600", "constellation_filament": "#8C733E",
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
        canvas_width=1000.0,
        canvas_height=700.0,
    )

    nodes = [
        {"id": "work_1", "type": "work", "label": "Obra 1", "cluster_id": 1},
        {"id": "work_2", "type": "work", "label": "Obra 2", "cluster_id": 1},
        {"id": "work_3", "type": "work", "label": "Obra 3", "cluster_id": 2},
        {"id": "work_4", "type": "work", "label": "Obra 4", "cluster_id": 2},
        {"id": "work_5", "type": "work", "label": "Obra 5", "cluster_id": 3},
        {"id": "work_6", "type": "work", "label": "Obra 6", "cluster_id": 3},
    ]
    links = [
        {"source": "work_1", "target": "work_2", "weight": 0.8},
        {"source": "work_3", "target": "work_4", "weight": 0.8},
        {"source": "work_5", "target": "work_6", "weight": 0.8},
        {"source": "work_1", "target": "work_3", "weight": 0.2},
    ]

    clusters = [
        {"id": 1, "name": "Cluster A"},
        {"id": 2, "name": "Cluster B"},
        {"id": 3, "name": "Cluster C"},
    ]

    sphere.set_data(nodes, links, clusters)

    import numpy as np
    coords = np.array([[n["x3"], n["y3"], n["z3"]] for n in sphere.nodes])
    azs = [np.arctan2(n["z3"], n["x3"]) * 180 / np.pi for n in sphere.nodes]

    # Constelações ocupam setores celestes distintos (amplitude angular ampla > 120°)
    az_span = max(azs) - min(azs)
    assert az_span > 120.0

    # Distância inter-constelações é significativamente superior à intra-constelação (isolamento de constelações)
    intra = []
    inter = []
    for i in range(len(sphere.nodes)):
        for j in range(i + 1, len(sphere.nodes)):
            d = np.linalg.norm(coords[i] - coords[j])
            if sphere.nodes[i]["cluster_id"] == sphere.nodes[j]["cluster_id"]:
                intra.append(d)
            else:
                inter.append(d)

    assert np.mean(inter) > 2.0 * np.mean(intra)


def test_work_fragments_wired_to_side_panel_on_selection():
    """Valida que os fragmentos da obra são recuperados e exibidos no painel lateral ao selecionar o nó."""
    from unittest.mock import MagicMock
    from src.controllers.core_controller import CoreController

    page = MagicMock()
    page.window = None
    page.width = 1920.0
    page.height = 1080.0

    ctrl = CoreController(page=page)
    composer = ctrl.create_composer()
    assert composer.get_knowledge_work_fragments is not None

    composer._compose_knowledge()
    kc = composer.knowledge_composer
    assert kc.get_work_fragments is not None

    # Simula clique no nó com fragmentos (A República - id 17)
    node_rep = next((n for n in kc.graph_data["nodes"] if n.get("entity_id") == 17), None)
    if node_rep:
        kc._handle_node_clicked(node_rep)
        assert kc.panel.panel_container.visible is True
        # Painel deve conter os cards de fragmentos da obra
        assert len(kc.panel.fragments_column.controls) >= 1
        # Não deve exibir a mensagem de lista vazia
        first_text = getattr(kc.panel.fragments_column.controls[0], "value", "")
        assert "não possui citações" not in first_text


def test_knowledge_panel_light_mode_visual_identity_zero_grena():
    """Valida que o painel lateral em modo claro elimina cores grená (#896200) e harmoniza com Acervo e Fragmentos."""
    from src.configs.settings import COLORS_LIGHT, FONT_FAMILIES, FONT_SIZES, FONT_WEIGHTS, UI
    from src.utils.types import ViewConfig
    from src.views.knowledge.knowledge_panel import KnowledgePanel

    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts={},
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes={},
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts={},
        core_menus={},
        main_view_cards={},
    )

    panel = KnowledgePanel(
        config=config,
        scale=1.0,
        on_close=lambda: None,
        on_select_resonance=lambda _: None,
    )

    # 1. Header do Painel
    assert panel.badge_text.color == COLORS_LIGHT["muted"]
    assert panel.badge_text.color != COLORS_LIGHT["gold"]
    assert panel.badge_container.border.top.color == COLORS_LIGHT["border"]
    assert panel.title_text.color == COLORS_LIGHT["text"]
    assert panel.title_text.color != COLORS_LIGHT["gold"]
    assert panel.excerpt_container.bgcolor == COLORS_LIGHT["surface"]

    # 2. Card de Fragmento (Harmonizado com tela Fragmentos)
    frag_data = {
        "id": 1,
        "excerpt": "A justiça é a virtude da alma.",
        "location": "Livro IV, 433a",
        "fragment_type": "quote",
    }
    frag_card = panel._build_fragment_card(frag_data)
    assert frag_card.bgcolor == COLORS_LIGHT["surface"]
    assert frag_card.border.top.color == COLORS_LIGHT["border"]

    col = frag_card.content
    badge_container = col.controls[0].controls[0]
    badge_text = badge_container.content
    assert badge_text.color == COLORS_LIGHT["muted"]
    assert badge_text.color != COLORS_LIGHT["gold"]
    assert badge_container.bgcolor == COLORS_LIGHT.get("card_hover", COLORS_LIGHT["surface"])

    excerpt_text = col.controls[1]
    assert excerpt_text.color == COLORS_LIGHT["text"]

    # 3. Card de Ressonância
    res_data = {
        "id": "work_2",
        "label": "Ética a Nicômaco",
        "work_title": "Aristóteles",
        "weight": 0.88,
    }
    res_card = panel._build_resonance_card(res_data, 88)
    assert res_card.bgcolor == COLORS_LIGHT["surface"]
    assert res_card.border.top.color == COLORS_LIGHT["border"]

    res_col = res_card.content
    pct_badge = res_col.controls[0].controls[1]
    assert pct_badge.content.color == COLORS_LIGHT["text"]
    assert pct_badge.content.color != COLORS_LIGHT["gold"]
    assert pct_badge.bgcolor == COLORS_LIGHT.get("card_hover", COLORS_LIGHT["surface"])

    progress_bar = res_col.controls[2]
    assert progress_bar.color == COLORS_LIGHT["text"]
    assert progress_bar.color != COLORS_LIGHT["gold"]
    assert progress_bar.bgcolor == COLORS_LIGHT["border"]


def test_armillary_sphere_central_nodes_radial_depth():
    """Valida que nós centrais (com alta afinidade e fragmentos) ocupam camadas orbitais internas/núcleo."""
    from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
    from src.utils.types import ViewConfig
    import numpy as np

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
        canvas_width=1000.0,
        canvas_height=1000.0,
    )

    nodes = [
        {"id": "work_central", "type": "work", "label": "Obra Central", "cluster_id": 1, "fragment_count": 10},
        {"id": "work_leaf_1", "type": "work", "label": "Obra Folha 1", "cluster_id": 1, "fragment_count": 0},
        {"id": "work_leaf_2", "type": "work", "label": "Obra Folha 2", "cluster_id": 1, "fragment_count": 0},
        {"id": "work_isolated", "type": "work", "label": "Obra Isolada", "cluster_id": 2, "fragment_count": 0},
    ]

    links = [
        {"source": "work_central", "target": "work_leaf_1", "weight": 0.95},
        {"source": "work_central", "target": "work_leaf_2", "weight": 0.90},
        {"source": "work_central", "target": "work_isolated", "weight": 0.70},
    ]

    clusters = [
        {"id": 1, "name": "Núcleo"},
        {"id": 2, "name": "Periferia"},
    ]

    sphere.set_data(nodes, links, clusters)

    radii = {n["id"]: np.sqrt(n["x3"]**2 + n["y3"]**2 + n["z3"]**2) for n in sphere.nodes}

    # Nó central tem raio significativamente menor (mais interno) que nós periféricos/folhas
    assert radii["work_central"] < radii["work_leaf_1"]
    assert radii["work_central"] < radii["work_isolated"]

    # Nem todos os nós estão na mesma superfície esférica (variação de profundidade radial real)
    unique_radii = set(round(r, 1) for r in radii.values())
    assert len(unique_radii) >= 2


def test_armillary_sphere_zoom_controls():
    """Valida controles telescópicos de zoom in e zoom out na esfera armilar."""
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

    initial_dist = sphere.camera_distance
    sphere.zoom_in(100.0)
    assert sphere.camera_distance < initial_dist

    sphere.zoom_out(200.0)
    assert sphere.camera_distance > initial_dist

    sphere.reset_view()
    assert sphere.camera_distance == 680.0


def test_knowledge_composer_sensitivity_slider_and_hud():
    """Valida presença do slider de sensibilidade e HUD flutuante de zoom no compositor."""
    import flet as ft
    from src.configs.settings import COLORS_LIGHT, FONT_FAMILIES, FONT_SIZES, FONT_WEIGHTS, UI
    from src.utils.types import ViewConfig
    from src.views.knowledge.knowledge_composer import KnowledgeComposer

    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts={},
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes={},
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts={},
        core_menus={},
        main_view_cards={},
    )

    composer = KnowledgeComposer(
        page=None,
        config=config,
        scale=1.0,
        on_navigate=lambda _: None,
        get_graph_data=lambda _: {"nodes": [], "links": [], "clusters": []},
        sync_mesh=lambda: {"vectorized": 0, "clusters": 0},
        get_resonances=lambda *_: [],
    )

    # 1. Slider de sensibilidade
    assert isinstance(composer.sensitivity_slider, ft.Slider)
    assert composer.sensitivity_slider.divisions == 45
    assert composer.sensitivity_slider.min == 0.05
    assert composer.sensitivity_slider.max == 0.50

    # 2. HUD flutuante com zoom
    assert composer.floating_hud is not None
    assert composer.viewport_container is not None
    assert composer.floating_hud.right == 24 * composer.scale
    assert composer.floating_hud.bottom == 24 * composer.scale
    assert composer.floating_hud.alignment is None


def test_armillary_sphere_3d_gestures_and_hud_positioning():
    """Valida que o HUD não oclui a esfera 3D e que eventos de arrasto orbital e zoom são processados."""
    import flet as ft
    from src.configs.settings import COLORS_LIGHT, FONT_FAMILIES, FONT_SIZES, FONT_WEIGHTS, UI
    from src.utils.types import ViewConfig
    from src.views.knowledge.knowledge_composer import KnowledgeComposer

    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts={},
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes={},
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts={},
        core_menus={},
        main_view_cards={},
    )

    composer = KnowledgeComposer(
        page=None,
        config=config,
        scale=1.0,
        on_navigate=lambda _: None,
        get_graph_data=lambda _: {"nodes": [], "links": [], "clusters": []},
        sync_mesh=lambda: {"vectorized": 0, "clusters": 0},
        get_resonances=lambda *_: [],
    )

    # O HUD flutuante deve estar posicionado no canto inferior direito sem ocluir a tela toda
    assert composer.floating_hud.right == 24 * composer.scale
    assert composer.floating_hud.bottom == 24 * composer.scale
    assert composer.floating_hud.alignment is None

    # O GestureDetector da esfera deve cobrir todo o Stack
    sphere = composer.armillary_3d
    assert sphere.gesture_detector.left == 0
    assert sphere.gesture_detector.top == 0
    assert sphere.gesture_detector.right == 0
    assert sphere.gesture_detector.bottom == 0
    assert sphere.gesture_detector.mouse_cursor == ft.MouseCursor.GRAB

    # Validação do gesto de rotação orbital (pan update)
    initial_yaw = sphere.yaw
    initial_pitch = sphere.pitch

    class DummyOffset:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    class DummyDragUpdateEvent:
        local_delta = DummyOffset(20.0, -10.0)
        global_delta = DummyOffset(20.0, -10.0)
        delta_x = 20.0
        delta_y = -10.0

    sphere._handle_pan_start(None)
    assert sphere._is_dragging is True
    assert sphere.gesture_detector.mouse_cursor == ft.MouseCursor.GRABBING

    sphere._handle_pan_update(DummyDragUpdateEvent())
    assert sphere.yaw > initial_yaw
    assert sphere.pitch < initial_pitch

    sphere._handle_pan_end(None)
    assert sphere._is_dragging is False
    assert sphere.gesture_detector.mouse_cursor == ft.MouseCursor.GRAB

    # Validação do gesto de zoom via scroll do mouse
    initial_cam = sphere.camera_distance

    class DummyScrollEvent:
        scroll_delta = DummyOffset(0.0, 50.0)
        scroll_delta_y = 50.0

    sphere._handle_scroll(DummyScrollEvent())
    assert sphere.camera_distance > initial_cam


def test_armillary_sphere_3d_smoothness_typography_and_path_batching():
    """Valida anéis com alta resolução circular (96 passos), batched paths para 60 FPS e tipografia canônica Cormorant/Montserrat."""
    import flet as ft
    import flet.canvas as cv
    from src.configs.settings import COLORS_LIGHT, FONT_FAMILIES, FONT_SIZES, FONT_WEIGHTS, UI
    from src.utils.types import ViewConfig
    from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D

    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts={},
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes={},
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts={},
        core_menus={},
        main_view_cards={},
    )

    sphere = ArmillaryConstellation3D(
        config=config,
        scale=1.0,
        on_select_node=lambda _: None,
        canvas_width=1000.0,
        canvas_height=800.0,
    )

    # 1. Resolução circular dos anéis: 96 passos (97 pontos) em vez de 24
    assert len(sphere._precomputed_rings[0][1]) == 97
    assert sphere.gesture_detector.drag_interval == 12

    # 2. Tipografia canônica: Cormorant Garamond por padrão, permitindo alternância para Montserrat
    assert sphere.font_family == config.font_families["cormorant"]
    sphere.set_font_family("montserrat")
    assert sphere.font_family == config.font_families["montserrat"]
    sphere.set_font_family("cormorant")
    assert sphere.font_family == config.font_families["cormorant"]

    # 3. Batching via cv.Path: os anéis e a grade utilizam cv.Path para eliminar sobrecarga de IPC e assegurar 60 FPS
    nodes = [
        {"id": "work_1", "type": "work", "label": "Obra Alpha", "cluster_id": 1, "x3": 0.0, "y3": 0.0, "z3": 0.0},
        {"id": "work_2", "type": "work", "label": "Obra Beta", "cluster_id": 1, "x3": 50.0, "y3": 0.0, "z3": 0.0},
    ]
    sphere.set_data(nodes, [], [{"id": 1, "name": "Cluster 1"}])
    sphere.render(high_detail=True)

    path_shapes = [s for s in sphere.canvas.shapes if isinstance(s, cv.Path)]
    assert len(path_shapes) >= 4  # Anéis agrupados em cv.Path de alta performance

    # Validação da fonte renderizada nos textos
    text_shapes = [s for s in sphere.canvas.shapes if isinstance(s, cv.Text)]
    assert len(text_shapes) >= 1
    assert text_shapes[0].style.font_family == config.font_families["cormorant"]


def test_cosmic_tapestry_and_responsive_toolbar_adaptation():
    """Valida a tapeçaria cósmica profunda (Via Láctea, nebulosas, estrelas espectrais) e adaptação elástica da toolbar."""
    import flet as ft
    import flet.canvas as cv
    from src.configs.settings import COLORS_DARK, COLORS_LIGHT, FONT_FAMILIES, FONT_SIZES, FONT_WEIGHTS, UI
    from src.utils.types import ViewConfig
    from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
    from src.views.knowledge.knowledge_composer import KnowledgeComposer

    config = ViewConfig(
        colors=COLORS_DARK,
        page_fonts={},
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes={},
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts={},
        core_menus={},
        main_view_cards={},
    )

    # 1. Validação da Tapeçaria Cósmica Estelar
    sphere = ArmillaryConstellation3D(
        config=config,
        scale=1.0,
        on_select_node=lambda _: None,
        current_theme_mode="dark",
        canvas_width=1200.0,
        canvas_height=900.0,
    )

    assert len(sphere.milky_way_stream) == 160
    assert len(sphere.nebulae) == 4
    assert len(sphere.starfield) == 72

    sphere.render(high_detail=True)

    # Presença do rio estelar da Via Láctea via cv.Points
    points_shapes = [s for s in sphere.canvas.shapes if isinstance(s, cv.Points)]
    assert len(points_shapes) >= 1
    assert len(points_shapes[0].points) == 160

    # Presença de centelhas estelares de magnitude 1 com spikes ópticos de difração
    diffraction_spikes = [
        s for s in sphere.canvas.shapes
        if isinstance(s, cv.Line) and s.data != "filament"
    ]
    assert len(diffraction_spikes) >= 28  # 14 estrelas-guia x 2 linhas ortogonais

    # 2. Validação da Toolbar Responsiva e do Gradiente Cósmico
    composer = KnowledgeComposer(
        page=None,
        config=config,
        scale=1.0,
        on_navigate=lambda _: None,
        get_graph_data=lambda _: {"nodes": [], "links": [], "clusters": []},
        sync_mesh=lambda: {"vectorized": 0, "clusters": 0},
        get_resonances=lambda *_: [],
        current_theme_mode="dark",
    )

    # Gradiente cósmico profundo de cúpula estelar no viewport
    assert isinstance(composer.viewport_container.gradient, ft.RadialGradient)
    assert "#090D1C" in composer.viewport_container.gradient.colors

    # A) Adaptação no Modo Amplo / Maximizado (avail_w >= 1220)
    composer._update_toolbar_responsive(1350.0)
    assert composer.subtitle_prefix.visible is True
    assert composer.subtitle_dot.visible is True
    assert composer.search_field.width == 200 * composer.scale
    assert composer.sync_button.content.value == "Sincronizar"
    assert composer.d3_button.content.value == "D3.js"

    # B) Adaptação no Modo Normal / Desmaximizado (920 <= avail_w < 1220)
    composer._update_toolbar_responsive(1050.0)
    assert composer.subtitle_prefix.visible is False
    assert composer.subtitle_dot.visible is False
    assert composer.search_field.width == 150 * composer.scale
    assert composer.filter_mode_dropdown.width == 135 * composer.scale
    assert composer.sync_button.content.value == "Sincronizar"

    # C) Adaptação no Modo Compacto / Painel Lateral Aberto (avail_w < 920)
    composer._update_toolbar_responsive(700.0)
    assert composer.subtitle_prefix.visible is False
    assert composer.subtitle_dot.visible is False
    assert composer.search_field.width == 115 * composer.scale
    assert composer.filter_mode_dropdown.width == 110 * composer.scale
    assert composer.sync_button.content.value == "Sync"
    assert composer.d3_button.content.value == "D3"





