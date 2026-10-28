from types import SimpleNamespace

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
from src.controllers.core_controller import CoreController
from src.utils.types import ViewConfig
from src.views.core_composer import CoreComposer


def test_incomplete_sections_show_wip_dashboard():
    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={
            "Limbo": "thrash",
        },
        main_view_cards=MAIN_VIEW_CARDS,
    )
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = config
    composer.scale = 1
    composer.on_navigate = lambda _destination: None
    composer.content = SimpleNamespace(content=None, update=lambda: None)

    navigated_sections = []
    controller = CoreController.__new__(CoreController)
    controller.application = SimpleNamespace(
        show_view=navigated_sections.append,
    )

    for section in config.core_menus:
        if section not in {
            "Limbo",
        }:
            continue
        controller.navigate(section)
        composer.show_view(section)

        view = composer.content.content
        header = view.content.controls[0]
        heading = header.content.controls[0].controls
        assert heading[0].value == "Oops..."
        assert heading[1].value == section

        body = view.content.controls[1]
        image, message = body.content.controls
        assert image.src == "assets/images/wip.png"
        assert message.value == "Esta seção ainda está em construção."

    assert navigated_sections == list(config.core_menus)


def test_nous_section_shows_nous_view():
    from unittest.mock import MagicMock
    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={
            "Nous": "analytics",
        },
        main_view_cards=MAIN_VIEW_CARDS,
    )
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = config
    composer.scale = 1
    composer.on_navigate = lambda _destination: None
    composer.content = SimpleNamespace(content=None, update=lambda: None)
    mock_nous_service = MagicMock()
    mock_nous_service.get_api_key.return_value = ""
    mock_nous_service.list_works_ai_status.return_value = []
    composer.nous_service = mock_nous_service

    composer.show_view("Nous")
    assert composer.content.content is not None
    assert composer.nous_composer is not None


def test_estruturas_de_saber_shows_knowledge_view():
    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={
            "Estruturas de Saber": "hub_outlined",
        },
        main_view_cards=MAIN_VIEW_CARDS,
    )
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = config
    composer.scale = 1
    composer.on_navigate = lambda _destination: None
    composer.content = SimpleNamespace(content=None, update=lambda: None)

    composer.show_view("Estruturas de Saber")
    assert composer.content.content is not None
    assert composer.knowledge_composer is not None


def test_settings_section_shows_settings_dashboard():
    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={
            "Configurações": "settings",
        },
        main_view_cards=MAIN_VIEW_CARDS,
    )
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = config
    composer.scale = 1.0
    composer.current_theme_mode = "light"
    composer.auto_scale = True
    composer.manual_scale = 1.0
    composer.on_navigate = lambda _destination: None
    composer.on_change_theme = lambda _t: None
    composer.on_toggle_auto_scale = lambda _a: None
    composer.on_change_scale = lambda _s: None
    composer.on_reset_settings = lambda: None
    composer.content = SimpleNamespace(content=None, update=lambda: None)

    composer.show_view("Configurações")
    view = composer.content.content
    assert view is not None

    # Check header
    header = view.content.controls[0]
    heading = header.content.controls[0].controls
    assert heading[0].value == "Configurações"
    assert heading[1].value == "Personalize a aparência, tema e proporções visuais do gabinete."

    # Check cards container and controls
    body = view.content.controls[1]
    scroll_column = body.content
    assert isinstance(scroll_column, ft.Column)
    cards_row = scroll_column.controls[0]
    assert isinstance(cards_row, ft.ResponsiveRow)
    assert len(cards_row.controls) == 3

