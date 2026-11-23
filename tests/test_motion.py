"""Testes do sistema de movimento do UI Kit (durações, hover e seleção)."""

import flet as ft

from src.views import ui_kit as ui
from src.views.command_palette import CommandPalette
from src.views.sidebar import SidebarComposer, SidebarData


def test_motion_tokens_are_ordered_and_use_ease_out():
    durations = [
        ui.MOTION_INSTANT,
        ui.MOTION_FAST,
        ui.MOTION_BASE,
        ui.MOTION_SLOW,
    ]
    assert durations == sorted(durations)

    animation = ui.motion(ui.MOTION_BASE)
    assert isinstance(animation, ft.Animation)
    assert animation.duration == ui.MOTION_BASE
    assert animation.curve == ft.AnimationCurve.EASE_OUT


def test_sidebar_hover_animates_glyph_and_surface(view_config):
    sidebar = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=lambda _d: None,
        current="Acervo",
    )
    items = {
        control.data: control
        for control in _walk(sidebar.compose())
        if isinstance(getattr(control, "data", None), str)
    }
    fragmentos = items["Fragmentos"]
    assert fragmentos.animate is not None

    glyph_box = fragmentos.content.controls[0]
    assert glyph_box.animate_scale is not None

    fragmentos.on_hover(_Event("true"))
    assert glyph_box.scale == 1.12
    fragmentos.on_hover(_Event("false"))
    assert glyph_box.scale == 1.0


def test_command_palette_selection_animates_without_rebuilding_rows(view_config):
    palette = CommandPalette(
        page=None,
        config=view_config,
        search=lambda _query: {"works": [], "fragments": []},
        on_open_work=lambda _wid: None,
        on_open_fragments=lambda _query: None,
        actions=[
            ("plus", "Nova obra", None, lambda: None),
            ("book", "Ir para Acervo", None, lambda: None),
        ],
    )
    palette._render("")
    rows = list(palette._rows)
    assert len(rows) == 2
    assert rows[0][0].bgcolor == view_config.colors["selected"]
    assert rows[0][0].animate is not None

    palette.handle_key("Arrow Down")

    # A mesma instância de linha é reaproveitada: só o destaque muda.
    assert palette._rows[0][0] is rows[0][0]
    assert rows[0][0].bgcolor is None
    assert rows[1][0].bgcolor == view_config.colors["selected"]


def test_sidebar_state_change_reopens_projects_when_navigating_to_compilation(view_config):
    sidebar = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=lambda _d: None,
        current="Acervo",
        data=SidebarData(compilations=[(7, "Caderno Sete")]),
        compilations_expanded=False,
    )
    sidebar.compose()
    assert "compilacao:7" not in sidebar._items

    sidebar.update_state("compilacao:7", SidebarData(compilations=[(7, "Caderno Sete")]))

    assert sidebar.compilations_expanded is True
    assert "compilacao:7" in sidebar._items
    assert sidebar._items["compilacao:7"]["state"]["active"] is True


def test_sidebar_state_change_repaints_without_rebuilding(view_config):
    sidebar = SidebarComposer(
        scale=1.0,
        config=view_config,
        on_navigate=lambda _d: None,
        current="Acervo",
        data=SidebarData(works=3),
    )
    composed = sidebar.compose()
    items = {
        control.data: control
        for control in _walk(composed)
        if isinstance(getattr(control, "data", None), str)
    }
    acervo = items["Acervo"]
    fragmentos = items["Fragmentos"]
    assert acervo.bgcolor == view_config.colors["selected"]

    sidebar.update_state("Fragmentos", SidebarData(works=4))

    # Mesmos controles: nada foi reconstruído.
    assert items["Acervo"] is acervo
    assert acervo.bgcolor is None
    assert fragmentos.bgcolor == view_config.colors["selected"]
    assert acervo.content.controls[2].value == "4"


class _Event:
    def __init__(self, data: str) -> None:
        self.data = data


def _walk(control):
    yield control
    content = getattr(control, "content", None)
    if isinstance(content, list):
        for item in content:
            yield from _walk(item)
    elif content is not None and hasattr(content, "__dict__"):
        yield from _walk(content)
    for item in getattr(control, "controls", []) or []:
        yield from _walk(item)


def test_ui_kit_hover_survives_frozen_controls(view_config):
    """Hover é o fluxo que mais recebeu 'Frozen controls cannot be updated'."""
    icon_box = ui.icon_button(view_config, "copy", boxed=True)
    glyph = icon_box.content
    object.__setattr__(icon_box, "_frozen", True)
    object.__setattr__(glyph, "_frozen", True)

    icon_box.on_hover(_Event("true"))

    assert glyph.scale == 1.08
    assert not hasattr(glyph, "_frozen")

    icon_box.on_hover(_Event("false"))
    assert glyph.scale == 1.0

    link = ui.link_button(view_config, "Ver obra")
    link_text = link.content.controls[0]
    link_glyph = link.content.controls[1]
    for control in (link, link_text, link_glyph):
        object.__setattr__(control, "_frozen", True)
    link.on_hover(_Event("true"))
    assert link_text.color == view_config.colors["gold"]
    assert link_glyph.offset.x == 0.18
    assert not hasattr(link, "_frozen")
