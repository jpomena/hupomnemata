"""Bateria de testes de integração para o Modal de Importação Reversa e motor cognitivo Nous.

Valida conformidade estrutural de opções de dropdown, enriquecimento semântico de metadados,
sanitização rigorosa para todos os tipos suportados e persistência íntegra no acervo.
"""

from unittest.mock import MagicMock, patch

import flet as ft

from src.domains import CaseLaw, JournalArticle, MiscDigitalDocument, Statute
from src.services.nous_service import NousAIService
from src.services.settings_service import SettingsService
from src.services.work_form_service import WorkFormService
from src.services.work_service import WorkService
from src.utils.reference_parser import (
    ALL_WORK_TYPES,
    detect_probable_work_type,
)
from src.views.reverse_import_modal import (
    WORK_TYPE_MAP,
    WORK_TYPE_OPTIONS,
    ReverseImportModalDialog,
    sanitize_work_metadata,
)


def test_work_type_options_completeness_and_dropdown_mapping():
    """Garante que todos os tipos de obra conhecidos pelo sistema possuam correspondência exata."""
    option_keys = [k for k, _ in WORK_TYPE_OPTIONS]

    # Verifica os tipos fundamentais requeridos pelo sistema
    expected_types = [
        "editorial_monograph",
        "journal_article",
        "academic_monograph",
        "monographic_proceedings",
        "newspaper_article",
        "statute",
        "caselaw",
        "miscellaneous_digital_document",
    ]
    for exp in expected_types:
        assert exp in option_keys, f"Tipo {exp} não consta em WORK_TYPE_OPTIONS"
        assert exp in WORK_TYPE_MAP, f"Tipo {exp} não consta em WORK_TYPE_MAP"

    # Garante que qualquer tipo inferido por ALL_WORK_TYPES tenha mapeamento no modal
    for parser_type in ALL_WORK_TYPES:
        assert parser_type in WORK_TYPE_MAP, (
            f"Tipo {parser_type} do parser heurístico não possui opção de dropdown no modal."
        )


def test_detect_probable_work_type_all_categories():
    """Testa se as heurísticas do parser predizem corretamente as diferentes famílias de obras."""
    ref_book = "FOUCAULT, Michel. Vigiar e punir. Petrópolis: Vozes, 2014."
    assert detect_probable_work_type(ref_book) == "editorial_monograph"

    ref_journal = (
        "HABERMAS, Jürgen. Ação comunicativa e razão destranscendentalizada. "
        "Cadernos de Filosofia Alemã, v. 23, n. 2, p. 11-28, 2018."
    )
    assert detect_probable_work_type(ref_journal) == "journal_article"

    ref_statute = (
        "BRASIL. Lei nº 10.406, de 10 de janeiro de 2002. Institui o Código Civil. "
        "Diário Oficial da União: seção 1, Brasília, DF, ano 139, n. 8, p. 1-74, 11 jan. 2002."
    )
    assert detect_probable_work_type(ref_statute) == "statute"

    ref_caselaw = (
        "BRASIL. Supremo Tribunal Federal. Recurso Extraordinário 583.955. Relator: Min. Gilmar Mendes. "
        "Julgado em 15/03/2021. Diário da Justiça Eletrônico, 2021."
    )
    assert detect_probable_work_type(ref_caselaw) == "caselaw"

    ref_web = (
        "GOOGLE. Diretrizes de IA Responsável. Disponível em: <https://ai.google/principles/>. "
        "Acesso em: 12 nov. 2024."
    )
    assert detect_probable_work_type(ref_web) == "miscellaneous_digital_document"


def test_sanitize_journal_article_cleans_publisher_and_splits_pages(clean_db):
    """Assegura que para journal_article o publisher seja isolado do journal_title e páginas tratadas."""
    meta_raw = {
        "title": "Ação Comunicativa e Democracia",
        "authors": [{"name": "Jürgen Habermas", "corporation": False}],
        "date_anchor": "15/08/2020",
        "publisher": "Cadernos de Filosofia Alemã",  # IA colocou o nome da revista em publisher
        "journal_title": None,
        "publication_place": "São Paulo",
        "number": "2",
        "volume": "23",
        "part_start_page": "11-28",  # Faixa consolidada no início
        "part_end_page": None,
    }

    sanitized = sanitize_work_metadata(meta_raw, "journal_article")

    assert sanitized["is_partial"] is True
    assert sanitized["journal_title"] == "Cadernos de Filosofia Alemã"
    # Publisher não deve manter o nome do periódico
    assert sanitized["publisher"] == "[s.n.]"
    assert sanitized["part_start_page"] == "11"
    assert sanitized["part_end_page"] == "28"
    assert sanitized["number"] == 2
    assert sanitized["volume"] == 23
    assert sanitized["date_anchor"] == "08/2020"
    assert "parent_bibliographic_resource_id" in sanitized


def test_sanitize_editorial_monograph_chapter_vs_whole_book():
    """Testa se capítulos com 'In:' são marcados como is_partial=True e livros integrais is_partial=False."""
    # Livro integral
    meta_book = {
        "title": "Vigiar e Punir",
        "authors": [{"name": "Michel Foucault", "corporation": False}],
        "date_anchor": "2014",
        "publisher": "Vozes",
        "publication_place": "Petrópolis",
        "raw": "FOUCAULT, Michel. Vigiar e punir. Petrópolis: Vozes, 2014.",
    }
    san_book = sanitize_work_metadata(meta_book, "editorial_monograph")
    assert san_book["is_partial"] is False
    assert san_book["date_anchor"] == "2014"

    # Capítulo de livro
    meta_chapter = {
        "title": "A Escrita de Si",
        "authors": [{"name": "Michel Foucault", "corporation": False}],
        "date_anchor": "2004",
        "publisher": "Forense Universitária",
        "publication_place": "Rio de Janeiro",
        "part_start_page": "120-145",
        "raw": "FOUCAULT, M. A escrita de si. In: Ditos e escritos V. Rio de Janeiro: Forense, 2004. p. 120-145.",
    }
    san_chapter = sanitize_work_metadata(meta_chapter, "editorial_monograph")
    assert san_chapter["is_partial"] is True
    assert san_chapter["part_start_page"] == "120"
    assert san_chapter["part_end_page"] == "145"


def test_sanitize_caselaw_full_date_and_attributes(clean_db):
    """Garante que jurisprudência tenha data DD/MM/AAAA, decisão, tribunal e mídia devidamente configurados."""
    meta_case = {
        "title": "Recurso Extraordinário 583.955",
        "court": "Supremo Tribunal Federal",
        "decision_type": "Acórdão",
        "decision_date": "15/03/2021",
        "case_number": "RE 583.955",
        "rapporteur": "Min. Gilmar Mendes",
        "publication_media": "DJe",
        "date_anchor": "2021",
    }

    san = sanitize_work_metadata(meta_case, "caselaw")
    assert san["is_partial"] is False
    assert san["decision_type"] == "Acórdão"
    assert san["panel"] == "Supremo Tribunal Federal"
    assert san["region"] == "Supremo Tribunal Federal"
    assert san["case_number"] == "RE 583.955"
    assert san["rapporteur"] == "Min. Gilmar Mendes"
    assert san["publication_media"] == "DJe"
    assert san["publication_place"] == "Brasília"
    # Crítico para WorkFormService: deve ser DD/MM/AAAA completo
    assert san["date_anchor"] == "15/03/2021"
    assert san["decision_date"] == "15/03/2021"

    # Testa persistência de caselaw no banco através de WorkFormService e WorkService
    form_service = WorkFormService()
    work_service = WorkService()
    payload = form_service.prepare_payload(san)
    created = work_service.create(payload)
    assert created.id is not None
    works = work_service.list_works()
    matching = [w for w in works if isinstance(w.specific_work, CaseLaw)]
    assert len(matching) == 1
    assert matching[0].specific_work.decision_type == "Acórdão"
    assert matching[0].specific_work.case_number == "RE 583.955"


def test_sanitize_statute_full_date_and_attributes(clean_db):
    """Garante que legislação tenha data DD/MM/AAAA e persistência funcional."""
    meta_statute = {
        "title": "Lei nº 10.406/2002",
        "subtitle": "Código Civil",
        "promulgation_date": "10/01/2002",
        "publication_media": "Diário Oficial da União",
        "date_anchor": "2002",
    }

    san = sanitize_work_metadata(meta_statute, "statute")
    assert san["is_partial"] is False
    assert san["promulgation_date"] == "10/01/2002"
    assert san["date_anchor"] == "10/01/2002"
    assert san["publication_media"] == "Diário Oficial da União"
    assert san["publication_place"] == "Brasília"

    # Testa persistência no banco
    form_service = WorkFormService()
    work_service = WorkService()
    payload = form_service.prepare_payload(san)
    created = work_service.create(payload)
    assert created.id is not None
    works = work_service.list_works()
    matching = [w for w in works if isinstance(w.specific_work, Statute)]
    assert len(matching) == 1
    assert matching[0].specific_work.publication_media == "Diário Oficial da União"


def test_sanitize_miscellaneous_digital_document(clean_db):
    """Garante que documento digital preserve URL, viewed_at e persista no banco."""
    meta_digital = {
        "title": "Manifesto Ágil",
        "url": "https://agilemanifesto.org",
        "access_date": "15/04/2023",
        "date_anchor": "2001",
    }

    san = sanitize_work_metadata(meta_digital, "miscellaneous_digital_document")
    assert san["is_partial"] is False
    assert san["url"] == "https://agilemanifesto.org"
    assert san["viewed_at"] == "15/04/2023"
    assert san["date_anchor"] == "2001"

    form_service = WorkFormService()
    work_service = WorkService()
    payload = form_service.prepare_payload(san)
    created = work_service.create(payload)
    assert created.id is not None
    works = work_service.list_works()
    matching = [w for w in works if isinstance(w.specific_work, MiscDigitalDocument)]
    assert len(matching) == 1
    assert matching[0].specific_work.url == "https://agilemanifesto.org"


def test_nous_ai_extract_includes_suggested_work_type():
    """Garante que o prompt do Nous contenha instruções estruturadas e popule suggested_work_type."""
    settings_mock = MagicMock(spec=SettingsService)
    settings_obj = MagicMock()
    settings_obj.gemini_api_key = "AIzaSyTestKey123"
    settings_mock.load_settings.return_value = settings_obj

    service = NousAIService(settings_service=settings_mock)

    mock_gemini_json = {
        "suggested_work_type": "journal_article",
        "title": "Ação Comunicativa e Razão",
        "subtitle": None,
        "authors": [{"name": "Jürgen Habermas", "corporation": False}],
        "date_anchor": "2018",
        "publisher": "[s.n.]",
        "journal_title": "Cadernos de Filosofia Alemã",
        "volume": 23,
        "number": 2,
        "part_start_page": "11",
        "part_end_page": "28",
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": str(mock_gemini_json)
                            .replace("'", '"')
                            .replace("None", "null")
                            .replace("False", "false")
                        }
                    ]
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_response) as mock_post:
        ok, meta, msg = service.extract_reference_metadata(
            "HABERMAS, J. Ação comunicativa. Cadernos de Filosofia, v. 23, n. 2, p. 11-28, 2018.",
            target_work_type="editorial_monograph",  # Tipo pré-selecionado incorreto
        )
        assert ok
        assert meta["suggested_work_type"] == "journal_article"
        assert meta["journal_title"] == "Cadernos de Filosofia Alemã"
        assert meta["publisher"] == "[s.n.]"

        # Verifica se o prompt transmitido ao Gemini continha orientações de distinção e campos novos
        sent_payload = mock_post.call_args[1]["json"]
        sent_prompt = sent_payload["contents"][0]["parts"][0]["text"]
        assert "suggested_work_type" in sent_prompt
        assert "journal_title" in sent_prompt
        assert "caselaw" in sent_prompt
        assert "statute" in sent_prompt
        assert "Diretrizes de Distinção Rigorosa" in sent_prompt


def test_modal_auto_updates_work_type_from_nous_suggestion(clean_db, view_config):
    """Testa se o modal na Fase 3 adota a classificação sugerida pelo Nous em vez do default heurístico."""
    page = MagicMock(spec=ft.Page)
    page.overlay = []

    settings_mock = MagicMock(spec=SettingsService)
    settings_obj = MagicMock()
    settings_obj.gemini_api_key = "AIzaFakeKey"
    settings_mock.load_settings.return_value = settings_obj

    nous_service = NousAIService(settings_service=settings_mock)
    work_service = WorkService()
    form_service = WorkFormService()

    dialog = ReverseImportModalDialog(
        page=page,
        config=view_config,
        nous_service=nous_service,
        work_service=work_service,
        form_service=form_service,
    )

    dialog.show()
    # Adiciona item com heurística inicial de editorial_monograph
    dialog.items = [
        {
            "raw": "HABERMAS, Jürgen. Ação comunicativa. Cadernos de Filosofia, v. 23, n. 2, p. 11-28, 2018.",
            "work_type": "editorial_monograph",
            "metadata": None,
            "success": False,
            "error": None,
            "selected": True,
        }
    ]

    # Mock do Nous retornando cognitive suggestion de journal_article
    mock_extracted = {
        "suggested_work_type": "journal_article",
        "work_type": "editorial_monograph",
        "title": "Ação Comunicativa",
        "subtitle": None,
        "authors": [{"name": "Jürgen Habermas", "corporation": False}],
        "date_anchor": "2018",
        "journal_title": "Cadernos de Filosofia",
        "volume": 23,
        "number": 2,
        "part_start_page": "11",
        "part_end_page": "28",
        "is_partial": True,
    }

    dialog.progress_label = MagicMock()
    dialog.progress_bar = MagicMock()

    with patch.object(
        nous_service,
        "extract_reference_metadata",
        return_value=(True, mock_extracted, "OK"),
    ):
        dialog._run_extraction_background()

    # Verifica se o tipo do item foi promovido para journal_article conforme a cognição do Nous
    assert dialog.items[0]["work_type"] == "journal_article"
    assert dialog.items[0]["metadata"]["work_type"] == "journal_article"

    # Salva no banco de dados e valida que foi persistido como JournalArticle (além da revista pai)
    dialog._on_save_all_clicked()
    works = work_service.list_works()
    journal_articles = [w for w in works if isinstance(w.specific_work, JournalArticle)]
    assert len(journal_articles) == 1
    assert journal_articles[0].specific_work.title == "Ação comunicativa"


def test_modal_fallback_graceful_on_unknown_type(view_config):
    """Garante que valores estranhos de work_type sofram fallback seguro sem quebrar o Flet."""
    page = MagicMock(spec=ft.Page)
    nous_service = MagicMock(spec=NousAIService)
    work_service = MagicMock(spec=WorkService)
    form_service = MagicMock(spec=WorkFormService)

    dialog = ReverseImportModalDialog(
        page=page,
        config=view_config,
        nous_service=nous_service,
        work_service=work_service,
        form_service=form_service,
    )

    invalid_item = {
        "raw": "Referência com tipo corrompido",
        "work_type": "tipo_inexistente_xpto",
        "metadata": None,
        "success": False,
        "error": None,
        "selected": True,
    }

    card_phase2 = dialog._compose_segment_card(1, invalid_item)
    assert card_phase2 is not None
    # Deve ter feito fallback para editorial_monograph
    assert invalid_item["work_type"] == "editorial_monograph"

    invalid_item["work_type"] = "outro_tipo_invalido"
    card_phase3 = dialog._compose_result_card(1, invalid_item)
    assert card_phase3 is not None
    assert invalid_item["work_type"] == "editorial_monograph"
