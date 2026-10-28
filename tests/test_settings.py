"""Testes unitários e de integração para o módulo de Configurações."""

from types import SimpleNamespace
from pathlib import Path
import pytest
import flet as ft

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
from src.controllers.core_controller import CoreController
from src.services.settings_service import (
    AppearanceSettings,
    SettingsService,
    resolve_effective_scale,
    resolve_effective_theme,
)
from src.utils.types import ViewConfig
from src.views.settings import SettingsComposer
from src.views.core_composer import CoreComposer


@pytest.fixture
def test_config():
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


def test_appearance_settings_defaults():
    settings = AppearanceSettings()
    assert settings.theme_mode == "light"
    assert settings.auto_scale is True
    assert settings.manual_scale == 1.0


def test_appearance_settings_serialization_and_clamping():
    data = {
        "theme_mode": "dark",
        "auto_scale": False,
        "manual_scale": 1.75,  # Exceeds max 1.40
    }
    settings = AppearanceSettings.from_dict(data)
    assert settings.theme_mode == "dark"
    assert settings.auto_scale is False
    assert settings.manual_scale == 1.40

    data_low = {
        "theme_mode": "invalid_mode",
        "auto_scale": "yes",
        "manual_scale": 0.50,  # Below min 0.80
    }
    settings_low = AppearanceSettings.from_dict(data_low)
    assert settings_low.theme_mode == "light"
    assert settings_low.auto_scale is True
    assert settings_low.manual_scale == 0.80

    as_dict = settings.to_dict()
    assert as_dict["theme_mode"] == "dark"
    assert as_dict["auto_scale"] is False
    assert as_dict["manual_scale"] == 1.40


def test_resolve_effective_theme():
    assert resolve_effective_theme("light") == "light"
    assert resolve_effective_theme("dark") == "dark"

    # System with dark brightness
    page_dark = SimpleNamespace(platform_brightness=ft.Brightness.DARK)
    assert resolve_effective_theme("system", page_dark) == "dark"

    # System with light brightness
    page_light = SimpleNamespace(platform_brightness=ft.Brightness.LIGHT)
    assert resolve_effective_theme("system", page_light) == "light"

    # System without brightness info defaults to light
    page_none = SimpleNamespace()
    assert resolve_effective_theme("system", page_none) == "light"
    assert resolve_effective_theme("system", None) == "light"


def test_resolve_effective_scale():
    settings_manual = AppearanceSettings(auto_scale=False, manual_scale=1.20)
    assert resolve_effective_scale(settings_manual, None) == 1.20

    # Auto scale calculates from page dimensions
    settings_auto = AppearanceSettings(auto_scale=True, manual_scale=1.0)
    page_1080p = SimpleNamespace(
        width=1920,
        height=1080,
        window=SimpleNamespace(maximized=False),
    )
    # 1920 / 1280 = 1.5, 1080 / 720 = 1.5
    assert resolve_effective_scale(settings_auto, page_1080p) == 1.50

    page_small = SimpleNamespace(
        width=800,
        height=600,
        window=SimpleNamespace(maximized=False),
    )
    # min(800/1280, 600/720) = min(0.625, 0.833) = 0.625 -> clamped to 0.75
    assert resolve_effective_scale(settings_auto, page_small) == 0.75

    # Com auto_scale=False, a escala manual é rigorosamente preservada sem upscale não planejado
    settings_fixed = AppearanceSettings(auto_scale=False, manual_scale=1.0)
    page_max = SimpleNamespace(
        width=1920,
        height=1080,
        window=SimpleNamespace(maximized=True),
    )
    assert resolve_effective_scale(settings_fixed, page_max) == 1.0

    # Quando desmaximizado, retorna a escala manual fixada (1.0)
    page_unmax = SimpleNamespace(
        width=1400,
        height=900,
        window=SimpleNamespace(maximized=False),
    )
    assert resolve_effective_scale(settings_fixed, page_unmax) == 1.0


def test_settings_service_persistence(tmp_path):
    storage_path = tmp_path / "user_preferences.json"
    service = SettingsService(storage_path)

    # Initial load returns defaults
    settings = service.load_settings()
    assert settings.theme_mode == "light"

    # Save custom settings
    settings.theme_mode = "dark"
    settings.auto_scale = False
    settings.manual_scale = 1.15
    assert service.save_settings(settings) is True
    assert storage_path.exists()

    # Re-load from disk
    loaded = service.load_settings()
    assert loaded.theme_mode == "dark"
    assert loaded.auto_scale is False
    assert loaded.manual_scale == 1.15

    # Reset to defaults
    reset = service.reset_to_defaults()
    assert reset.theme_mode == "light"
    assert reset.auto_scale is True
    assert reset.manual_scale == 1.0


def test_settings_composer_structure_and_callbacks(test_config):
    theme_calls = []
    scale_calls = []
    auto_scale_calls = []
    reset_calls = []

    composer = SettingsComposer(
        scale=1.0,
        config=test_config,
        current_theme_mode="light",
        auto_scale=True,
        manual_scale=1.0,
        effective_scale=1.0,
        on_navigate=lambda _: None,
        on_change_theme=theme_calls.append,
        on_toggle_auto_scale=auto_scale_calls.append,
        on_change_scale=scale_calls.append,
        on_reset_settings=lambda: reset_calls.append(True),
    )

    view = composer.compose()
    assert isinstance(view, ft.Container)

    # Check header
    header = view.content.controls[0]
    title_text = header.content.controls[0].controls[0].value
    assert title_text == "Configurações"

    # Check cards
    body = view.content.controls[1]
    scroll_column = body.content
    cards_row = scroll_column.controls[0]
    assert len(cards_row.controls) == 3

    # Theme card
    theme_card = cards_row.controls[0].content
    theme_content = theme_card.content.controls[2]
    options_row = theme_content.controls[0]
    assert len(options_row.controls) == 3

    # Click dark theme option
    dark_option = options_row.controls[1]
    dark_option.on_click(None)
    assert theme_calls == ["dark"]

    # Scale card
    scale_card = cards_row.controls[1].content
    scale_content = scale_card.content.controls[2]
    auto_row = scale_content.controls[0]
    switch = auto_row.controls[1]
    switch.on_change(SimpleNamespace(control=SimpleNamespace(value=False)))
    assert auto_scale_calls == [False]

    slider = scale_content.controls[3]
    slider.on_change_end(SimpleNamespace(control=SimpleNamespace(value=1.20)))
    assert scale_calls == [1.20]

    # Preview & Reset card
    preview_card = cards_row.controls[2].content
    preview_content = preview_card.content.controls[2]
    reset_button = preview_content.controls[2]
    reset_button.on_click(None)
    assert reset_calls == [True]


def test_core_controller_settings_integration(tmp_path):
    storage_path = tmp_path / "user_preferences.json"
    dummy_page = SimpleNamespace(
        width=1400,
        height=900,
        platform_brightness=ft.Brightness.LIGHT,
        theme_mode=ft.ThemeMode.LIGHT,
        on_resize=None,
        on_platform_brightness_change=None,
        controls=[],
        clean=lambda: dummy_page.controls.clear(),
        add=lambda ctrl: dummy_page.controls.append(ctrl),
        update=lambda: None,
        show_dialog=lambda _: None,
        window=SimpleNamespace(
            width=1400,
            height=900,
            resizable=True,
            frameless=True,
            title_bar_hidden=True,
            title_bar_buttons_hidden=True,
            maximizable=True,
            minimizable=True,
            prevent_close=False,
            icon=None,
        ),
    )

    settings_service = SettingsService(storage_path)
    controller = CoreController(
        page=dummy_page, dark_theme=False, settings_service=settings_service
    )
    controller.build_application()

    # Verify initial state
    assert controller.settings.theme_mode == "light"
    assert controller.view_config.colors == COLORS_LIGHT
    assert controller.settings.auto_scale is True

    # Test change theme to dark
    controller.change_theme("dark")
    assert controller.settings.theme_mode == "dark"
    assert controller.view_config.colors == COLORS_DARK
    assert dummy_page.theme_mode == ft.ThemeMode.DARK

    # Test change auto_scale
    controller.toggle_auto_scale(False)
    assert controller.settings.auto_scale is False

    # Test change manual scale
    controller.change_scale(1.25)
    assert controller.settings.manual_scale == 1.25
    assert controller.scale == 1.25

    # Test reset settings
    controller.reset_settings()
    assert controller.settings.theme_mode == "light"
    assert controller.view_config.colors == COLORS_LIGHT
    assert controller.settings.auto_scale is True
    assert controller.settings.manual_scale == 1.0

    # Test navigate to Configurações
    controller.navigate("Configurações")
    assert controller.current_destination == "Configurações"

    # Test maximização sem distorção quando auto_scale=False
    controller.settings.auto_scale = False
    controller.settings.manual_scale = 1.0
    dummy_page.width = 1920
    dummy_page.height = 1080
    controller.toggle_maximize()
    assert dummy_page.window.maximized is True
    # Sem auto_scale, a escala permanece rigorosamente 1.0 sem distorções
    assert controller.scale == 1.0

    # Desmaximizar retorna para o tamanho normal mantendo escala fixa
    dummy_page.width = 1400
    dummy_page.height = 900
    controller.toggle_maximize()
    assert dummy_page.window.maximized is False
    assert controller.scale == 1.0


def test_window_events_trigger_native_readjustment(tmp_path):
    storage_path = tmp_path / "user_preferences.json"
    dummy_page = SimpleNamespace(
        width=1920,
        height=1080,
        platform_brightness=ft.Brightness.LIGHT,
        theme_mode=ft.ThemeMode.LIGHT,
        on_resize=None,
        on_platform_brightness_change=None,
        controls=[],
        clean=lambda: dummy_page.controls.clear(),
        add=lambda ctrl: dummy_page.controls.append(ctrl),
        update=lambda: None,
        show_dialog=lambda _: None,
        window=SimpleNamespace(
            width=1400,
            height=900,
            maximized=False,
            on_event=None,
        ),
    )

    settings_service = SettingsService(storage_path)
    controller = CoreController(
        page=dummy_page, dark_theme=False, settings_service=settings_service
    )
    controller.build_application()
    controller.configure_page()

    # O ouvinte de eventos de janela deve ser conectado
    assert dummy_page.window.on_event == controller.handle_window_event

    controller.settings.auto_scale = False
    controller.settings.manual_scale = 1.0

    # Simular evento nativo de maximizar com auto_scale desligado: escala permanece fixa
    dummy_page.window.maximized = True
    controller.handle_window_event(SimpleNamespace(data="maximize"))
    assert controller.scale == 1.0

    # Simular evento nativo de restauração
    dummy_page.width = 1400
    dummy_page.height = 900
    dummy_page.window.maximized = False
    controller.handle_window_event(SimpleNamespace(data="restore"))
    assert controller.scale == 1.0

    # Agora simular evento nativo com auto_scale ativado:
    controller.settings.auto_scale = True
    dummy_page.width = 1920
    dummy_page.height = 1080
    dummy_page.window.maximized = True
    controller.handle_window_event(SimpleNamespace(data="maximize"))
    assert controller.scale == 1.50


def test_title_bar_icon_switches_on_maximize(test_config):
    # Quando em modo janela, o ícone deve ser CROP_SQUARE
    page_windowed = SimpleNamespace(
        window=SimpleNamespace(maximized=False),
        update=lambda: None,
    )
    composer_windowed = CoreComposer(
        page=page_windowed,
        scale=1.0,
        config=test_config,
        on_navigate=lambda _: None,
        on_work_click=lambda _: None,
        on_edit_work=lambda _: None,
        on_format_reference=lambda _: None,
        on_copy_reference=lambda _: None,
        on_delete_work=lambda _: None,
        on_create_parent_work=lambda _: None,
        on_fragment_save=lambda *_: True,
        on_fragment_delete=lambda _: None,
        search_fragment_works=lambda _: [],
        search_compilation_works=lambda _: [],
        refresh_compilations=lambda: [],
        on_compilation_create=lambda _: 1,
        on_compilation_update=lambda *_: True,
        on_compilation_delete=lambda _: True,
        on_compilation_add_work=lambda *_: True,
        on_compilation_remove_work=lambda *_: True,
        on_compilation_reorder_works=lambda *_: True,
        on_compilation_fragment_membership=lambda *_: True,
        on_compilation_fragment_note=lambda *_: True,
        on_compilation_section_create=lambda *_: 1,
        on_compilation_section_update=lambda *_: True,
        on_compilation_section_delete=lambda *_: True,
        on_compilation_section_reorder=lambda *_: True,
        on_compilation_fragment_assign_section=lambda *_: True,
        on_compilation_section_reorder_fragments=lambda *_: True,
        on_compilation_copy_caderno=lambda _: None,
        on_compilation_create_work=lambda _: None,
        on_compilation_edit_work=lambda *_: None,
        on_compilation_create_fragment=lambda *_: None,
        on_compilation_edit_fragment=lambda *_: None,
    )
    title_bar = composer_windowed._compose_custom_title_bar()
    toolbar_row = title_bar.content.content.controls[1]
    maximize_btn = toolbar_row.controls[1]
    assert maximize_btn.icon == ft.Icons.CROP_SQUARE
    assert maximize_btn.tooltip == "Maximizar"

    # Quando maximizado, o ícone deve ser FILTER_NONE
    page_maximized = SimpleNamespace(
        window=SimpleNamespace(maximized=True),
        update=lambda: None,
    )
    composer_maximized = CoreComposer(
        page=page_maximized,
        scale=1.0,
        config=test_config,
        on_navigate=lambda _: None,
        on_work_click=lambda _: None,
        on_edit_work=lambda _: None,
        on_format_reference=lambda _: None,
        on_copy_reference=lambda _: None,
        on_delete_work=lambda _: None,
        on_create_parent_work=lambda _: None,
        on_fragment_save=lambda *_: True,
        on_fragment_delete=lambda _: None,
        search_fragment_works=lambda _: [],
        search_compilation_works=lambda _: [],
        refresh_compilations=lambda: [],
        on_compilation_create=lambda _: 1,
        on_compilation_update=lambda *_: True,
        on_compilation_delete=lambda _: True,
        on_compilation_add_work=lambda *_: True,
        on_compilation_remove_work=lambda *_: True,
        on_compilation_reorder_works=lambda *_: True,
        on_compilation_fragment_membership=lambda *_: True,
        on_compilation_fragment_note=lambda *_: True,
        on_compilation_section_create=lambda *_: 1,
        on_compilation_section_update=lambda *_: True,
        on_compilation_section_delete=lambda *_: True,
        on_compilation_section_reorder=lambda *_: True,
        on_compilation_fragment_assign_section=lambda *_: True,
        on_compilation_section_reorder_fragments=lambda *_: True,
        on_compilation_copy_caderno=lambda _: None,
        on_compilation_create_work=lambda _: None,
        on_compilation_edit_work=lambda *_: None,
        on_compilation_create_fragment=lambda *_: None,
        on_compilation_edit_fragment=lambda *_: None,
    )
    title_bar_max = composer_maximized._compose_custom_title_bar()
    toolbar_row_max = title_bar_max.content.content.controls[1]
    restore_btn = toolbar_row_max.controls[1]
    assert restore_btn.icon == ft.Icons.FILTER_NONE
    assert restore_btn.tooltip == "Restaurar"

    # Testar update_window_state dinâmico sem reconstruir a barra
    composer_windowed.update_window_state(True)
    assert composer_windowed.maximize_button.icon == ft.Icons.FILTER_NONE
    assert composer_windowed.maximize_button.tooltip == "Restaurar"

    composer_windowed.update_window_state(False)
    assert composer_windowed.maximize_button.icon == ft.Icons.CROP_SQUARE
    assert composer_windowed.maximize_button.tooltip == "Maximizar"

