from unittest.mock import MagicMock
import flet as ft

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
from src.utils.types import ReferencePart, ViewConfig, ViewReference
from src.views import ui_kit as ui
from src.views.compilation_hub import common
from src.views.compilation_hub.hub_composer import CompilationHubComposer
from src.views.fragment_modal import FragmentModal
from src.views.fragments import FragmentsComposer
from src.views.knowledge.knowledge_panel import KnowledgePanel
from src.views.work_details_popup import WorkDetailsPopup
from src.views.works import WorksComposer


def _view_config() -> ViewConfig:
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


def test_ui_kit_input_field_justification():
    cfg = _view_config()
    # Multiline must be JUSTIFY
    field_ml = ui.input_field(cfg, multiline=True)
    assert field_ml.text_align == ft.TextAlign.JUSTIFY

    # Single-line must be START
    field_single = ui.input_field(cfg, multiline=False)
    assert field_single.text_align == ft.TextAlign.START

    # Explicit override is respected
    field_custom = ui.input_field(cfg, multiline=True, text_align=ft.TextAlign.RIGHT)
    assert field_custom.text_align == ft.TextAlign.RIGHT


def test_compilation_common_text_input_justification():
    cfg = _view_config()
    # Multiline must be JUSTIFY
    inp_ml = common.text_input(cfg, multiline=True)
    assert inp_ml.text_align == ft.TextAlign.JUSTIFY

    # Single-line must be START
    inp_single = common.text_input(cfg, multiline=False)
    assert inp_single.text_align == ft.TextAlign.START


def test_fragment_modal_excerpt_is_justified():
    cfg = _view_config()
    modal = FragmentModal(
        page=MagicMock(),
        config=cfg,
        on_save=lambda _id, _p: True,
        search_works=lambda _q: [],
    )
    assert modal.excerpt.text_align == ft.TextAlign.JUSTIFY


def test_references_are_strictly_not_justified():
    """ABNT mandates formatted references must remain left aligned (not justified)."""
    cfg = _view_config()
    sample_ref = ViewReference(parts=[
        ReferencePart("SOBRENOME, Nome. "),
        ReferencePart("Título da Obra"),
        ReferencePart(". Local: Editora, 2020."),
    ])

    # common.reference_text
    ref_ctrl = common.reference_text(cfg, sample_ref)
    assert ref_ctrl.text_align != ft.TextAlign.JUSTIFY
    assert ref_ctrl.text_align in (None, ft.TextAlign.START, ft.TextAlign.LEFT)

    # works.py _reference_text
    works = WorksComposer(
        scale=1.0,
        config=cfg,
        works=[],
        on_navigate=lambda _d: None,
        on_work_click=lambda _w: None,
        on_edit_work=lambda _w: None,
        format_reference=lambda _w: sample_ref,
        on_copy_reference=lambda _r: None,
        on_delete_work=lambda _w: None,
    )
    mock_resource = MagicMock()
    mock_resource.id = 1
    works.works = [mock_resource]
    ctrl = works._reference_text(mock_resource)
    assert ctrl.text_align != ft.TextAlign.JUSTIFY


def test_fragments_screen_rows_are_justified():
    cfg = _view_config()
    composer = FragmentsComposer(
        page=MagicMock(),
        config=cfg,
        fragments=[],
        search_works=lambda _q: [],
        on_save=lambda _id, _p: True,
        on_delete=lambda _id: None,
        on_copy_reference=lambda _r: None,
    )

    quote_row = composer._compose_fragment_row({
        "id": 1,
        "fragment_type": "quote",
        "excerpt": "Citação longa e justificada.",
        "location_type": "Página",
        "location_value": "42",
        "work_title": "Livro Teste",
        "citation_author": "TESTE, Autor",
        "citation_year": "2024",
        "display_year": "2024",
        "created_at": "2024-01-01",
    })
    col = quote_row.content.controls[1]
    body = col.controls[0]
    assert body.text_align == ft.TextAlign.JUSTIFY

    paraphrase_row = composer._compose_fragment_row({
        "id": 2,
        "fragment_type": "comment",
        "excerpt": "Paráfrase explicativa de um conceito chave.",
        "location_type": "Sem localização",
        "location_value": "",
        "work_title": "Livro Teste",
        "citation_author": "TESTE, Autor",
        "citation_year": "2024",
        "display_year": "2024",
        "created_at": "2024-01-01",
    })
    col_p = paraphrase_row.content.controls[1]
    body_p = col_p.controls[0]
    assert body_p.text_align == ft.TextAlign.JUSTIFY


def test_works_inspector_fragments_and_resumo_are_justified():
    cfg = _view_config()
    composer = WorksComposer(
        scale=1.0,
        config=cfg,
        works=[],
        on_navigate=lambda _d: None,
        on_work_click=lambda _w: None,
        on_edit_work=lambda _w: None,
        format_reference=lambda _w: None,
        on_copy_reference=lambda _r: None,
        on_delete_work=lambda _w: None,
    )

    fragments = [
        {"id": 1, "fragment_type": "quote", "excerpt": "Texto citação", "location_value": "12"},
        {"id": 2, "fragment_type": "comment", "excerpt": "Texto paráfrase", "location_value": ""},
    ]
    controls = composer._inspector_fragments(fragments)
    card1_text = controls[0].content.controls[0].controls[1]
    card2_text = controls[1].content.controls[0].controls[1]
    assert card1_text.text_align == ft.TextAlign.JUSTIFY
    assert card2_text.text_align == ft.TextAlign.JUSTIFY


def test_compilation_hub_caderno_and_notes_are_justified():
    cfg = _view_config()
    hub = CompilationHubComposer(
        page=MagicMock(),
        config=cfg,
        compilation={"id": 1, "name": "Projeto Alpha", "description": "Desc"},
        refresh_compilations=lambda: [],
        search_works=lambda _q: [],
        on_update=lambda _id, _p: True,
        on_add_work=lambda _cid, _wid: True,
        on_remove_work=lambda _cid, _wid: True,
        on_reorder_works=lambda _cid, _wids: True,
        on_fragment_membership=lambda _cid, _fid, _add: True,
        on_fragment_note=lambda _cid, _fid, _n: True,
        on_create_section=lambda _cid, _t, _i: 1,
        on_update_section=lambda _cid, _sid, _t, _i: True,
        on_delete_section=lambda _cid, _sid: True,
        on_reorder_sections=lambda _cid, _sids: True,
        on_assign_fragment_to_section=lambda _cid, _fid, _sid: True,
        on_reorder_section_fragments=lambda _cid, _sid, _fids: True,
        on_copy_caderno=lambda _t: None,
        on_create_work=lambda _cid: None,
        on_edit_work=lambda _cid, _wid: None,
        on_create_fragment=lambda _cid, _wid: None,
        on_edit_fragment=lambda _cid, _f: None,
    )

    frag_quote = {"id": 1, "fragment_type": "quote", "excerpt": "Trecho da citação"}
    body_q = hub._fragment_body(frag_quote)
    assert body_q.text_align == ft.TextAlign.JUSTIFY

    frag_comment = {"id": 2, "fragment_type": "comment", "excerpt": "Trecho da paráfrase"}
    body_c = hub._fragment_body(frag_comment)
    assert body_c.text_align == ft.TextAlign.JUSTIFY

    # Note footer
    frag_with_note = {"id": 1, "work_note": "Nota importante de articulação"}
    note_ctrl = hub._compose_fragment_note(frag_with_note)
    text_in_footer = note_ctrl.content.controls[0]
    assert text_in_footer.text_align == ft.TextAlign.JUSTIFY


def test_work_details_popup_synthesis_is_justified():
    cfg = _view_config()
    res = MagicMock()
    res.id = 1
    res.effective_description = "Esta é uma síntese epistemológica gerada pela mente racional."
    res.custom_description = "Síntese"
    res.llm_description = None
    res.url = None
    res.doi = None
    res.authors = []

    popup = WorkDetailsPopup(
        resource=res,
        config=cfg,
        on_close=lambda: None,
        page=MagicMock(),
    )
    synthesis_body = popup._build_synthesis_body()
    # The text widget is the second control in the column
    text_widget = synthesis_body.controls[1]
    assert text_widget.text_align == ft.TextAlign.JUSTIFY


def test_nous_and_knowledge_panel_justification():
    cfg = _view_config()
    panel = KnowledgePanel(
        config=cfg,
        scale=1.0,
        on_close=lambda: None,
        on_select_resonance=lambda _res: None,
        page=MagicMock(),
    )
    assert panel.excerpt_text.text_align == ft.TextAlign.JUSTIFY
