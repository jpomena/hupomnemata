"""Testes do controlador da paleta ⌘K extraído do CoreComposer."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.views.command_palette import CommandPaletteController


def _composer(view_config):
    calls: dict[str, list] = {
        "navigate": [],
        "navigate_with": [],
        "import": [],
        "reverse": [],
        "theme": [],
    }
    composer = SimpleNamespace(
        page=MagicMock(),
        config=view_config,
        palette_search=lambda query: {"works": [], "fragments": []},
        on_navigate=lambda destination: calls["navigate"].append(destination),
        on_navigate_with=lambda destination, **options: calls[
            "navigate_with"
        ].append((destination, options)),
        on_import_work=lambda: calls["import"].append(True),
        on_reverse_import=lambda: calls["reverse"].append(True),
        on_toggle_theme=lambda: calls["theme"].append(True),
    )
    return composer, calls


def test_open_builds_palette_and_exposes_actions(view_config):
    composer, _calls = _composer(view_config)

    CommandPaletteController(composer).open()

    assert composer.palette.is_open is True
    labels = [action[1] for action in composer.palette.actions]
    assert "Inserir nova obra" in labels
    assert "Importar obra (DOI, ISBN, ISSN)" in labels
    assert "Importar por referências (texto / Nous)" in labels
    assert "Ir para Compilações" in labels


def test_actions_dispatch_to_composer_callbacks(view_config):
    composer, calls = _composer(view_config)
    controller = CommandPaletteController(composer)
    controller.open()

    actions = {label: handler for _icon, label, _hint, handler in composer.palette.actions}
    actions["Inserir nova obra"]()
    actions["Importar obra (DOI, ISBN, ISSN)"]()
    actions["Importar por referências (texto / Nous)"]()
    actions["Alternar tema"]()
    actions["Ir para Acervo"]()

    assert calls["navigate"] == ["work_insert", "Acervo"]
    assert calls["import"] == [True]
    assert calls["reverse"] == [True]
    assert calls["theme"] == [True]


def test_handle_key_returns_false_without_open_palette(view_config):
    composer, _calls = _composer(view_config)
    controller = CommandPaletteController(composer)

    assert controller.handle_key("Arrow Down") is False


def test_handle_key_delegates_when_palette_is_open(view_config):
    composer, _calls = _composer(view_config)
    seen: list[str] = []
    composer.palette = SimpleNamespace(
        is_open=True,
        handle_key=lambda key: seen.append(key) or True,
    )

    result = CommandPaletteController(composer).handle_key("Escape")

    assert result is True
    assert seen == ["Escape"]


def test_open_without_page_is_a_noop(view_config):
    composer, _calls = _composer(view_config)
    composer.page = None

    CommandPaletteController(composer).open()

    assert not hasattr(composer, "palette")
