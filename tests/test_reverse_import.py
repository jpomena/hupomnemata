"""Testes para o fluxo de importação reversa de referências bibliográficas via Nous."""

from unittest.mock import MagicMock, patch

import flet as ft

from src.domains import AcademicMonograph, EditorialMonograph, JournalArticle
from src.services.nous_service import NousAIService
from src.services.settings_service import SettingsService
from src.services.work_form_service import WorkFormService
from src.services.work_service import WorkService
from src.views.reverse_import_modal import (
    ReverseImportModalDialog,
    sanitize_work_metadata,
)


def test_nous_extract_without_api_key():
    settings_mock = MagicMock(spec=SettingsService)
    settings_obj = MagicMock()
    settings_obj.gemini_api_key = ""
    settings_mock.load_settings.return_value = settings_obj

    service = NousAIService(settings_service=settings_mock)
    assert not service.has_api_key()

    ok, meta, msg = service.extract_reference_metadata("Foucault, M. Vigiar e punir.")
    assert not ok
    assert meta == {}
    assert "Nenhuma chave de API" in msg


def test_nous_extract_with_mock_gemini_success():
    settings_mock = MagicMock(spec=SettingsService)
    settings_obj = MagicMock()
    settings_obj.gemini_api_key = "AIzaSyTestKey123"
    settings_mock.load_settings.return_value = settings_obj

    service = NousAIService(settings_service=settings_mock)
    assert service.has_api_key()

    mock_gemini_json = {
        "title": "Vigiar e Punir",
        "subtitle": "Nascimento da prisão",
        "authors": [{"name": "Michel Foucault", "corporation": False}],
        "date_anchor": "2014",
        "publisher": "Vozes",
        "publication_place": "Petrópolis",
        "edition": 42,
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": '```json\n' + str(mock_gemini_json).replace("'", '"').replace("False", "false") + '\n```'}
                    ]
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_response):
        ok, meta, msg = service.extract_reference_metadata(
            "FOUCAULT, Michel. Vigiar e punir: nascimento da prisão. Petrópolis: Vozes, 2014.",
            target_work_type="editorial_monograph",
        )
        assert ok
        assert meta["title"] == "Vigiar e Punir"
        assert meta["subtitle"] == "Nascimento da prisão"
        assert meta["publisher"] == "Vozes"
        assert meta["publication_place"] == "Petrópolis"
        assert meta["work_type"] == "editorial_monograph"


def test_nous_batch_extract():
    settings_mock = MagicMock(spec=SettingsService)
    settings_obj = MagicMock()
    settings_obj.gemini_api_key = "AIzaSyTestKey"
    settings_mock.load_settings.return_value = settings_obj

    service = NousAIService(settings_service=settings_mock)

    with patch.object(service, "extract_reference_metadata") as mock_extract:
        mock_extract.return_value = (True, {"title": "Test Title"}, "OK")
        progress_calls = []

        def on_prog(idx, total, snippet):
            progress_calls.append((idx, total, snippet))

        items = [
            ("Ref 1", "editorial_monograph"),
            ("Ref 2", "journal_article"),
        ]
        results = service.batch_extract_references(items, on_progress=on_prog)
        assert len(results) == 2
        assert len(progress_calls) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is True


def test_reverse_import_modal_phases_and_persistence(clean_db, view_config):
    page = MagicMock(spec=ft.Page)
    page.overlay = []

    settings_mock = MagicMock(spec=SettingsService)
    settings_obj = MagicMock()
    settings_obj.gemini_api_key = "AIzaFakeKey"
    settings_mock.load_settings.return_value = settings_obj

    nous_service = NousAIService(settings_service=settings_mock)
    work_service = WorkService()
    form_service = WorkFormService()

    success_counts = []
    dialog = ReverseImportModalDialog(
        page=page,
        config=view_config,
        nous_service=nous_service,
        work_service=work_service,
        form_service=form_service,
        on_success=lambda count: success_counts.append(count),
    )

    # 1. Abre o diálogo
    dialog.show()
    assert dialog.is_open
    assert dialog.phase == 1

    # 2. Testa segmentação sem texto (gera erro na UI)
    dialog.input_textarea.value = "   "
    dialog._on_segment_clicked()
    assert dialog.phase == 1
    assert dialog.error_container.visible is True

    # 3. Informa bloco com 2 referências e segmenta
    dialog.input_textarea.value = (
        "FOUCAULT, Michel. Vigiar e punir: nascimento da prisão. Petrópolis: Vozes, 2014.\n\n"
        "HABERMAS, Jürgen. Ação comunicativa. Cadernos de Filosofia, v. 23, n. 2, p. 11-28, 2018."
    )
    dialog._on_segment_clicked()
    assert dialog.phase == 2
    assert len(dialog.items) == 2
    assert dialog.items[0]["work_type"] == "editorial_monograph"
    assert dialog.items[1]["work_type"] == "journal_article"

    # 4. Mock da extração no Nous para as 2 obras
    mock_extracted_1 = {
        "title": "Vigiar e Punir",
        "subtitle": "Nascimento da prisão",
        "authors": [{"name": "Michel Foucault", "corporation": False}],
        "date_anchor": "2014",
        "publisher": "Vozes",
        "publication_place": "Petrópolis",
        "work_type": "editorial_monograph",
    }
    mock_extracted_2 = {
        "title": "Ação comunicativa",
        "subtitle": None,
        "authors": [{"name": "Jürgen Habermas", "corporation": False}],
        "date_anchor": "2018",
        "journal_title": "Cadernos de Filosofia",
        "publication_place": "São Paulo",
        "volume": 23,
        "number": 2,
        "part_start_page": "11",
        "part_end_page": "28",
        "is_partial": True,
        "work_type": "journal_article",
    }

    dialog.items[0]["metadata"] = mock_extracted_1
    dialog.items[0]["success"] = True
    dialog.items[0]["selected"] = True

    dialog.items[1]["metadata"] = mock_extracted_2
    dialog.items[1]["success"] = True
    dialog.items[1]["selected"] = True

    # 5. Salva no banco de dados
    dialog._on_save_all_clicked()
    assert success_counts == [2]
    assert not dialog.is_open

    # 6. Verifica se as obras foram de fato persistidas no banco
    works = work_service.list_works()
    titles = [w.specific_work.title for w in works if w.specific_work]
    assert "Vigiar e punir" in titles
    assert "Ação comunicativa" in titles


def test_sanitize_work_metadata_all_types(clean_db):
    """Garante que metadados brutos sejam enriquecidos para qualquer tipo alvo."""
    base = {
        "title": "Ensaio sobre a Razão",
        "authors": [{"name": "Autor Teste", "corporation": False}],
        "date_anchor": "2021",
        "publisher": "Editora Alfa",
        "publication_place": "Brasília",
    }

    # 1. Monografia editorial
    mono = sanitize_work_metadata(base, "editorial_monograph")
    assert mono["work_type"] == "editorial_monograph"
    assert mono["date_anchor"] == "2021"
    assert mono["is_partial"] is False

    # 2. Artigo de periódico (gera magazine pai e formata MM/AAAA)
    art = sanitize_work_metadata(base, "journal_article")
    assert art["work_type"] == "journal_article"
    assert art["date_anchor"] == "01/2021"
    assert art["is_partial"] is True
    assert art["number"] == 1
    assert "parent_bibliographic_resource_id" in art

    # 3. Monografia acadêmica (tese/dissertação)
    acad = sanitize_work_metadata(base, "academic_monograph")
    assert acad["work_type"] == "academic_monograph"
    assert acad["thesis_type"] == "Dissertação"
    assert acad["defense_year"] == 2021
    assert acad["page_quantity"] == 100

    # 4. Trabalho em anais
    proc = sanitize_work_metadata(base, "monographic_proceedings")
    assert proc["work_type"] == "monographic_proceedings"
    assert proc["event_year"] == 2021
    assert "Anais do Ensaio sobre a Razão" in proc["event_name"]

    # 5. Artigo de jornal (data DD/MM/AAAA)
    news = sanitize_work_metadata(base, "newspaper_article")
    assert news["work_type"] == "newspaper_article"
    assert news["date_anchor"] == "01/01/2021"
    assert news["start_page"] == "s.p."

    # 6. Legislação / Norma
    stat = sanitize_work_metadata(base, "statute")
    assert stat["work_type"] == "statute"
    assert stat["promulgation_date"] == "01/01/2021"
    assert stat["publication_media"] == "Diário Oficial"


def test_work_type_changes_batch_and_individual(clean_db, view_config):
    """Testa a alteração de tipos em lote e individual nas Fases 2 e 3."""
    page = MagicMock(spec=ft.Page)
    page.overlay = []

    settings_mock = MagicMock(spec=SettingsService)
    settings_obj = MagicMock()
    settings_obj.gemini_api_key = "AIzaFakeKey"
    settings_mock.load_settings.return_value = settings_obj

    nous_service = NousAIService(settings_service=settings_mock)
    work_service = WorkService()
    form_service = WorkFormService()

    success_counts = []
    dialog = ReverseImportModalDialog(
        page=page,
        config=view_config,
        nous_service=nous_service,
        work_service=work_service,
        form_service=form_service,
        on_success=lambda count: success_counts.append(count),
    )

    dialog.show()
    dialog.input_textarea.value = (
        "OBRA 1: Teoria dos Sistemas. São Paulo: Martins, 2020.\n\n"
        "OBRA 2: Métodos de Pesquisa. Rio de Janeiro: Vozes, 2022."
    )
    dialog._on_segment_clicked()
    assert dialog.phase == 2
    assert len(dialog.items) == 2

    # Altera tipo de todas na Fase 2 via batch
    dialog.selected_batch_type = "academic_monograph"
    phase2_container = dialog._compose_phase2()
    # Encontra o botão "Aplicar a todas" e simula clique
    batch_bar = phase2_container.content.controls[0]
    btn_apply = batch_bar.content.controls[4]
    btn_apply.on_click(MagicMock())

    assert dialog.items[0]["work_type"] == "academic_monograph"
    assert dialog.items[1]["work_type"] == "academic_monograph"

    # Altera o item 0 individualmente para journal_article na Fase 2
    card0 = dialog._compose_segment_card(1, dialog.items[0])
    type_dropdown = card0.content.controls[0].controls[1].content
    type_dropdown.on_change(MagicMock(control=MagicMock(value="journal_article")))

    assert dialog.items[0]["work_type"] == "journal_article"
    assert dialog.items[1]["work_type"] == "academic_monograph"

    # Simula extração pelo Nous
    dialog.items[0]["metadata"] = {
        "title": "Teoria dos Sistemas",
        "authors": [{"name": "Niklas Luhmann", "corporation": False}],
        "date_anchor": "2020",
        "publisher": "Martins",
        "publication_place": "São Paulo",
        "journal_title": "Revista de Sociologia",
        "work_type": "journal_article",
    }
    dialog.items[0]["success"] = True
    dialog.items[0]["selected"] = True

    dialog.items[1]["metadata"] = {
        "title": "Métodos de Pesquisa",
        "authors": [{"name": "Minayo, M.", "corporation": False}],
        "date_anchor": "2022",
        "publisher": "Vozes",
        "publication_place": "Rio de Janeiro",
        "work_type": "academic_monograph",
    }
    dialog.items[1]["success"] = True
    dialog.items[1]["selected"] = True

    dialog.phase = 3
    dialog._render_current_phase()

    # Salva no acervo
    dialog._on_save_all_clicked()
    assert success_counts == [2]

    # Verifica os modelos das obras no banco
    works = work_service.list_works()
    types_saved = {type(w.specific_work) for w in works if w.specific_work}
    assert JournalArticle in types_saved
    assert AcademicMonograph in types_saved


def test_work_type_change_in_phase3_alters_persistence(clean_db, view_config):
    """Garante que a alteração do tipo na Fase 3 (após extração) seja respeitada no salvamento."""
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
    # Cria item já extraído como editorial_monograph
    dialog.items = [
        {
            "raw": "HABERMAS, Jürgen. Teoria da Ação Comunicativa. 1987.",
            "work_type": "editorial_monograph",
            "metadata": {
                "title": "Teoria da Ação Comunicativa",
                "authors": [{"name": "Jürgen Habermas", "corporation": False}],
                "date_anchor": "1987",
                "publisher": "Taurus",
                "publication_place": "Madrid",
                "work_type": "editorial_monograph",
            },
            "success": True,
            "error": None,
            "selected": True,
        }
    ]
    dialog.phase = 3
    phase3_container = dialog._compose_phase3()

    # Na Fase 3, o usuário altera o tipo no dropdown do cartão para "journal_article"
    # O cartão está dentro da lista de resultados
    results_list = phase3_container.content.controls[2]
    card = results_list.controls[0]
    header_row = card.content.controls[0]
    type_dropdown = header_row.controls[2].content

    # Dispara alteração para journal_article
    type_dropdown.on_change(MagicMock(control=MagicMock(value="journal_article")))
    assert dialog.items[0]["work_type"] == "journal_article"
    assert dialog.items[0]["metadata"]["work_type"] == "journal_article"

    # Salva no acervo
    dialog._on_save_all_clicked()

    # Verifica se salvou como JournalArticle e NÃO como EditorialMonograph
    works = work_service.list_works()
    journal_articles = [w for w in works if isinstance(w.specific_work, JournalArticle)]
    editorial_monographs = [w for w in works if isinstance(w.specific_work, EditorialMonograph)]
    assert len(journal_articles) == 1
    assert len(editorial_monographs) == 0
