"""Testes da fábrica de telas e das fachadas de composição do CoreComposer."""

from types import SimpleNamespace

import flet as ft
import pytest

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
from src.utils.types import ViewConfig
from src.views.core_composer import CoreComposer
from src.views.view_factory import ViewFactory


def _config() -> ViewConfig:
    return ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={"dashboard": "home"},
        main_view_cards=MAIN_VIEW_CARDS,
    )


def _composer() -> CoreComposer:
    """Composer criado sem ``__init__``, como fazem os testes legados."""
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = _config()
    composer.scale = 1.0
    composer.on_navigate = lambda _destination, **_kw: None
    composer.get_dashboard_data = None
    composer.on_navigate_with = None
    composer.on_import_work = None
    composer.on_reverse_import = None
    composer.open_fragment_create = lambda: None
    composer.open_palette = lambda: None
    composer.content = SimpleNamespace(content=None, update=lambda: None)
    return composer


def test_view_factory_dashboard_returns_control_without_core_init():
    composer = _composer()

    factory = ViewFactory(composer)
    control = factory.dashboard()

    assert factory.composer is composer
    assert isinstance(control, ft.Control)


def test_show_view_builds_factory_lazily_without_core_init():
    composer = _composer()

    composer.show_view("dashboard")

    assert getattr(composer, "_views", None) is not None
    assert composer.view_options == {}
    assert isinstance(composer.content.content, ft.Control)


def test_show_view_keeps_view_options_for_the_factory():
    composer = _composer()

    composer.show_view("dashboard", focus_work_id=7)

    assert composer.view_options == {"focus_work_id": 7}


def test_compose_knowledge_facade_builds_knowledge_composer():
    composer = _composer()

    control = composer._compose_knowledge()

    assert isinstance(control, ft.Control)
    assert composer.knowledge_composer is not None


def test_compose_knowledge_facade_delegates_to_factory():
    composer = _composer()
    sentinel = object()

    class _StubFactory:
        def knowledge(self):
            return sentinel

    composer._views = _StubFactory()

    assert composer._compose_knowledge() is sentinel


@pytest.mark.parametrize(
    ("facade", "method", "invoke"),
    [
        ("_compose_dashboard", "dashboard", lambda c: c._compose_dashboard()),
        ("_compose_works", "works", lambda c: c._compose_works(None)),
        ("_compose_fragments", "fragments", lambda c: c._compose_fragments(None)),
        (
            "_compose_compilations",
            "compilations",
            lambda c: c._compose_compilations(None),
        ),
        (
            "_compose_compilation_page",
            "compilation_page",
            lambda c: c._compose_compilation_page(None, 1),
        ),
        ("_compose_pdf_reader", "pdf_reader", lambda c: c._compose_pdf_reader(1)),
        (
            "_compose_placeholder_dashboard",
            "placeholder",
            lambda c: c._compose_placeholder_dashboard("Limbo"),
        ),
        ("_compose_settings", "settings", lambda c: c._compose_settings()),
        ("_compose_nous", "nous", lambda c: c._compose_nous()),
        ("_compose_knowledge", "knowledge", lambda c: c._compose_knowledge()),
    ],
)
def test_compose_facades_delegate_to_view_factory(facade, method, invoke):
    composer = _composer()
    calls = []

    def _stub(*args, **kwargs):
        calls.append((args, kwargs))
        return ft.Container()

    composer._views = SimpleNamespace(**{method: _stub})

    result = invoke(composer)

    assert isinstance(result, ft.Container)
    assert len(calls) == 1


def test_core_composer_keeps_public_entrypoints_and_facades():
    for name in (
        "show_view",
        "_view_factory",
        "_compose_dashboard",
        "_compose_works",
        "_compose_fragments",
        "_compose_compilations",
        "_compose_compilation_page",
        "_compose_pdf_reader",
        "_compose_placeholder_dashboard",
        "_compose_settings",
        "_compose_nous",
        "_compose_knowledge",
    ):
        assert name in CoreComposer.__dict__, name


def test_view_factory_exposes_public_composition_api():
    for name in (
        "dashboard",
        "works",
        "fragments",
        "compilations",
        "compilation_page",
        "pdf_reader",
        "placeholder",
        "settings",
        "nous",
        "knowledge",
    ):
        assert callable(getattr(ViewFactory, name)), name
