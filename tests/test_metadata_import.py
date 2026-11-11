"""Testes unitários do serviço de metadados e importação (DOI, ISBN, ISSN)."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.metadata_service import (
    IdentifierType,
    ImportedMetadata,
    MetadataService,
    clean_doi,
    clean_isbn,
    clean_issn,
    detect_identifier,
)


def test_clean_doi():
    assert clean_doi("10.1038/nature.2014.14583") == "10.1038/nature.2014.14583"
    assert clean_doi("https://doi.org/10.1038/nature.2014.14583") == "10.1038/nature.2014.14583"
    assert clean_doi("http://dx.doi.org/10.1016/j.cell.2020.02.052") == "10.1016/j.cell.2020.02.052"
    assert clean_doi("doi: 10.1000/182") == "10.1000/182"


def test_clean_isbn():
    assert clean_isbn("978-85-7559-484-1") == "9788575594841"
    assert clean_isbn("0-14-044913-2") == "0140449132"
    assert clean_isbn("ISBN: 9788575594841") == "9788575594841"
    assert clean_isbn("ISBN-13: 978-85-7559-484-1") == "9788575594841"


def test_clean_issn():
    assert clean_issn("0101-3300") == "0101-3300"
    assert clean_issn("01013300") == "0101-3300"
    assert clean_issn("issn: 2317-1782") == "2317-1782"
    assert clean_issn("2448-0959") == "2448-0959"


def test_detect_identifier():
    assert detect_identifier("10.1038/nature.2014.14583") == (
        IdentifierType.DOI,
        "10.1038/nature.2014.14583",
    )
    assert detect_identifier("https://doi.org/10.1038/s41586-020-2003-4") == (
        IdentifierType.DOI,
        "10.1038/s41586-020-2003-4",
    )
    assert detect_identifier("978-85-7559-484-1") == (
        IdentifierType.ISBN,
        "9788575594841",
    )
    assert detect_identifier("0140449132") == (
        IdentifierType.ISBN,
        "0140449132",
    )
    assert detect_identifier("0101-3300") == (
        IdentifierType.ISSN,
        "0101-3300",
    )
    assert detect_identifier("23171782") == (
        IdentifierType.ISSN,
        "2317-1782",
    )
    assert detect_identifier("invalid string") == (
        IdentifierType.UNKNOWN,
        "invalid string",
    )
    assert detect_identifier("") == (IdentifierType.UNKNOWN, "")


def test_map_csl_json_journal_article():
    service = MetadataService()
    csl_sample = {
        "type": "journal-article",
        "title": "A Nova Razão do Mundo: Ensaio sobre a sociedade",
        "container-title": "Revista de Economia Política",
        "publisher": "Editora 34",
        "volume": "42",
        "issue": "3",
        "page": "150-175",
        "issued": {"date-parts": [[2021, 5, 12]]},
        "ISSN": ["1809-4538"],
        "author": [
            {"family": "Dardot", "given": "Pierre"},
            {"family": "Laval", "given": "Christian"},
            {"literal": "Coletivo Pensamento Crítico"},
        ],
        "abstract": "<p>Um ensaio fundamental sobre neoliberalismo contemporâneo.</p>",
    }

    result = service._map_csl_json(csl_sample, raw_doi="10.1234/test", normalized_doi="10.1234/test")
    assert result.identifier_type == IdentifierType.DOI
    assert result.work_type == "journal_article"
    assert result.values["title"] == "A Nova Razão do Mundo"
    assert result.values["subtitle"] == "Ensaio sobre a sociedade"
    assert result.values["journal_title"] == "Revista de Economia Política"
    assert result.values["publisher"] == "Editora 34"
    assert result.values["volume"] == "42"
    assert result.values["number"] == "3"
    assert result.values["part_start_page"] == "150"
    assert result.values["part_end_page"] == "175"
    assert result.values["display_year"] == "2021"
    assert result.values["date_anchor"] == "12/05/2021"
    assert result.values["issn"] == "1809-4538"
    assert result.values["abstract"] == "Um ensaio fundamental sobre neoliberalismo contemporâneo."

    assert len(result.authors) == 3
    assert result.authors[0]["name"] == "Pierre Dardot"
    assert result.authors[0]["corporation"] is False
    assert result.authors[1]["name"] == "Christian Laval"
    assert result.authors[2]["name"] == "Coletivo Pensamento Crítico"
    assert result.authors[2]["corporation"] is True


def test_map_brasil_api_isbn():
    service = MetadataService()
    sample = {
        "isbn": "9788575594841",
        "title": "A nova razão do mundo: ensaio sobre a sociedade neoliberal",
        "subtitle": None,
        "authors": ["Pierre Dardot", "Christian Laval"],
        "publisher": "Boitempo",
        "year": 2016,
        "page_count": 416,
        "dimensions": "21 x 14 cm",
        "synopsis": "Obra crítica sobre a racionalidade neoliberal.",
    }

    result = service._map_brasil_api(sample, raw_isbn="978-85-7559-484-1", normalized_isbn="9788575594841")
    assert result.identifier_type == IdentifierType.ISBN
    assert result.work_type == "editorial_monograph"
    assert result.values["title"] == "A nova razão do mundo"
    assert result.values["subtitle"] == "ensaio sobre a sociedade neoliberal"
    assert result.values["publisher"] == "Boitempo"
    assert result.values["display_year"] == "2016"
    assert result.values["date_anchor"] == "01/01/2016"
    assert result.values["page_quantity"] == "416"
    assert result.values["dimensions"] == "21 x 14 cm"
    assert result.values["abstract"] == "Obra crítica sobre a racionalidade neoliberal."
    assert len(result.authors) == 2
    assert result.authors[0]["name"] == "Pierre Dardot"
    assert result.authors[1]["name"] == "Christian Laval"


def test_map_open_library_isbn():
    service = MetadataService()
    sample = {
        "title": "Crime and Punishment",
        "publishers": ["Penguin Classics"],
        "publish_date": "2003",
        "number_of_pages": 671,
        "authors": [{"name": "Fyodor Dostoevsky"}],
    }

    result = service._map_open_library(sample, raw_isbn="9780140449136", normalized_isbn="9780140449136")
    assert result.identifier_type == IdentifierType.ISBN
    assert result.work_type == "editorial_monograph"
    assert result.values["title"] == "Crime and Punishment"
    assert result.values["publisher"] == "Penguin Classics"
    assert result.values["display_year"] == "2003"
    assert result.values["page_quantity"] == "671"
    assert len(result.authors) == 1
    assert result.authors[0]["name"] == "Fyodor Dostoevsky"


def test_fetch_issn_mock():
    service = MetadataService()
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {
            "title": "Novos Estudos - CEBRAP",
            "publisher": "Centro Brasileiro de Análise e Planejamento",
        }
    }
    mock_client.get.return_value = mock_resp

    result = service.fetch_issn("0101-3300", client=mock_client)
    assert result.identifier_type == IdentifierType.ISSN
    assert result.work_type == "periodical_collection"
    assert result.values["title"] == "Novos Estudos - CEBRAP"
    assert result.values["journal_title"] == "Novos Estudos - CEBRAP"
    assert result.values["publisher"] == "Centro Brasileiro de Análise e Planejamento"
    assert result.values["issn"] == "0101-3300"


def test_resolve_dispatches_correctly():
    service = MetadataService()

    with patch.object(service, "fetch_doi") as mock_doi:
        mock_doi.return_value = MagicMock(spec=ImportedMetadata)
        service.resolve("10.1038/nature.2014.14583")
        mock_doi.assert_called_once_with("10.1038/nature.2014.14583", client=None)

    with patch.object(service, "fetch_isbn") as mock_isbn:
        mock_isbn.return_value = MagicMock(spec=ImportedMetadata)
        service.resolve("978-85-7559-484-1")
        mock_isbn.assert_called_once_with("9788575594841", client=None)

    with patch.object(service, "fetch_issn") as mock_issn:
        mock_issn.return_value = MagicMock(spec=ImportedMetadata)
        service.resolve("0101-3300")
        mock_issn.assert_called_once_with("0101-3300", client=None)

    with pytest.raises(ValueError, match="Identificador não reconhecido"):
        service.resolve("random string")


def test_check_local_duplicate():
    from src.services.metadata_service import check_local_duplicate

    mock_session = MagicMock()
    mock_work = MagicMock()
    mock_work.bib_res_id = 42
    mock_work.title = "O Capital"
    mock_work.isbn = "978-85-7559-484-1"

    # Simular busca por ISBN
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_work]

    with patch("src.services.metadata_service.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__enter__.return_value = mock_session
        result = check_local_duplicate(IdentifierType.ISBN, "9788575594841")
        assert result == (42, "O Capital")

        # Teste quando não há duplicidade
        mock_session.query.return_value.filter.return_value.all.return_value = []
        result_none = check_local_duplicate(IdentifierType.ISBN, "0000000000000")
        assert result_none is None


def _test_config():
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


def test_import_modal_dialog_detection_and_badges():
    from types import SimpleNamespace
    from src.views.import_modal import ImportModalDialog

    page = SimpleNamespace(show_dialog=MagicMock(), pop_dialog=MagicMock(), update=MagicMock())
    config = _test_config()
    on_success = MagicMock()
    modal = ImportModalDialog(page=page, config=config, on_success=on_success)
    modal.show()
    assert modal.is_open is True
    assert page.show_dialog.called

    # 1. Simular digitação de DOI
    mock_event = SimpleNamespace(control=SimpleNamespace(value="10.1038/nature.2014.14583"))
    modal._on_input_change(mock_event)
    assert modal.badge_container.visible is True
    assert "DOI Detectado" in modal.badge_container.content.content.controls[-1].value

    # 2. Simular digitação de ISBN
    mock_event.control.value = "978-85-7559-484-1"
    modal._on_input_change(mock_event)
    assert modal.badge_container.visible is True
    assert "ISBN Detectado" in modal.badge_container.content.content.controls[-1].value

    # 3. Simular digitação de ISSN
    mock_event.control.value = "0101-3300"
    modal._on_input_change(mock_event)
    assert modal.badge_container.visible is True
    assert "ISSN Detectado" in modal.badge_container.content.content.controls[-1].value

    # 4. Formato desconhecido
    mock_event.control.value = "texto aleatorio"
    modal._on_input_change(mock_event)
    assert modal.badge_container.visible is True
    assert "desconhecido" in modal.badge_container.content.content.controls[-1].value

    modal.close()
    assert modal.is_open is False


def test_import_modal_duplicate_warning_and_force_continue():
    from types import SimpleNamespace
    from src.views.import_modal import ImportModalDialog

    page = SimpleNamespace(show_dialog=MagicMock(), pop_dialog=MagicMock(), update=MagicMock())
    config = _test_config()
    on_success = MagicMock()
    modal = ImportModalDialog(page=page, config=config, on_success=on_success)
    modal.show()

    modal.input_field.value = "978-85-7559-484-1"

    # Simular duplicidade encontrada
    with patch("src.views.import_modal.check_local_duplicate") as mock_check:
        mock_check.return_value = (10, "Obra Existente")
        modal._on_search_clicked()

        assert modal.duplicate_box.visible is True
        assert "Obra Existente" in modal.duplicate_box.content.content.controls[1].value

        # Forçar continuação
        with patch.object(modal, "_execute_remote_search") as mock_exec:
            # Encontrar o botão "Importar como nova"
            buttons = modal.duplicate_box.content.content.controls[2].controls
            force_btn = buttons[1]
            force_btn.on_click(None)
            assert modal.ignore_duplicate is True
            assert mock_exec.called


def test_works_composer_header_has_no_import_button():
    from src.views.works import WorksComposer

    config = _test_config()
    composer = WorksComposer(
        scale=1,
        config=config,
        works=[],
        on_navigate=lambda _d: None,
        on_work_click=lambda _r: None,
        on_edit_work=lambda _r: None,
        format_reference=lambda _r: None,
        on_copy_reference=lambda _r: None,
        on_delete_work=lambda _r: None,
    )
    body = composer._compose_body()
    header = body.controls[0]
    # Header actions deve conter apenas o botão "Nova obra"
    buttons = header.content.controls[1].controls
    assert len(buttons) == 1
    assert buttons[0].content.controls[-1].value == "Nova obra"


def test_core_composer_palette_has_import_action():
    import inspect
    from unittest.mock import MagicMock
    from src.views.core_composer import CoreComposer

    config = _test_config()
    called = []
    page = MagicMock()
    sig = inspect.signature(CoreComposer.__init__)
    kwargs = {}
    for param_name in sig.parameters:
        if param_name in ("self", "args", "kwargs"):
            continue
        kwargs[param_name] = MagicMock()
    kwargs["page"] = page
    kwargs["scale"] = 1.0
    kwargs["config"] = config
    kwargs["on_import_work"] = lambda: called.append(True)

    composer = CoreComposer(**kwargs)
    composer.open_palette()
    assert composer.palette is not None
    # Verificar se a ação de importação está presente nas ações da paleta
    import_actions = [a for a in composer.palette.actions if "Importar" in a[1]]
    assert len(import_actions) == 1
    icon, label, shortcut, handler = import_actions[0]
    assert label == "Importar obra (DOI, ISBN, ISSN)"
    assert shortcut == "⌘I"
    handler()
    assert called == [True]


def test_work_insert_modal_has_import_button_and_applies_metadata():
    from types import SimpleNamespace
    from src.views.work_insert_modal import WorkInsertModalComposer
    from src.services.metadata_service import ImportedMetadata, IdentifierType

    config = _test_config()
    page = SimpleNamespace(update=MagicMock(), show_dialog=MagicMock(), pop_dialog=MagicMock())
    composer = WorkInsertModalComposer(
        page=page,
        config=config,
        on_save=lambda _data: True,
    )
    modal = composer.compose()
    header = modal.composer._header()
    # No header, deve haver o botão Importar e o botão Fechar
    row = header.content
    title = row.controls[0]
    import_btn = row.controls[1]
    close_btn = row.controls[2]

    assert title.value == "Nova obra"
    assert import_btn.content.controls[-1].value == "Importar"

    # Simular aplicação de metadados importados
    fake_meta = ImportedMetadata(
        identifier_type=IdentifierType.ISBN,
        raw_identifier="9780547539683",
        normalized_identifier="9780547539683",
        work_type="editorial_monograph",
        values={
            "title": "The Hobbit",
            "subtitle": "There and Back Again",
            "publication_city": "Boston",
            "publisher": "Houghton Mifflin",
            "publication_year": "2012",
        },
        authors=[
            {"name": "J. R. R. Tolkien", "given_names": "J. R. R.", "last_name": "Tolkien", "corporation": False}
        ],
    )
    composer.apply_imported_metadata(fake_meta)

    # Verificar se os campos foram aplicados
    assert composer.selected.key == "editorial_monograph"
    assert composer.stored_values["title"] == "The Hobbit"
    assert composer.stored_values["subtitle"] == "There and Back Again"
    assert composer.stored_values["publisher"] == "Houghton Mifflin"
    assert len(composer.author_references) == 1
    assert composer.author_references[0]["name"] == "J. R. R. Tolkien"
    # Campos renderizados
    assert composer.fields["title"].value == "The Hobbit"
    assert composer.fields["subtitle"].value == "There and Back Again"
    assert composer.fields["publisher"].value == "Houghton Mifflin"


def test_work_insert_modal_hides_import_button_in_edit_and_parent_mode():
    from types import SimpleNamespace
    from src.views.work_insert_modal import WorkInsertModalComposer

    config = _test_config()
    page = SimpleNamespace(update=MagicMock(), show_dialog=MagicMock(), pop_dialog=MagicMock())

    # Edit mode
    edit_composer = WorkInsertModalComposer(
        page=page,
        config=config,
        on_save=lambda _data: True,
        edit_mode=True,
    )
    header_edit = edit_composer._header()
    assert len(header_edit.content.controls) == 2  # title e close

    # Parent mode
    parent_composer = WorkInsertModalComposer(
        page=page,
        config=config,
        on_save=lambda _data: True,
        parent_mode=True,
    )
    header_parent = parent_composer._header()
    assert len(header_parent.content.controls) == 2  # title e close


@pytest.mark.anyio
async def test_import_modal_execute_remote_search_async():
    from types import SimpleNamespace
    from src.views.import_modal import ImportModalDialog
    import asyncio
    import inspect

    success_results = []
    def fake_run_task(handler, *args, **kwargs):
        # Asynchronously schedule the coroutine handler like Flet's run_task
        assert inspect.iscoroutinefunction(handler), "run_task handler must be a coroutine function"
        return asyncio.create_task(handler(*args, **kwargs))

    page = SimpleNamespace(
        show_dialog=MagicMock(),
        pop_dialog=MagicMock(),
        update=MagicMock(),
        run_task=fake_run_task,
    )
    config = _test_config()
    modal = ImportModalDialog(
        page=page,
        config=config,
        on_success=lambda meta: success_results.append(meta),
    )
    modal.input_field.value = "978-85-7559-484-1"

    fake_meta = MagicMock(spec=ImportedMetadata)
    with patch.object(modal.service, "resolve", return_value=fake_meta):
        modal._execute_remote_search()
        await asyncio.sleep(0.05)

        assert len(success_results) == 1
        assert success_results[0] == fake_meta
        assert modal.loading is False


def test_find_or_create_magazine():
    from src.services.metadata_service import find_or_create_magazine
    from src.db.db import SessionLocal
    from src.domains.core_domain import BibliographicResource
    from src.domains.periodicals import Magazine
    from sqlalchemy import delete

    mag_id, mag_title = find_or_create_magazine("Revista de Teste Temporária", "São Paulo")
    assert mag_id > 0
    assert mag_title == "Revista de Teste Temporária"

    # Segunda chamada com case diferente deve retornar o mesmo id sem duplicar
    mag_id_2, mag_title_2 = find_or_create_magazine("revista de teste temporária")
    assert mag_id_2 == mag_id
    assert mag_title_2 == "Revista de Teste Temporária"

    with pytest.raises(ValueError):
        find_or_create_magazine("   ")

    # Limpar registro criado no teste
    with SessionLocal() as session:
        session.execute(delete(Magazine).where(Magazine.bib_res_id == mag_id))
        session.execute(delete(BibliographicResource).where(BibliographicResource.id == mag_id))
        session.commit()


def test_work_insert_modal_auto_provisions_magazine_for_journal_article():
    from types import SimpleNamespace
    from src.views.work_insert_modal import WorkInsertModalComposer
    from src.services.metadata_service import ImportedMetadata, IdentifierType
    from src.db.db import SessionLocal
    from src.domains.core_domain import BibliographicResource
    from src.domains.periodicals import Magazine
    from sqlalchemy import delete

    config = _test_config()
    page = SimpleNamespace(update=MagicMock(), show_dialog=MagicMock(), pop_dialog=MagicMock())
    composer = WorkInsertModalComposer(
        page=page,
        config=config,
        on_save=lambda _data: True,
    )
    composer.compose()

    meta_article = ImportedMetadata(
        identifier_type=IdentifierType.DOI,
        raw_identifier="10.1016/j.cell.2020.02.052",
        normalized_identifier="10.1016/j.cell.2020.02.052",
        work_type="journal_article",
        values={
            "title": "Cryo-EM structure of the SARS-CoV-2 spike",
            "journal_title": "Cell Research Journal",
            "volume": "181",
            "number": "2",
            "part_start_page": "271",
            "date_anchor": "15/03/2020",
        },
        authors=[{"name": "Daniel Wrapp", "given_names": "Daniel", "last_name": "Wrapp", "corporation": False}],
    )

    composer.apply_imported_metadata(meta_article)

    assert composer.selected.key == "journal_article"
    assert composer.parent_work_id is not None
    assert composer.parent_work_id > 0
    assert composer.parent_work_search == "Cell Research Journal"
    collected = composer._collect()
    assert collected["parent_bibliographic_resource_id"] == composer.parent_work_id

    # Limpar registro criado no teste
    with SessionLocal() as session:
        session.execute(delete(Magazine).where(Magazine.bib_res_id == composer.parent_work_id))
        session.execute(delete(BibliographicResource).where(BibliographicResource.id == composer.parent_work_id))
        session.commit()




