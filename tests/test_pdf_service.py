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
    assert view.text_layer_stack.controls[0].content.selectable is False

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
    view.close()


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


def test_pdf_reader_page_offset_and_synchronization(tmp_path: Path, test_resource: int):
    """Valida a funcionalidade sagrada de sincronização de offset de páginas (Problema 3):
    1. Ausência do botão de abrir no navegador e presença do controle de offset na toolbar.
    2. Persistência do offset no banco de dados através do BibliographicResource e PdfService.
    3. Exibição harmoniosa do offset e reflexo imediato nos rótulos de página (ex: 'p. 1 (PDF 2/6)').
    4. Comportamento dos botões de incremento (+), decremento (-) e sincronia rápida ('bullseye').
    5. Localização inicial de novos fragmentos utilizando a numeração sincronizada da obra física.
    6. Navegação via fragmentos mapeando a página da obra de volta à página física do PDF.
    7. Extração de anotação como fragmento aplicando o offset da obra.
    """
    import flet as ft
    import pymupdf
    from src.configs.settings import (
        COLORS_LIGHT,
        FONT_FAMILIES,
        FONT_SIZES,
        FONT_WEIGHTS,
        ICON_SIZES,
        PAGE_FONTS,
        TEXTS,
        UI,
    )
    from src.db.db import SessionLocal
    from src.domains import BibliographicResource
    from src.services.pdf_service import PdfService
    from src.utils.types import ViewConfig
    from src.views.pdf_reader import PdfReaderView

    # Cria documento de 6 páginas
    pdf_path = tmp_path / 'offset_doc.pdf'
    doc = pymupdf.open()
    for i in range(1, 7):
        p = doc.new_page(width=200, height=300)
        p.insert_text((20, 50), f"Página de teste {i}")
    doc.save(str(pdf_path))
    doc.close()

    config = ViewConfig(
        colors=COLORS_LIGHT,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        font_weights=FONT_WEIGHTS,
        icon_sizes=ICON_SIZES,
        page_fonts=PAGE_FONTS,
        texts=TEXTS,
        ui=UI,
        core_menus={},
        main_view_cards={},
    )

    service = PdfService(storage_dir=tmp_path / 'storage')
    service.attach_pdf(test_resource, pdf_path)

    # 1. Verifica estado inicial no banco e serviço
    info = service.get_pdf_info(test_resource)
    assert info is not None
    assert info['pdf_page_offset'] == 0

    with SessionLocal() as session:
        resource = session.get(BibliographicResource, test_resource)
        view = PdfReaderView(
            config=config,
            resource=resource,
            on_back=lambda: None,
            pdf_service=service,
        )

    # 2. Valida ausência do botão browser_btn / _handle_open_browser_viewer
    assert not hasattr(view, 'browser_btn')
    assert not hasattr(view, '_handle_open_browser_viewer')

    # 3. Valida presença e estado inicial do controle de offset
    assert hasattr(view, 'page_offset')
    assert view.page_offset == 0
    assert isinstance(view.offset_field, ft.TextField)
    assert view.offset_field.value == '0'
    assert view.page_number_label.value == '1'
    assert view.page_count_label.value == ' de 6'
    assert view.get_work_page(1) == 1

    # 4. Ajuste manual de offset via set_page_offset
    # Exemplo: obra impressa começa na página 1 no PDF página 3 (offset = -2)
    view.set_page_offset(-2)
    assert view.page_offset == -2
    assert view.offset_field.value == '-2'
    assert view.get_work_page(1) == -1
    assert view.get_work_page(3) == 1

    # Rótulo na página 1 do PDF reflete obra página -1
    assert view.page_number_label.value == 'p. -1'
    assert view.page_count_label.value == ' (PDF 1/6)'

    # Avança para a página 3 do PDF -> obra página 1
    view.current_page = 3
    view._load_current_page()
    assert view.page_number_label.value == 'p. 1'
    assert view.page_count_label.value == ' (PDF 3/6)'

    # 5. Persistência no banco de dados
    with SessionLocal() as session:
        db_res = session.get(BibliographicResource, test_resource)
        assert db_res.pdf_page_offset == -2

    # 6. Incremento (+) e Decremento (-)
    view._handle_offset_increment()
    assert view.page_offset == -1
    assert view.offset_field.value == '-1'

    view._handle_offset_decrement()
    assert view.page_offset == -2
    assert view.offset_field.value == '-2'

    # 7. Sincronia rápida: fixar página atual (PDF 3) como Página 1 da obra
    view.current_page = 4
    view._handle_sync_current_as_page_one()
    # Para PDF 4 ser página 1 da obra: offset = 1 - 4 = -3
    assert view.page_offset == -3
    assert view.offset_field.value == '-3'
    assert view.get_work_page(4) == 1
    assert view.page_number_label.value == 'p. 1'
    assert view.page_count_label.value == ' (PDF 4/6)'

    # 8. Entrada direta no TextField de offset
    view.offset_field.value = '-5'
    view._handle_offset_submit()
    assert view.page_offset == -5
    assert view.get_work_page(6) == 1

    # Entrada inválida deve preservar o valor atual
    view.offset_field.value = 'invalid'
    view._handle_offset_submit()
    assert view.page_offset == -5

    # 9. Criação de fragmento com numeração sincronizada
    dialogs = []

    class MockPage:
        def show_dialog(self, dlg):
            dialogs.append(dlg)

        def update(self):
            pass

    mock_page = MockPage()
    view.page = mock_page
    view.current_page = 6  # PDF 6 com offset -5 é página 1 da obra
    view.selected_text = "Trecho extraído com offset sincronizado"
    view.selected_page = 6

    view._handle_new_fragment_click()
    assert len(dialogs) >= 1
    assert view.fragment_modal.excerpt.value == "Trecho extraído com offset sincronizado"
    assert view.fragment_modal.location_value.value == "1"  # obra página 1, não PDF 6!

    # 10. Salto a partir de fragmento da obra
    # Fragmento registrado na página '1' da obra deve pular para o PDF 6 (1 - (-5) = 6)
    view.current_page = 1
    view._load_current_page()
    assert view.current_page == 1

    view._jump_to_fragment_page("1")
    assert view.current_page == 6

    # 11. Extração de anotação do PdfService com offset
    ann = service.save_annotation(
        bib_res_id=test_resource,
        page_number=6,
        selected_text="Grifo sagrado do Omnissiah",
    )
    extracted = service.extract_as_fragment(ann['id'])
    assert extracted['location_value'] == "1"

    # 12. Restauração ao reabrir a view
    view.close()

    with SessionLocal() as session:
        reloaded_res = session.get(BibliographicResource, test_resource)
        view2 = PdfReaderView(
            config=config,
            resource=reloaded_res,
            on_back=lambda: None,
            pdf_service=service,
        )
        assert view2.page_offset == -5
        assert view2.offset_field.value == '-5'
        view2.close()


def test_pdf_reader_hold_and_drag_gesture_pan(
    tmp_path: Path, dummy_pdf: Path, test_resource: int
):
    """Testa a arquitetura de hold-and-drag: bounding box do texto, ferramentas e pan irrestrito."""
    import flet as ft
    from types import SimpleNamespace
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
            pdf_service=service,
        )

    try:
        # 1. Validação da contenção por Bounding Box Real
        assert hasattr(view, 'selection_container')
        assert isinstance(view.selection_container, ft.Container)
        assert view.selection_container.content is view.selection_area
        assert view.selection_container.visible is True
        assert view.selection_container.left >= 0
        assert view.selection_container.top >= 0
        assert view.selection_container.width > 0
        assert view.selection_container.height > 0

        # Margens livres: bounding box do texto não ocupa toda a largura da página
        assert view.selection_container.width <= view.page_image.width

        # 2. Arrastar sobre o texto em modo de seleção -> NÃO ativa pan (permite selecionar)
        assert view.active_tool == 'select'
        assert len(view._left_text_boxes) >= 1
        first_box = view._left_text_boxes[0]
        on_text_x = first_box[0] + first_box[2] / 2
        on_text_y = first_box[1] + first_box[3] / 2

        start_on_text = SimpleNamespace(local_position=SimpleNamespace(x=on_text_x, y=on_text_y))
        view._on_left_card_pan_start(start_on_text)
        assert view._is_panning is False

        # 3. Arrastar fora do texto (nas margens do PDF: x=2, y=2) -> ATIVA pan imediatamente
        start_outside_text = SimpleNamespace(local_position=SimpleNamespace(x=2.0, y=2.0))
        view._on_left_card_pan_start(start_outside_text)
        assert view._is_panning is True

        pan_event = SimpleNamespace(local_delta=SimpleNamespace(x=10.0, y=-20.0))
        view._on_pan_update(pan_event)
        assert view._pan_dx_acc == 10.0
        assert view._pan_dy_acc == -20.0

        view._on_pan_end(None)
        assert view._is_panning is False

        # 4. Alternância de ferramenta para modo Mão / Pan ('pan')
        view._on_tool_mode_change('pan')
        assert view.active_tool == 'pan'
        # SelectionArea é desativada/ocultada para liberar 100% da página para o gesto
        assert view.selection_container.visible is False
        assert view.left_page_gesture.mouse_cursor == ft.MouseCursor.GRAB

        # No modo Pan, tocar SOBRE o texto também ativa o pan imediatamente
        view._on_left_card_pan_start(start_on_text)
        assert view._is_panning is True
        view._on_pan_end(None)

        # 5. Alternância de volta para modo Seleção ('select')
        view._on_tool_mode_change('select')
        assert view.active_tool == 'select'
        assert view.selection_container.visible is True
        assert view.left_page_gesture.mouse_cursor == ft.MouseCursor.BASIC

        # 6. Arrasto com Botão Secundário (Direito) -> Sempre ativa pan mesmo sobre o texto
        view._on_card_right_pan_start(start_on_text)
        assert view._is_panning is True
        view._on_pan_end(None)

        # 7. Arrasto na área externa do leitor (gesture_container / fundo cinza)
        view._on_outer_pan_start(SimpleNamespace())
        assert view._is_panning is True
        view._on_pan_end(None)

        # 8. Atalhos de teclado 'H' e 'V' para alternância rápida de ferramenta
        assert view.handle_key('h') is True
        assert view.active_tool == 'pan'

        assert view.handle_key('v') is True
        assert view.active_tool == 'select'

    finally:
        view.close()


def test_pdf_reader_page_input_and_jump(tmp_path: Path, test_resource: int):
    """Valida o indicador de página interativo e editável (Problema 2):
    1. Transição de label para TextField compacto ao clicar no container indicador.
    2. Navegação para página alvo via Enter (on_submit) e ao desfocar (on_blur).
    3. Restauração sem erros em caso de cancelamento (Escape) ou valor inválido.
    4. Compatibilidade completa com modo Lado a Lado (duas páginas: '1 - 2', '5 - 6').
    5. Proteção contra avanço acidental de páginas por setas do teclado durante edição.
    """
    import flet as ft
    import pymupdf
    from types import SimpleNamespace
    from src.configs.settings import (
        COLORS_LIGHT,
        FONT_FAMILIES,
        FONT_SIZES,
        FONT_WEIGHTS,
        ICON_SIZES,
        PAGE_FONTS,
        TEXTS,
        UI,
    )
    from src.db.db import SessionLocal
    from src.domains import BibliographicResource
    from src.services.pdf_service import PdfService
    from src.utils.types import ViewConfig
    from src.views.pdf_reader import PdfReaderView

    # Cria documento de 6 páginas para validar saltos e modo split
    multi_pdf_path = tmp_path / 'multi_page_doc.pdf'
    doc = pymupdf.open()
    for i in range(1, 7):
        p = doc.new_page(width=200, height=300)
        p.insert_text((20, 50), f"Página {i} de dados sagrados do Mechanicus")
    doc.save(str(multi_pdf_path))
    doc.close()

    config = ViewConfig(
        colors=COLORS_LIGHT,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        font_weights=FONT_WEIGHTS,
        icon_sizes=ICON_SIZES,
        page_fonts=PAGE_FONTS,
        texts=TEXTS,
        ui=UI,
        core_menus={},
        main_view_cards={},
    )

    service = PdfService(storage_dir=tmp_path / 'storage')
    service.attach_pdf(test_resource, multi_pdf_path)

    with SessionLocal() as session:
        resource = session.get(BibliographicResource, test_resource)
        view = PdfReaderView(
            config=config,
            resource=resource,
            on_back=lambda: None,
            pdf_service=service,
        )

    # 1. Estrutura do controle indicador
    assert isinstance(view.page_number_display, ft.Container)
    assert view.page_number_container is view.page_number_display
    assert isinstance(view.page_number_input, ft.TextField)
    assert view.page_number_display.content is view.page_number_label
    assert view.page_number_display.visible is True
    assert view.page_number_input.visible is False
    assert view._is_editing_page is False
    assert view.page_number_label.value == '1'
    assert view.total_pages == 6

    # 2. Transição ao clicar no container indicador
    view._start_page_edit()
    assert view._is_editing_page is True
    assert view.page_number_display.visible is False
    assert view.page_number_input.visible is True
    assert view.page_number_input.value == '1'
    assert view.page_number_input.selection.base_offset == 0
    assert view.page_number_input.selection.extent_offset == 1

    # 3. Teclas de navegação do leitor devem ser ignoradas enquanto editando
    assert view.handle_key("Arrow Right") is False
    assert view.current_page == 1

    # 4. Cancelamento via tecla Escape (restaura estado original)
    view.page_number_input.value = '4'
    handled_esc = view.handle_key("Escape")
    assert handled_esc is True
    assert view._is_editing_page is False
    assert view.current_page == 1
    assert view.page_number_display.visible is True
    assert view.page_number_input.visible is False
    assert view.page_number_label.value == '1'

    # Cancelamento via alias Esc
    view._start_page_edit()
    view.page_number_input.value = '5'
    assert view.handle_key("Esc") is True
    assert view.current_page == 1
    assert view._is_editing_page is False

    # 5. Salto de página via Enter (on_submit)
    view._start_page_edit()
    view.page_number_input.value = '4'
    view._on_page_input_submit(None)
    assert view._is_editing_page is False
    assert view.current_page == 4
    assert view.page_number_display.visible is True
    assert view.page_number_input.visible is False
    assert view.page_number_label.value == '4'

    # 6. Salto de página via perda de foco (on_blur)
    view._start_page_edit()
    view.page_number_input.value = '2'
    view._on_page_input_blur(None)
    assert view._is_editing_page is False
    assert view.current_page == 2
    assert view.page_number_display.visible is True
    assert view.page_number_input.visible is False
    assert view.page_number_label.value == '2'

    # 7. Salto via handle_key("Enter")
    view._start_page_edit()
    view.page_number_input.value = '3'
    assert view.handle_key("Enter") is True
    assert view._is_editing_page is False
    assert view.current_page == 3
    assert view.page_number_label.value == '3'

    # 8. Valores inválidos (fora de limites, negativos, não numéricos, vazios)
    # 8.1. Página acima do total (999)
    view._start_page_edit()
    view.page_number_input.value = '999'
    view._submit_page_input()
    assert view._is_editing_page is False
    assert view.current_page == 3
    assert view.page_number_label.value == '3'

    # 8.2. Página zero (0)
    view._start_page_edit()
    view.page_number_input.value = '0'
    view._submit_page_input()
    assert view.current_page == 3
    assert view.page_number_label.value == '3'

    # 8.3. Texto não numérico ("abc")
    view._start_page_edit()
    view.page_number_input.value = 'abc'
    view._submit_page_input()
    assert view.current_page == 3
    assert view.page_number_label.value == '3'

    # 8.4. Entrada vazia ("   ")
    view._start_page_edit()
    view.page_number_input.value = '   '
    view._submit_page_input()
    assert view.current_page == 3
    assert view.page_number_label.value == '3'

    # 9. Compatibilidade com modo Lado a Lado (Duas Páginas / 'split')
    view._on_view_mode_change('split')
    assert view.view_mode == 'split'
    assert view.page_number_label.value == '3 - 4'

    # Salto para página 5 no modo split -> deve exibir '5 - 6'
    view._start_page_edit()
    assert view.page_number_input.value == '3'
    view.page_number_input.value = '5'
    view._submit_page_input()
    assert view.current_page == 5
    assert view.page_number_label.value == '5 - 6'

    # Entrada inválida no modo split -> deve restaurar '5 - 6'
    view._start_page_edit()
    view.page_number_input.value = '88'
    view._submit_page_input()
    assert view.current_page == 5
    assert view.page_number_label.value == '5 - 6'

    # Salto para última página individual (6) no modo split -> página 6 sozinha
    view._start_page_edit()
    view.page_number_input.value = '6'
    view._submit_page_input()
    assert view.current_page == 6
    assert view.page_number_label.value == '6'

    # Salto de volta para página 1 via blur no modo split -> exibe '1 - 2'
    view._start_page_edit()
    view.page_number_input.value = '1'
    view._on_page_input_blur(None)
    assert view.current_page == 1
    assert view.page_number_label.value == '1 - 2'

    # 10. Interações de hover no container indicador
    hover_event_enter = SimpleNamespace(data=True)
    view.page_number_display.on_hover(hover_event_enter)
    assert view.page_number_display.bgcolor == config.colors['card_hover']

    hover_event_leave = SimpleNamespace(data=False)
    view.page_number_display.on_hover(hover_event_leave)
    assert view.page_number_display.bgcolor is None

    view.close()


def test_pdf_reader_toolbar_layout_and_stacked_controls(tmp_path: Path, dummy_pdf: Path, test_resource: int):
    """Valida a arquitetura sagrada da Toolbar do leitor de PDF (Pontos 2 e 3):
    1. Altura ampliada da barra superior (s(66)) para conforto vertical.
    2. Estruturação em três zonas equilibradas com o Paginador como elemento CENTRAL.
    3. Empilhamento vertical com colunas (ft.Column) e legendas técnicas discretas.
    4. Preservação de todos os controles interativos operacionais.
    """
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
    from src.db.db import SessionLocal
    from src.domains import BibliographicResource
    from src.services.pdf_service import PdfService
    from src.utils.types import ViewConfig
    from src.views import ui_kit as ui
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
            pdf_service=service,
            show_back_button=True,
        )

    # 1. Validação da altura ampliada da barra superior
    top_bar = view.content.controls[0]
    assert isinstance(top_bar, ft.Container)
    assert top_bar.height == ui.s(66)

    # 2. Validação da estruturação em três zonas com Paginador no centro
    top_row = top_bar.content
    assert isinstance(top_row, ft.Row)
    assert len(top_row.controls) == 3

    left_zone, center_zone, right_zone = top_row.controls
    assert isinstance(left_zone, ft.Row)
    assert left_zone.expand is True
    assert isinstance(center_zone, ft.Container)
    assert center_zone.alignment == ft.Alignment.CENTER
    assert isinstance(right_zone, ft.Row)
    assert right_zone.expand is True

    # 3. Validação do Paginador na Zona Central
    pager_col = center_zone.content
    assert isinstance(pager_col, ft.Column)
    assert pager_col.tight is True
    assert pager_col.controls[0].value == 'Páginas'
    pager_controls_row = pager_col.controls[1]
    assert isinstance(pager_controls_row, ft.Row)
    assert view.page_number_display in pager_controls_row.controls
    assert view.page_number_input in pager_controls_row.controls
    assert view.page_count_label in pager_controls_row.controls

    # 4. Validação dos controles empilhados na Zona Esquerda
    # Controles esperados: [back_group, title_drag, div, zoom_group, div, tool_mode_host]
    assert len(left_zone.controls) == 6
    # Verifica grupo Zoom
    zoom_group = None
    for ctrl in left_zone.controls:
        if isinstance(ctrl, ft.Column) and hasattr(ctrl, 'controls') and len(ctrl.controls) >= 2:
            row0 = ctrl.controls[0]
            if isinstance(row0, ft.Row) and any(getattr(c, 'value', None) == 'Zoom' for c in row0.controls):
                zoom_group = ctrl
                break
    assert zoom_group is not None, "Grupo Zoom empilhado deve estar presente na Zona Esquerda"

    # Verifica grupo Ferramenta (tool_mode_host)
    assert view.tool_mode_host in left_zone.controls
    assert isinstance(view.tool_mode_host.content, ft.Column)
    assert view.tool_mode_host.content.controls[0].value == 'Ferramenta'

    # Alterna ferramenta para verificar reatividade do empilhamento
    view._on_tool_mode_change('pan')
    assert view.active_tool == 'pan'
    assert isinstance(view.tool_mode_host.content, ft.Column)
    assert view.tool_mode_host.content.controls[0].value == 'Ferramenta'

    # 5. Validação dos controles empilhados na Zona Direita
    # Controles esperados: [view_mode_host, div, offset_group, div, text_actions_group, div, sidebar_group]
    assert view.view_mode_host in right_zone.controls
    assert isinstance(view.view_mode_host.content, ft.Column)
    assert view.view_mode_host.content.controls[0].value == 'Exibição'

    # Alterna modo de visualização para verificar reatividade do empilhamento
    view._on_view_mode_change('split')
    assert view.view_mode == 'split'
    assert isinstance(view.view_mode_host.content, ft.Column)
    assert view.view_mode_host.content.controls[0].value == 'Exibição'

    # Verifica grupo Offset empilhado
    offset_group = None
    for ctrl in right_zone.controls:
        if isinstance(ctrl, ft.Column) and hasattr(ctrl, 'controls') and len(ctrl.controls) >= 2:
            if getattr(ctrl.controls[0], 'value', None) == 'Offset':
                offset_group = ctrl
                break
    assert offset_group is not None, "Grupo Offset empilhado deve estar presente na Zona Direita"
    assert view.offset_field in offset_group.controls[1].controls

    # Verifica grupo de Ações de Texto empilhado
    text_group = None
    for ctrl in right_zone.controls:
        if isinstance(ctrl, ft.Column) and hasattr(ctrl, 'controls') and len(ctrl.controls) >= 2:
            if getattr(ctrl.controls[0], 'value', None) == 'Texto':
                text_group = ctrl
                break
    assert text_group is not None, "Grupo Ações de Texto empilhado deve estar presente na Zona Direita"

    # Verifica grupo Painel Lateral empilhado
    sidebar_group = None
    for ctrl in right_zone.controls:
        if isinstance(ctrl, ft.Column) and hasattr(ctrl, 'controls') and len(ctrl.controls) >= 2:
            if getattr(ctrl.controls[0], 'value', None) == 'Painel':
                sidebar_group = ctrl
                break
    assert sidebar_group is not None, "Grupo Painel Lateral empilhado deve estar presente na Zona Direita"

    # 6. Validação do Modo Compacto (Menu '...' vertical para janela não-maximizada)
    view.set_compact_mode(True)
    assert view._is_compact is True
    assert view.more_menu_group in right_zone.controls
    assert view.view_mode_host not in right_zone.controls
    assert view.text_actions_group not in right_zone.controls
    assert view.offset_group in right_zone.controls
    assert view.sidebar_group in right_zone.controls

    # Verifica os itens do menu suspenso ('...')
    assert hasattr(view, 'more_popup_btn')
    assert len(view.more_popup_btn.items) >= 4
    # Alternância de modo via menu
    view._set_view_mode('split')
    assert view.view_mode == 'split'

    # 7. Validação do retorno ao Modo Desempacotado (Janela maximizada)
    view.set_compact_mode(False)
    assert view._is_compact is False
    assert view.view_mode_host in right_zone.controls
    assert view.text_actions_group in right_zone.controls
    assert view.more_menu_group not in right_zone.controls

    # 8. Validação de seleção de texto multilinhas (Issue 2)
    # Garante que controles de texto na camada não possuem selectable isolado (selectable=False)
    assert len(view.text_layer_stack.controls) > 0
    for container in view.text_layer_stack.controls:
        text_ctrl = container.content
        assert isinstance(text_ctrl, ft.Text)
        assert text_ctrl.selectable is False

    # Valida que selection_container é irmão superior da imagem na Stack do card (não envolvido pelo GestureDetector)
    page_stack = view.page_card.content
    assert isinstance(page_stack, ft.Stack)
    assert view.left_page_gesture in page_stack.controls
    assert view.selection_container in page_stack.controls
    # selection_container deve estar após left_page_gesture para receber cliques primeiro
    gesture_idx = page_stack.controls.index(view.left_page_gesture)
    selection_idx = page_stack.controls.index(view.selection_container)
    assert selection_idx > gesture_idx

    view.close()


def test_pdf_reader_sidebar_fragment_edit_and_modal_focus_isolation(
    tmp_path: Path, dummy_pdf: Path, test_resource: int
):
    """Valida:
    1. Clicar em um fragmento na barra lateral abre o modal padrão de edição (FragmentModal.open_edit).
    2. Navega para a página correspondente do fragmento.
    3. Foco total no modal: atalhos de teclado e gestos de mouse são completamente ignorados pelo leitor abaixo
       enquanto o modal estiver aberto (is_modal_open == True).
    4. Persistência de edição e restauração de interação após o fechamento do modal.
    """
    import flet as ft
    import pymupdf
    from types import SimpleNamespace
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
    from src.db.db import SessionLocal
    from src.domains import BibliographicResource, Fragment
    from src.services.pdf_service import PdfService
    from src.utils.types import ViewConfig
    from src.views.pdf_reader import PdfReaderView

    # Cria documento de 5 páginas
    multi_pdf = tmp_path / "multi_page_doc.pdf"
    doc = pymupdf.open()
    for i in range(1, 6):
        p = doc.new_page(width=200, height=300)
        p.insert_text((20, 50), f"Página sagrada {i}")
    doc.save(str(multi_pdf))
    doc.close()

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

    service = PdfService(storage_dir=tmp_path / "storage")
    service.attach_pdf(test_resource, multi_pdf)

    # Insere fragmento prévio na página 3
    with SessionLocal() as session:
        frag = Fragment(
            bib_res_id=test_resource,
            fragment_type="quote",
            excerpt="Citação sagrada de teste da mecânica lógica",
            location_type="Página",
            location_value="3",
        )
        session.add(frag)
        session.commit()
        frag_id = frag.id

    class MockPage:
        def __init__(self):
            self.overlay = []
            self.dialog = None

        def show_dialog(self, dlg):
            self.dialog = dlg
            dlg.open = True
            if dlg not in self.overlay:
                self.overlay.append(dlg)

        def update(self):
            pass

        def run_task(self, task):
            pass

    mock_page = MockPage()

    with SessionLocal() as session:
        resource = session.get(BibliographicResource, test_resource)
        view = PdfReaderView(
            config=config,
            resource=resource,
            on_back=lambda: None,
            pdf_service=service,
            page=mock_page,
        )

    try:
        # 1. Verifica presença do fragmento na barra lateral
        assert len(view.fragments_column.controls) == 1
        card = view.fragments_column.controls[0]
        assert isinstance(card, ft.Container)
        assert card.tooltip == "Clique para editar este fragmento"

        # 2. Clicar no fragmento deve navegar para a página 3 e abrir o modal de edição
        assert view.current_page == 1
        card.on_click(None)

        assert view.current_page == 3
        assert view.is_modal_open is True
        assert view.fragment_modal.modal.open is True
        assert view.fragment_modal.editing_id == frag_id
        assert view.fragment_modal.form_title.value == "Editar fragmento"
        assert view.fragment_modal.excerpt.value == "Citação sagrada de teste da mecânica lógica"
        assert view.fragment_modal.location_value.value == "3"

        # 3. Foco total no modal: todos os atalhos de teclado devem ser rejeitados pelo leitor abaixo
        assert view.handle_key("Arrow Right") is False
        assert view.current_page == 3  # Não mudou de página

        assert view.handle_key("Arrow Left") is False
        assert view.current_page == 3  # Não mudou de página

        assert view.handle_key("PageDown") is False
        assert view.handle_key("PageUp") is False
        assert view.handle_key("v") is False
        assert view.handle_key("h") is False
        assert view.handle_key("+", mod=True) is False
        assert view.zoom_level == 1.0  # Não aplicou zoom
        assert view.handle_key("-", mod=True) is False
        assert view.handle_key("a", mod=True) is False

        # 4. Foco total no modal: interações de mouse wheel e arrasto devem ser bloqueadas
        scroll_event = SimpleNamespace(scroll_delta=SimpleNamespace(y=100.0))
        view._on_mouse_scroll(scroll_event)
        assert view.current_page == 3

        pan_event = SimpleNamespace(local_position=SimpleNamespace(x=10.0, y=10.0))
        view._on_left_card_pan_start(pan_event)
        assert view._is_panning is False

        view._prev_page()
        assert view.current_page == 3

        view._next_page()
        assert view.current_page == 3

        view._zoom_in()
        assert view.zoom_level == 1.0

        view._start_page_edit()
        assert view._is_editing_page is False

        # 5. Edita o fragmento no modal e salva
        view.fragment_modal.excerpt.value = "Citação sagrada editada com sucesso pelo Omnissiah"
        view.fragment_modal._save()

        # O modal foi fechado
        assert view.fragment_modal.modal.open is False
        assert view.is_modal_open is False

        # Verifica persistência no banco de dados
        with SessionLocal() as session:
            updated_frag = session.get(Fragment, frag_id)
            assert updated_frag.excerpt == "Citação sagrada editada com sucesso pelo Omnissiah"

        # Verifica que o card na sidebar foi atualizado
        assert len(view.fragments_column.controls) == 1
        updated_card = view.fragments_column.controls[0]
        assert "Citação sagrada editada com sucesso pelo Omnissiah" in str(
            updated_card.content.controls[1].value
        )

        # 6. Com o modal fechado, o controle de teclado do leitor volta a operar normalmente
        assert view.handle_key("Arrow Right") is True
        assert view.current_page == 4

        assert view.handle_key("Arrow Left") is True
        assert view.current_page == 3

    finally:
        view.close()


def test_pdf_orphan_cleanup_on_work_delete_and_detach(
    tmp_path: Path, dummy_pdf: Path, test_resource: int
):
    """Valida:
    1. Exclusão de obra apaga PDF físico órfão do disco (Ponto 1).
    2. Obras compartilhando o mesmo PDF preservam o arquivo até o último ser excluído.
    3. cleanup_orphan_files varre o diretório e remove PDFs órfãos.
    4. Remoção imediata do badge 'PDF' da linha do Acervo quando a obra não tem mais PDF (Ponto 2).
    5. Opção 'Desanexar PDF / excluir arquivo' no menu expansível '...' do inspector (Ponto 3).
    """
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
    from src.db.db import SessionLocal
    from src.domains import BibliographicResource, EditorialMonograph
    from src.repositories.work_repository import WorkRepository
    from src.services.pdf_service import PdfService
    from src.utils.types import ViewConfig
    from src.views.works import WorksComposer

    storage_dir = tmp_path / "pdf_storage"
    service = PdfService(storage_dir=storage_dir)

    # 1. Anexa PDF e valida criação física
    info = service.attach_pdf(test_resource, dummy_pdf)
    physical_path = Path(info["pdf_absolute_path"])
    assert physical_path.exists() is True

    # 2. Exclusão da obra apaga o arquivo físico órfão
    with SessionLocal() as session:
        repo = WorkRepository(session)
        res = session.get(BibliographicResource, test_resource)
        assert res is not None
        repo.remove_work(res)

    assert physical_path.exists() is False

    # 3. Teste com 2 obras compartilhando o mesmo PDF
    with SessionLocal() as session:
        res1 = BibliographicResource()
        res1.editorial_monograph = EditorialMonograph(title="Obra Alfa", publication_place="Roma")
        res2 = BibliographicResource()
        res2.editorial_monograph = EditorialMonograph(title="Obra Beta", publication_place="Atenas")
        session.add_all([res1, res2])
        session.commit()
        id1, id2 = res1.id, res2.id

    info1 = service.attach_pdf(id1, dummy_pdf)
    shared_path = Path(info1["pdf_absolute_path"])
    # Simula compartilhamento do mesmo caminho para res2
    with SessionLocal() as session:
        r2 = session.get(BibliographicResource, id2)
        r2.pdf_path = info1["pdf_path"]
        r2.pdf_filename = info1["pdf_filename"]
        session.commit()

    # Exclui a primeira obra: o arquivo compartilhado NÃO deve ser apagado
    with SessionLocal() as session:
        repo = WorkRepository(session)
        r1 = session.get(BibliographicResource, id1)
        repo.remove_work(r1)

    assert shared_path.exists() is True

    # Exclui a segunda obra: agora é órfão, DEVE ser apagado
    with SessionLocal() as session:
        repo = WorkRepository(session)
        r2 = session.get(BibliographicResource, id2)
        repo.remove_work(r2)

    assert shared_path.exists() is False

    # 4. cleanup_orphan_files detecta e remove arquivos soltos
    storage_dir.mkdir(parents=True, exist_ok=True)
    loose_file = storage_dir / "loose_orphan.pdf"
    loose_file.write_bytes(dummy_pdf.read_bytes())
    assert loose_file.exists() is True

    removed = service.cleanup_orphan_files()
    assert removed == 1
    assert loose_file.exists() is False

    # 5. Validação de UI no WorksComposer (Pontos 2 e 3)
    with SessionLocal() as session:
        res3 = BibliographicResource()
        res3.editorial_monograph = EditorialMonograph(title="Tratado de Física", publication_place="Tebas")
        session.add(res3)
        session.commit()
        id3 = res3.id

    # Anexa PDF à obra 3
    info3 = service.attach_pdf(id3, dummy_pdf)
    res3_file = Path(info3["pdf_absolute_path"])
    assert res3_file.exists() is True

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

    class MockWorksPage:
        def __init__(self):
            self.dialog = None

        def show_dialog(self, dlg):
            self.dialog = dlg
            dlg.open = True

        def pop_dialog(self):
            if self.dialog:
                self.dialog.open = False
                self.dialog = None

        def update(self):
            pass

    mock_page = MockWorksPage()

    with SessionLocal() as session:
        work_res = session.get(BibliographicResource, id3)
        composer = WorksComposer(
            scale=1.0,
            config=config,
            works=[work_res],
            on_navigate=lambda _dst: None,
            on_work_click=lambda _w: None,
            on_edit_work=lambda _w: None,
            format_reference=lambda _w: None,
            on_copy_reference=lambda _r: None,
            on_delete_work=lambda _w: None,
            page=mock_page,
        )

        # 5a. Obra com PDF deve apresentar o badge 'PDF' na linha da listagem
        assert composer._work_has_pdf(work_res) is True
        row = composer._row(work_res, level=0)
        # Procura pelo badge 'PDF' nos controles do título
        title_cell_row = row.content.controls[1].content
        badges = [
            c for c in title_cell_row.controls
            if isinstance(c, ft.Container) and getattr(c.content, 'data', None) == 'badge'
            or (isinstance(c, ft.Container) and getattr(c, 'tooltip', None) == 'Abrir no Leitor de PDF')
        ]
        assert len(badges) >= 1

        # 5b. Inspector deve conter botão 'Ler PDF' e no '...' a opção 'Desanexar PDF / excluir arquivo'
        composer.selected_id = id3
        inspector = composer._compose_inspector()
        assert inspector is not None

        # 5c. Executa _confirm_detach_pdf para desanexar
        composer._confirm_detach_pdf(work_res)
        assert mock_page.dialog is not None
        assert "Desanexar PDF de “Tratado de Física”?" in str(mock_page.dialog.title.value)

        # Clica no botão de confirmar desanexação
        confirm_btn = mock_page.dialog.actions[1]
        confirm_btn.on_click(None)

        # 5d. Verifica que o arquivo físico foi apagado e o recurso atualizado
        assert res3_file.exists() is False
        assert work_res.pdf_path is None
        assert composer._work_has_pdf(work_res) is False

        # 5e. Re-renderiza a linha da listagem: a etiqueta 'PDF' NÃO deve mais existir
        row_after = composer._row(work_res, level=0)
        title_cell_row_after = row_after.content.controls[1].content
        badges_after = [
            c for c in title_cell_row_after.controls
            if isinstance(c, ft.Container) and getattr(c, 'tooltip', None) == 'Abrir no Leitor de PDF'
        ]
        assert len(badges_after) == 0

        # Limpeza
        repo = WorkRepository(session)
        repo.remove_work(work_res)
