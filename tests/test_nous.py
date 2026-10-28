"""Testes unitários para o módulo Nous (Inteligência Artificial, BYOK e Esfera Armilar 3D)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
from src.db import db as db_module
from src.db.db import Base, SessionLocal
from src.domains import (
    BibliographicResource,
    EditorialMonograph,
)
from src.services.settings_service import AppearanceSettings, SettingsService
from src.services.nous_service import NousAIService
from src.utils.types import ViewConfig
from src.views.knowledge.armillary_sphere_3d import ArmillaryConstellation3D
from src.views.nous_composer import NousComposer
from src.views.work_details_popup import WorkDetailsPopup

@pytest.fixture(autouse=True)
def clean_test_db(tmp_path):
    db_file = tmp_path / "nous_test.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    old_engine = db_module.engine
    db_module.engine = engine
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    yield
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()
    db_module.engine = old_engine
    db_module.SessionLocal.configure(bind=old_engine)



@pytest.fixture
def mock_view_config():
    return ViewConfig(
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


def test_effective_description_precedence():
    """Valida a regra de precedência da descrição efetiva da obra:
    custom_description > llm_description > abstract / subtitle.
    """
    res = BibliographicResource()
    res.custom_description = None
    res.llm_description = None

    # Sem nada e sem specific_work -> ""
    assert res.effective_description == ""

    # Com specific_work contendo abstract
    mono = EditorialMonograph(title="Crítica da Razão Pura", abstract="Investigação a priori.")
    res.editorial_monograph = mono
    assert res.effective_description == "Investigação a priori."

    # IA gera síntese -> sobrepõe abstract
    res.llm_description = "Síntese IA das categorias do entendimento e estética transcendental."
    assert res.effective_description == res.llm_description

    # Usuário define sua própria interpretação -> sobrepõe IA
    res.custom_description = "Minha interpretação crítica do kantismo."
    assert res.effective_description == "Minha interpretação crítica do kantismo."

    # Limpando custom -> retorna à síntese da IA
    res.custom_description = None
    assert res.effective_description == res.llm_description


def test_appearance_settings_gemini_key(tmp_path):
    """Valida persistência e recuperação do campo gemini_api_key nas configurações."""
    storage = tmp_path / "user_preferences.json"
    service = SettingsService(storage_path=storage)

    settings = service.load_settings()
    assert settings.gemini_api_key == ""

    settings.gemini_api_key = "AIzaSyTestKey123"
    service.save_settings(settings)

    reloaded = service.load_settings()
    assert reloaded.gemini_api_key == "AIzaSyTestKey123"


def test_nous_service_api_key_management(tmp_path):
    """Valida que o NousAIService delega a leitura e gravação da chave de forma confiável."""
    storage = tmp_path / "user_preferences.json"
    settings_srv = SettingsService(storage_path=storage)
    nous_srv = NousAIService(settings_service=settings_srv)

    assert nous_srv.get_api_key() == ""
    assert nous_srv.save_api_key("AIzaSyMyCustomKey") is True
    assert nous_srv.get_api_key() == "AIzaSyMyCustomKey"


def test_nous_service_test_connection_empty():
    """Valida rejeição imediata quando nenhuma chave foi fornecida."""
    nous_srv = NousAIService()
    ok, msg = nous_srv.test_connection("")
    assert ok is False
    assert "Nenhuma chave de API" in msg


def test_nous_service_test_connection_success(monkeypatch):
    """Valida autenticação bem-sucedida via mock do Gemini REST API."""
    nous_srv = NousAIService()

    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "OK"}]}}
                ]
            }

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json=None):
            return MockResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)
    ok, msg = nous_srv.test_connection("AIzaSyValidKey")
    assert ok is True
    assert "sucesso" in msg.lower()


def test_nous_service_test_connection_error(monkeypatch):
    """Valida erro HTTP 400 da API Gemini com mensagem de chave inválida."""
    nous_srv = NousAIService()

    class MockErrorResponse:
        status_code = 400

        def json(self):
            return {
                "error": {
                    "message": "API key not valid. Please pass a valid API key."
                }
            }

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json=None):
            return MockErrorResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)
    ok, msg = nous_srv.test_connection("AIzaSyInvalidKey")
    assert ok is False
    assert "API key not valid" in msg


def test_nous_service_generate_and_override_work_description(monkeypatch, tmp_path):
    """Valida fluxo completo de geração e sobreposição de síntese de uma obra."""
    storage = tmp_path / "user_preferences.json"
    settings_srv = SettingsService(storage_path=storage)
    settings_srv.save_settings(AppearanceSettings(gemini_api_key="AIzaSyValidKey"))

    mock_knowledge = MagicMock()
    nous_srv = NousAIService(
        settings_service=settings_srv,
        knowledge_service=mock_knowledge,
    )

    # 1. Cria uma obra associada no banco real
    with SessionLocal() as session:
        res = BibliographicResource()
        mono = EditorialMonograph(
            title="Fenomenologia do Espírito",
            display_year="1807",
            abstract="A dialética da consciência ao saber absoluto.",
        )
        res.editorial_monograph = mono
        session.add(res)
        session.commit()
        work_id = res.id

    # 2. Mock do retorno do Gemini
    class MockGenerateResponse:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "Obra hegeliana que delineia os estágios formativos da consciência."
                                }
                            ]
                        }
                    }
                ]
            }

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json=None):
            return MockGenerateResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)

    # 3. Executa a geração
    ok, generated_text = nous_srv.generate_work_description(work_id)
    assert ok is True
    assert "hegeliana" in generated_text

    # Verifica persistência no banco
    with SessionLocal() as session:
        res_db = session.get(BibliographicResource, work_id)
        assert res_db.llm_description == generated_text
        assert res_db.effective_description == generated_text

    # Verifica que re-vetorização foi invocada
    mock_knowledge.revectorize_work.assert_called_with(work_id)

    # 4. Usuário sobrepõe texto manualmente
    custom = "Minha anotação fenomenológica pessoal."
    nous_srv.override_work_description(work_id, custom)

    with SessionLocal() as session:
        res_db = session.get(BibliographicResource, work_id)
        assert res_db.custom_description == custom
        assert res_db.effective_description == custom

    # 5. Lista status das obras
    status_list = nous_srv.list_works_ai_status()
    matching = [w for w in status_list if w["id"] == work_id]
    assert len(matching) == 1
    assert matching[0]["status_label"] == "Personalizada"


def test_armillary_sphere_3d_math(mock_view_config):
    """Valida a projeção tridimensional em perspectiva da Esfera Armilar."""
    sphere = ArmillaryConstellation3D(
        config=mock_view_config,
        scale=1.0,
        on_select_node=lambda _: None,
        canvas_width=800.0,
        canvas_height=600.0,
    )

    # Verifica parâmetros de câmera e projeção
    assert sphere.canvas_width == 800.0
    assert sphere.canvas_height == 600.0
    assert sphere.camera_distance > 0

    # Ponto na origem projeta no centro da tela (400, 300)
    sx, sy, sz = sphere._project_point(0.0, 0.0, 0.0)
    assert pytest.approx(sx, 1.0) == 400.0
    assert pytest.approx(sy, 1.0) == 300.0

    # Zoom in e zoom out respeitam limites
    sphere._handle_scroll(SimpleNamespace(scroll_delta_y=100.0))
    assert sphere.camera_distance <= 1200.0

    sphere._handle_scroll(SimpleNamespace(scroll_delta_y=-2000.0))
    assert sphere.camera_distance >= 280.0


def test_nous_composer_instantiation(mock_view_config):
    """Valida renderização e montagem do compositor do Menu Nous."""
    mock_srv = MagicMock()
    mock_srv.get_api_key.return_value = "AIzaSyTest"
    mock_srv.list_works_ai_status.return_value = [
        {
            "id": 1,
            "title": "Ensaio sobre a Cegueira",
            "authors": "José Saramago",
            "year": "1995",
            "has_custom": False,
            "has_llm": True,
            "status_label": "Síntese IA",
            "status_color": "#896200",
            "llm_description": "Alegoria sobre a condição humana e a desintegração social.",
            "custom_description": "",
            "effective_description": "Alegoria sobre a condição humana.",
            "snippet": "Alegoria sobre a condição humana...",
        }
    ]

    composer = NousComposer(
        page=None,
        config=mock_view_config,
        scale=1.0,
        on_navigate=lambda _: None,
        nous_service=mock_srv,
    )
    control = composer.compose()
    assert control is not None


def test_work_details_popup_synthesis_rendering(mock_view_config):
    """Valida que o popup de detalhes da obra inclui a seção de síntese epistemológica."""
    res = BibliographicResource()
    res.id = 99
    res.llm_description = "Síntese epistemológica gerada pela inteligência do Nous."
    res.custom_description = None

    mono = EditorialMonograph(
        title="Discurso do Método",
        display_year="1637",
        abstract="Regras para a direção do espírito.",
    )
    res.editorial_monograph = mono

    popup = WorkDetailsPopup(
        resource=res,
        config=mock_view_config,
        on_close=lambda: None,
        page=None,
        nous_service=MagicMock(),
    )
    dialog = popup.compose()
    assert dialog is not None
    assert dialog.title.value == "Discurso do Método"


def test_nous_service_test_connection_404_fallback(monkeypatch):
    """Valida fallback automático de modelo quando o primeiro modelo retorna 404."""
    nous_srv = NousAIService()

    calls = []

    class MockResponse404:
        status_code = 404
        def json(self):
            return {"error": {"message": "Model not found"}}

    class MockResponse200:
        status_code = 200
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, json=None):
            calls.append(url)
            if "gemini-1.5-flash" in url:
                return MockResponse404()
            return MockResponse200()

    monkeypatch.setattr(httpx, "Client", MockClient)
    ok, msg = nous_srv.test_connection("AIzaSyValidKey")
    assert ok is True
    assert len(calls) == 2
    assert "gemini-2.0-flash" in calls[1]
    assert nous_srv.preferred_model == "gemini-2.0-flash"


def test_nous_composer_error_contrast_colors(mock_view_config):
    """Valida contraste dinâmico de cores de erro no tema claro vs escuro."""
    composer_dark = NousComposer(
        page=None,
        config=mock_view_config,
        scale=1.0,
        on_navigate=lambda _: None,
        current_theme_mode="dark",
    )
    dark_txt, dark_bg = composer_dark._get_error_colors()
    assert dark_txt == "#FF6B6B"  # Claro no fundo escuro

    composer_light = NousComposer(
        page=None,
        config=mock_view_config,
        scale=1.0,
        on_navigate=lambda _: None,
        current_theme_mode="light",
    )
    light_txt, light_bg = composer_light._get_error_colors()
    assert light_txt == "#B71C1C"  # Escuro no fundo claro


def test_nous_composer_open_ai_studio(monkeypatch, mock_view_config):
    """Valida acionamento do navegador para o link do Google AI Studio."""
    opened_urls = []
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda url: opened_urls.append(url) or True)

    composer = NousComposer(
        page=None,
        config=mock_view_config,
        scale=1.0,
        on_navigate=lambda _: None,
    )
    composer._handle_open_ai_studio(None)
    assert len(opened_urls) == 1
    assert "aistudio.google.com" in opened_urls[0]


def test_nous_composer_single_generate_visual_feedback(monkeypatch, mock_view_config):
    """Valida que o acionamento de geração individual ativa o estado visual de processamento em thread."""
    from types import SimpleNamespace
    import time

    dummy_page = SimpleNamespace(
        overlay=[],
        update=lambda: None,
    )
    mock_service = SimpleNamespace(
        get_api_key=lambda: "dummy_key",
        list_works_ai_status=lambda: [
            {
                "id": 1,
                "title": "Obra de Teste",
                "authors": "Autor X",
                "year": "2020",
                "status_label": "Pendente",
                "status_color": "#FF0000",
                "snippet": "",
                "has_llm": False,
                "has_custom": False,
            }
        ],
        generate_work_description=lambda wid: (True, "Síntese gerada"),
    )

    composer = NousComposer(
        page=dummy_page,
        config=mock_view_config,
        scale=1.0,
        on_navigate=lambda _: None,
        nous_service=mock_service,
    )
    composer.compose()
    assert 1 not in composer.generating_work_ids
    composer._handle_single_generate(1)

    # Espera a thread de background concluir
    for _ in range(50):
        if 1 not in composer.generating_work_ids:
            break
        time.sleep(0.02)

    assert 1 not in composer.generating_work_ids
    assert len(dummy_page.overlay) >= 2
