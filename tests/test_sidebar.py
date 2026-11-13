"""Testes unitários para o SidebarComposer e delimitação de espaço na barra lateral."""

import flet as ft

from src.views.sidebar import SidebarComposer, SidebarData
from src.views.ui_kit import s


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


def test_sidebar_compilations_order_and_collapsible_behavior(view_config):
    toggled = []
    navigated = []
    sidebar = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=navigated.append,
        data=SidebarData(compilations=[(1, "Caderno Alpha"), (2, "Caderno Beta")]),
        compilations_expanded=True,
        on_toggle_compilations=toggled.append,
    )
    composed = sidebar.compose()
    items = {item.data: item for item in _nav_items(composed)}
    destinations = [item.data for item in _nav_items(composed)]

    # "Compilações" (Todas as compilações) deve vir ANTES de qualquer compilação filha
    assert "Compilações" in destinations
    assert "compilacao:1" in destinations
    assert "compilacao:2" in destinations
    assert destinations.index("Compilações") < destinations.index("compilacao:1")
    assert destinations.index("compilacao:1") < destinations.index("compilacao:2")

    # Item 'Compilações' possui o chevron trailing
    root_item = items["Compilações"]
    row_controls = root_item.content.controls
    # [glyph, label_text, count_ctrl, chevron_btn]
    assert len(row_controls) == 4
    chevron_btn = row_controls[3]
    assert callable(chevron_btn.on_click)

    # Clicar no chevron alterna expansão sem navegar
    chevron_btn.on_click(None)
    assert toggled == [False]
    assert navigated == []

    # Clicar no corpo de 'Compilações' navega normalmente
    root_item.on_click(None)
    assert navigated == ["Compilações"]

    # Quando recolhido, as compilações filhas não devem constar no DOM
    sidebar_collapsed = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=lambda _d: None,
        data=SidebarData(compilations=[(1, "Caderno Alpha")]),
        compilations_expanded=False,
    )
    collapsed_destinations = [item.data for item in _nav_items(sidebar_collapsed.compose())]
    assert "Compilações" in collapsed_destinations
    assert "compilacao:1" not in collapsed_destinations

    # Auto-expansão quando o destino atual for um caderno filho
    sidebar_auto = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=lambda _d: None,
        current="compilacao:1",
        data=SidebarData(compilations=[(1, "Caderno Alpha")]),
        compilations_expanded=False,
    )
    auto_destinations = [item.data for item in _nav_items(sidebar_auto.compose())]
    assert "compilacao:1" in auto_destinations
