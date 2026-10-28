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
from src.views.sidebar import SidebarComposer


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


def test_sidebar_navigation_scroll_and_expand(view_config):
    navigated = []
    sidebar = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=navigated.append,
    )
    composed = sidebar.compose()
    assert isinstance(composed, ft.Container)

    # Coluna principal
    main_column = composed.content
    assert isinstance(main_column, ft.Column)
    assert main_column.spacing == 0
    assert len(main_column.controls) == 3

    # Seção 1: Branding
    branding = main_column.controls[0]
    assert isinstance(branding, ft.Container)

    # Seção 2: Navegação
    nav_container = main_column.controls[1]
    assert isinstance(nav_container, ft.Container)
    assert nav_container.expand is True

    nav_column = nav_container.content
    assert isinstance(nav_column, ft.Column)
    assert nav_column.expand is True
    # O scroll AUTO garante que os itens nunca invadam o rodapé
    assert nav_column.scroll == ft.ScrollMode.AUTO

    # Verifica que todos os menus estão contidos na coluna
    cadernos_header = nav_column.controls[0]
    assert cadernos_header.value == "Cadernos"
    menu_items = nav_column.controls[1:]
    assert len(menu_items) == len(view_config.core_menus)


def test_sidebar_footnote_height_and_scroll_constraints(view_config):
    # Teste na escala padrão 1.0x (altura variável para se ajustar à citação)
    sidebar_normal = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=lambda _: None,
    )
    composed_normal = sidebar_normal.compose()
    footnote_normal = composed_normal.content.controls[2]
    assert isinstance(footnote_normal, ft.Container)
    # A altura rígida foi removida para permitir que o painel se ajuste à citação
    assert footnote_normal.height is None

    # A citação deve estar contida em uma coluna compacta (tight) que cresce com o texto
    inner_column = footnote_normal.content
    assert isinstance(inner_column, ft.Column)
    assert inner_column.tight is True
    citation_text = inner_column.controls[0]
    assert isinstance(citation_text, ft.Text)
    assert citation_text.size == view_config.font_sizes["cormorant_small"] * 1.0

    # Teste na escala grande 1.40x (ambos menu e painel crescem proporcionalmente)
    sidebar_large = SidebarComposer(
        scale=1.40,
        config=view_config,
        on_navigate=lambda _: None,
    )
    composed_large = sidebar_large.compose()
    footnote_large = composed_large.content.controls[2]
    assert footnote_large.height is None
    citation_large = footnote_large.content.controls[0]
    assert citation_large.size == view_config.font_sizes["cormorant_small"] * 1.40

    # Teste na escala reduzida 0.80x
    sidebar_small = SidebarComposer(
        scale=0.80,
        config=view_config,
        on_navigate=lambda _: None,
    )
    composed_small = sidebar_small.compose()
    footnote_small = composed_small.content.controls[2]
    assert footnote_small.height is None
    citation_small = footnote_small.content.controls[0]
    assert citation_small.size == view_config.font_sizes["cormorant_small"] * 0.80


def test_sidebar_menu_click_triggers_navigation(view_config):
    navigated = []
    sidebar = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=navigated.append,
    )
    composed = sidebar.compose()
    nav_column = composed.content.controls[1].content
    menu_button = nav_column.controls[1]  # Primeiro item de menu ("Acervo")

    menu_button.on_click(None)
    assert "Acervo" in navigated
