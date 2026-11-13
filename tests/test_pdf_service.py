from pathlib import Path
import pytest

from src.db.db import SessionLocal, init_db
from src.domains import BibliographicResource, EditorialMonograph
from src.services.pdf_service import PdfService


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def dummy_pdf(tmp_path: Path) -> Path:
    """Gera um arquivo PDF de 2 páginas com texto vetorial para testes."""
    import pymupdf

    pdf_path = tmp_path / 'sample_doc.pdf'
    doc = pymupdf.open()
    p1 = doc.new_page(width=200, height=300)
    p1.insert_text((20, 50), "Texto de teste da pagina 1")
    p2 = doc.new_page(width=200, height=300)
    p2.insert_text((20, 50), "Texto de teste da pagina 2")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def test_resource():
    """Cria uma obra bibliográfica para os testes de vínculo."""
    with SessionLocal() as session:
        resource = BibliographicResource()
        work = EditorialMonograph(
            title='Tratado de Mecânica Lógica',
            publication_place='Marte',
        )
        resource.editorial_monograph = work
        session.add(resource)
        session.commit()
        res_id = resource.id

    yield res_id

    # Teardown seguro
    with SessionLocal() as session:
        res = session.get(BibliographicResource, res_id)
        if res:
            if res.editorial_monograph:
                session.delete(res.editorial_monograph)
            session.delete(res)
            session.commit()


def test_attach_and_detach_pdf(tmp_path: Path, dummy_pdf: Path, test_resource: int):
    service = PdfService(storage_dir=tmp_path / 'storage')

    # Anexa o PDF
    info = service.attach_pdf(
        bib_res_id=test_resource,
        source_path=dummy_pdf,
        original_filename='manual.pdf',
    )

    assert info['bib_res_id'] == test_resource
    assert info['pdf_filename'] == 'manual.pdf'
    assert info['pdf_page_count'] == 2
    assert len(info['pdf_sha256']) == 64
    assert Path(info['pdf_absolute_path']).exists()

    # Consulta info
    retrieved = service.get_pdf_info(test_resource)
    assert retrieved is not None
    assert retrieved['pdf_filename'] == 'manual.pdf'
    assert retrieved['file_exists'] is True

    # Desvincula e apaga
    detached = service.detach_pdf(test_resource, delete_file=True)
    assert detached is True
    assert not Path(info['pdf_absolute_path']).exists()

    # Verifica banco
    assert service.get_pdf_info(test_resource) is None


def test_pdf_annotations_and_extract_fragment(
    tmp_path: Path, dummy_pdf: Path, test_resource: int
):
    service = PdfService(storage_dir=tmp_path / 'storage')
    service.attach_pdf(test_resource, dummy_pdf)

    # Salva anotação
    annotation = service.save_annotation(
        bib_res_id=test_resource,
        page_number=1,
        selected_text='Omnissiah guia os espíritos das máquinas.',
        rect_json='[{"x1": 10, "y1": 20, "x2": 100, "y2": 40}]',
        color='#F59E0B',
        note='Passagem fundamental.',
    )

    assert annotation['id'] is not None
    assert annotation['page_number'] == 1
    assert annotation['selected_text'] == 'Omnissiah guia os espíritos das máquinas.'

    # Lista anotações
    ann_list = service.list_annotations(test_resource)
    assert len(ann_list) == 1
    assert ann_list[0]['id'] == annotation['id']

    # Extrai como Fragmento oficial
    fragment_data = service.extract_as_fragment(annotation['id'], fragment_type='quote')
    assert fragment_data['fragment_id'] is not None
    assert fragment_data['location_type'] == 'Página'
    assert fragment_data['location_value'] == '1'
    assert fragment_data['excerpt'] == 'Omnissiah guia os espíritos das máquinas.'

    # Deleta anotação
    deleted = service.delete_annotation(annotation['id'])
    assert deleted is True
    assert len(service.list_annotations(test_resource)) == 0


def test_pdf_reader_view_initialization_and_fit(
    tmp_path: Path, dummy_pdf: Path, test_resource: int
):
    import flet as ft
    from src.configs.settings import (
        COLORS_LIGHT,
        CORE_MENUS,
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
    from src.views.pdf_reader import PdfReaderView

    config = ViewConfig(
        colors=COLORS_LIGHT,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        font_weights=FONT_WEIGHTS,
        icon_sizes=ICON_SIZES,
        main_view_cards=MAIN_VIEW_CARDS,
        page_fonts=PAGE_FONTS,
        texts=TEXTS,
        ui=UI,
        core_menus=CORE_MENUS,
    )

    service = PdfService(storage_dir=tmp_path / 'storage')
    service.attach_pdf(test_resource, dummy_pdf)

    with SessionLocal() as session:
        resource = session.get(BibliographicResource, test_resource)
        view = PdfReaderView(
            config=config,
            resource=resource,
            on_back=lambda: None,
            on_new_fragment=lambda *a: None,
            pdf_service=service,
        )

    assert view.page_image.fit == ft.BoxFit.CONTAIN
    assert view.page_image.src.startswith('data:image/png;base64,')
    assert view.page_image.height == 680
    assert view.loading_ring is not None
    assert view.loading_ring.visible is False
    assert view.total_pages == 2

    # Validação do zoom opcional e redução da página
    assert view.zoom_level == 1.0
    view._zoom_in()
    assert view.zoom_level == 1.25
    assert view.page_image.height == 850
    view._zoom_reset()
    assert view.zoom_level == 1.0
    assert view.page_image.height == 680

    # Validação da camada de texto selecionável (SelectionArea com caracteres)
    assert isinstance(view.selection_area, ft.SelectionArea)
    assert view.selection_area.content is view.text_layer_stack
    assert len(view.text_layer_stack.controls) >= 1
    assert view.text_layer_stack.controls[0].content.selectable is True

    # Validação dos modos de visualização (Página, Lado a Lado, Texto)
    view._on_view_mode_change('split')
    assert view.view_mode == 'split'
    assert view.text_reading_card.visible is True
    view._on_view_mode_change('page')
    assert view.view_mode == 'page'
    assert view.text_reading_card.visible is False

    # 1. Navegação pelas setas do teclado (Arrow Left / Arrow Right)
    assert view.handle_key("Arrow Left") is False
    assert view.current_page == 1

    assert view.handle_key("Arrow Right") is True
    assert view.current_page == 2

    assert view.handle_key("Arrow Right") is False
    assert view.current_page == 2

    assert view.handle_key("Arrow Left") is True
    assert view.current_page == 1

    assert view.handle_key("PageDown") is True
    assert view.current_page == 2

    assert view.handle_key("PageUp") is True
    assert view.current_page == 1

    # 2. Navegação lateral por clique
    assert view.left_nav_zone.on_click == view._prev_page
    assert view.right_nav_zone.on_click == view._next_page
    assert view.left_page_margin_click.on_click == view._prev_page
    assert view.right_page_margin_click.on_click == view._next_page

    view._next_page()
    assert view.current_page == 2
    view._prev_page()
    assert view.current_page == 1

    # 3. Criação de fragmento dentro do PDF sem sair da tela
    dialogs = []

    class MockPage:
        def show_dialog(self, dlg):
            dialogs.append(dlg)

        def update(self):
            pass

    mock_page = MockPage()
    view.page = mock_page
    view.page_text_field.value = "Texto vetorial de teste para fragmento"

    view._handle_new_fragment_click()
    assert len(dialogs) == 1
    modal_dialog = dialogs[0]
    assert modal_dialog is view.fragment_modal.modal
    assert view.fragment_modal.form_title.value == "Novo fragmento"
    assert view.fragment_modal.excerpt.value == "Texto vetorial de teste para fragmento"
    assert view.fragment_modal.location_value.value == "1"

    # Simula salvamento via botão Salvar padronizado
    view.fragment_modal._save(None)

    # Verifica se o fragmento foi persistido no banco e listado na barra lateral
    with SessionLocal() as session:
        from src.domains.core_domain import Fragment
        frags = session.query(Fragment).filter_by(bib_res_id=test_resource).all()
        assert len(frags) >= 1
        assert any("Texto vetorial de teste" in f.excerpt for f in frags)

    assert len(view.fragments_column.controls) >= 1


def test_open_pdf_standalone_window_launches_subprocess(monkeypatch):
    from unittest.mock import MagicMock
    from src.views.pdf_reader.standalone import open_pdf_standalone_window
    from src.utils.types import ViewConfig
    from src.configs.settings import (
        COLORS_LIGHT,
        CORE_MENUS,
        FONT_FAMILIES,
        FONT_SIZES,
        FONT_WEIGHTS,
        ICON_SIZES,
        MAIN_VIEW_CARDS,
        PAGE_FONTS,
        TEXTS,
        UI,
    )

    mock_popen = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)

    mock_page = MagicMock()
    config = ViewConfig(
        colors=COLORS_LIGHT,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        font_weights=FONT_WEIGHTS,
        icon_sizes=ICON_SIZES,
        main_view_cards=MAIN_VIEW_CARDS,
        page_fonts=PAGE_FONTS,
        texts=TEXTS,
        ui=UI,
        core_menus=CORE_MENUS,
    )

    result = open_pdf_standalone_window(
        resource_id=42,
        page=mock_page,
        config=config,
        work_title="Metafísica dos Costumes",
    )

    assert result is True
    assert mock_popen.called
    cmd_args = mock_popen.call_args[0][0]
    assert cmd_args[1:] == ["-m", "src.views.pdf_reader.standalone", "42"]
    assert "start_new_session" in mock_popen.call_args[1]
    assert mock_popen.call_args[1]["start_new_session"] is True
