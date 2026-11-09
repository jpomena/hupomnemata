"""Testes unitários para o SidebarComposer e delimitação de espaço na barra lateral."""

import flet as ft
import pytest

from src.configs.settings import (
    COLORS_DARK,
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
from src.views.sidebar import SidebarComposer, SidebarData
from src.views.ui_kit import s


@pytest.fixture
def view_config():
    return ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus=CORE_MENUS,
        main_view_cards=MAIN_VIEW_CARDS,
    )


def _walk(control):
    yield control
    for attr in ("content", "controls"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for item in child:
                yield from _walk(item)
        elif child is not None and hasattr(child, "__dict__"):
            yield from _walk(child)


def _nav_items(sidebar_control):
    return [c for c in _walk(sidebar_control) if isinstance(getattr(c, "data", None), str)]


def test_sidebar_structure_and_scrollable_navigation(view_config):
    sidebar = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=lambda _d: None,
        data=SidebarData(works=29, fragments=47, compilations=[(1, "O multiplicador punitivo")]),
    )
    composed = sidebar.compose()
    assert isinstance(composed, ft.Container)
    main_column = composed.content
    assert isinstance(main_column, ft.Column)
    assert len(main_column.controls) == 3  # busca, navegação, rodapé

    nav_container = main_column.controls[1]
    assert nav_container.expand is True
    assert nav_container.content.scroll == ft.ScrollMode.AUTO

    destinations = [item.data for item in _nav_items(composed)]
    for expected in ("dashboard", "Acervo", "Fragmentos", "compilacao:1", "Compilações", "Estruturas de Saber", "Nous", "Configurações"):
        assert expected in destinations


def test_sidebar_marks_current_destination(view_config):
    sidebar = SidebarComposer(scale=1.0, config=view_config, on_navigate=lambda _d: None, current="Acervo")
    items = {item.data: item for item in _nav_items(sidebar.compose())}
    assert items["Acervo"].bgcolor == view_config.colors["selected"]
    assert items["Fragmentos"].bgcolor is None


def test_sidebar_menu_click_triggers_navigation(view_config):
    navigated = []
    sidebar = SidebarComposer(
        scale=1.0, config=view_config, on_navigate=navigated.append,
        data=SidebarData(compilations=[(7, "Tese")]),
    )
    items = {item.data: item for item in _nav_items(sidebar.compose())}
    items["Fragmentos"].on_click(None)
    items["compilacao:7"].on_click(None)
    assert navigated == ["Fragmentos", "compilacao:7"]


def test_sidebar_item_hover_illuminates_glyph_and_label(view_config):
    from types import SimpleNamespace
    sidebar = SidebarComposer(
        scale=1.0, config=view_config, on_navigate=lambda _d: None, current="Acervo",
        data=SidebarData(compilations=[(7, "Tese")]),
    )
    items = {item.data: item for item in _nav_items(sidebar.compose())}
    inactive_item = items["Fragmentos"]
    assert callable(inactive_item.on_hover)

    # Hover in
    inactive_item.on_hover(SimpleNamespace(data="true"))
    assert inactive_item.bgcolor == view_config.colors["card_hover"]
    assert inactive_item.border.left.color == view_config.colors["gold"]
    assert inactive_item.border.left.width == s(3)
    # Row controls: [Container(glyph), label_text, count]
    row = inactive_item.content
    glyph_container, label_text = row.controls[0], row.controls[1]
    assert glyph_container.content.color == view_config.colors["gold"]
    assert label_text.color == view_config.colors["gold"]

    # Hover out
    inactive_item.on_hover(SimpleNamespace(data="false"))
    assert inactive_item.bgcolor is None
    assert inactive_item.border is None
    assert glyph_container.content.color == view_config.colors["faint"]
    assert label_text.color == view_config.colors["muted"]
