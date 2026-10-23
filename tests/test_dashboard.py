from types import SimpleNamespace

import flet as ft

from src.configs.settings import (
    COLORS,
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
        colors=COLORS,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={
            "Nous": "analytics",
            "Configurações": "settings",
            "Limbo": "thrash",
            "Estruturas de Saber": "hub_outlined",
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
            "Nous",
            "Configurações",
            "Limbo",
            "Estruturas de Saber",
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
