"""Testes do fatiamento de ``PdfReaderView`` em cinco mixins."""

import flet as ft

from src.views.pdf_reader import PdfReaderView
from src.views.pdf_reader.pdf_common import BASE_PAGE_HEIGHT
from src.views.pdf_reader.pdf_fragments_mixin import PdfFragmentsMixin
from src.views.pdf_reader.pdf_navigation_mixin import PdfNavigationMixin
from src.views.pdf_reader.pdf_pan_mixin import PdfPanSelectionMixin
from src.views.pdf_reader.pdf_render_mixin import PdfRenderMixin
from src.views.pdf_reader.pdf_tools_mixin import PdfToolsMixin


def test_reader_mro_places_mixins_before_container():
    assert PdfReaderView.__mro__[1:7] == (
        PdfToolsMixin,
        PdfPanSelectionMixin,
        PdfNavigationMixin,
        PdfFragmentsMixin,
        PdfRenderMixin,
        ft.Container,
    )


def test_each_method_lives_in_its_designated_mixin():
    expected = {
        PdfToolsMixin: (
            "_render_tool_mode_selector",
            "_on_view_mode_change",
            "set_compact_mode",
            "did_mount",
        ),
        PdfPanSelectionMixin: (
            "_is_ctrl_down",
            "_on_mouse_scroll",
            "_on_pan_update",
            "_on_text_selection_change",
        ),
        PdfNavigationMixin: (
            "_start_page_edit",
            "_submit_page_input",
            "handle_key",
            "_next_page",
            "_zoom_in",
            "_toggle_sidebar",
        ),
        PdfFragmentsMixin: (
            "_handle_new_fragment_click",
            "_save_fragment_from_modal",
            "_refresh_fragments_list",
        ),
        PdfRenderMixin: (
            "_handle_attach_pdf",
            "_render_page_into_card",
            "_load_current_page",
            "_copy_page_text",
        ),
    }
    for mixin, names in expected.items():
        for name in names:
            assert name in mixin.__dict__, f"{name} ausente em {mixin.__name__}"


def test_facade_keeps_lifecycle_and_layout():
    for name in (
        "__init__",
        "is_modal_open",
        "page",
        "_init_pdf_document",
        "close",
        "_handle_back",
        "_build_layout",
    ):
        assert name in PdfReaderView.__dict__


def test_no_method_is_defined_twice_among_custom_mixins():
    owners: dict[str, list[str]] = {}
    custom_classes = PdfReaderView.__mro__[:6]
    for klass in custom_classes:
        for name, value in vars(klass).items():
            if name.startswith("__") or not callable(value):
                continue
            owners.setdefault(name, []).append(klass.__name__)
    duplicated = {name: klasses for name, klasses in owners.items() if len(klasses) > 1}

    assert duplicated == {}


def test_mixins_have_no_initializer():
    for mixin in (
        PdfToolsMixin,
        PdfPanSelectionMixin,
        PdfNavigationMixin,
        PdfFragmentsMixin,
        PdfRenderMixin,
    ):
        assert "__init__" not in mixin.__dict__


def test_base_page_height_is_reexported():
    from src.views.pdf_reader import reader_view

    assert BASE_PAGE_HEIGHT == 680
    assert reader_view.BASE_PAGE_HEIGHT == BASE_PAGE_HEIGHT
