"""Testes do chrome da janela extraido de ``CoreComposer``."""

from types import SimpleNamespace

import flet as ft

from src.utils.fa import glyph as fa_glyph
from src.views.core_composer import CoreComposer
from src.views.sidebar import SidebarData
from src.views.window_chrome import WindowChromeComposer


def _bare_composer(config, **overrides):
    """Instancia ``CoreComposer`` via ``__new__`` com o minimo do chrome."""
    composer = CoreComposer.__new__(CoreComposer)
    composer.page = SimpleNamespace(
        window=SimpleNamespace(maximized=False),
        update=lambda: None,
    )
    composer.scale = 1.0
    composer.config = config
    composer.on_navigate = lambda _destination: None
    composer.on_toggle_maximize = None
    composer.on_history = lambda _step: None
    composer.can_go_back = False
    composer.can_go_forward = False
    composer.current_destination = "dashboard"
    composer.get_sidebar_data = None
    for key, value in overrides.items():
        setattr(composer, key, value)
    return composer


def test_compose_title_bar_populates_composer(view_config):
    composer = _bare_composer(view_config, can_go_back=True)

    title_bar = composer._compose_custom_title_bar()

    assert isinstance(title_bar, ft.WindowDragArea)
    for attribute in (
        "maximize_button",
        "back_button",
        "forward_button",
        "history_host",
        "crumbs_host",
    ):
        assert getattr(composer, attribute) is not None

    row = title_bar.content.content
    assert isinstance(row, ft.Row)
    assert row.controls[1] is composer.history_host
    assert row.controls[2] is composer.crumbs_host
    assert row.controls[-1].controls[1] is composer.maximize_button

    square, _ = fa_glyph("square", "regular")
    assert composer.maximize_button.data.value == square
    assert composer.maximize_button.tooltip == "Maximizar"
    assert composer.back_button.on_click is not None
    assert composer.forward_button.on_click is None

    assert isinstance(composer._chrome(), WindowChromeComposer)
    assert composer._chrome() is composer._window_chrome


def test_update_window_state_keeps_button_identity(view_config):
    composer = _bare_composer(view_config)
    composer._compose_custom_title_bar()
    button = composer.maximize_button
    square, _ = fa_glyph("square", "regular")
    clone, _ = fa_glyph("clone", "regular")

    composer.update_window_state(True)

    assert composer.maximize_button is button
    assert button.data.value == clone
    assert button.tooltip == "Restaurar"

    composer.update_window_state(False)

    assert composer.maximize_button is button
    assert button.data.value == square
    assert button.tooltip == "Maximizar"


def test_set_history_state_rebuilds_buttons(view_config):
    composer = _bare_composer(view_config)
    composer._compose_custom_title_bar()
    previous_back = composer.back_button
    previous_forward = composer.forward_button

    composer.set_history_state(True, False)

    assert composer.can_go_back is True
    assert composer.can_go_forward is False
    assert composer.back_button is not previous_back
    assert composer.forward_button is not previous_forward
    assert composer.history_host.content.controls == [
        composer.back_button,
        composer.forward_button,
    ]
    assert composer.back_button.on_click is not None
    assert composer.forward_button.on_click is None

    composer.set_history_state(False, True)

    assert composer.back_button.on_click is None
    assert composer.forward_button.on_click is not None


def test_crumb_parts_dashboard_and_compilation(view_config):
    composer = _bare_composer(view_config)

    assert composer._crumb_parts() == [("Início", None)]

    composer.current_destination = "compilacao:7"
    composer.get_sidebar_data = lambda: SidebarData(
        compilations=[(7, "Caderno Sete")]
    )

    assert composer._crumb_parts() == [
        ("Compilações", "Compilações"),
        ("Caderno Sete", None),
    ]


def test_refresh_chrome_rebuilds_crumbs(view_config):
    composer = _bare_composer(view_config)
    composer._compose_custom_title_bar()
    composer.current_destination = "compilacao:7"
    composer.get_sidebar_data = lambda: SidebarData(
        compilations=[(7, "Caderno Sete")]
    )

    composer.refresh_chrome()

    crumbs = composer.crumbs_host.controls
    assert len(crumbs) == 3
    assert crumbs[-1].content.value == "Caderno Sete"


def test_chrome_facades_remain_on_core_composer():
    facade_names = {
        "_window_control_button": "window_control_button",
        "_compose_custom_title_bar": "compose_title_bar",
        "_crumb_parts": "crumb_parts",
        "_crumb_controls": "crumb_controls",
        "compilation_name": "compilation_name",
        "set_history_state": "set_history_state",
        "update_window_state": "update_window_state",
    }
    for facade, chrome_method in facade_names.items():
        assert facade in CoreComposer.__dict__
        assert callable(getattr(WindowChromeComposer, chrome_method))
    assert "refresh_crumbs" in WindowChromeComposer.__dict__
    assert "refresh_chrome" in CoreComposer.__dict__
