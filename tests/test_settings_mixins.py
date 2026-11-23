"""Testes do fatiamento de ``SettingsComposer`` em mixins."""

import flet as ft

from src.views.settings import SettingsComposer
from src.views.settings_cloud import SettingsCloudMixin
from src.views.settings_database import SettingsDatabaseMixin
from src.views.settings_preview import SettingsPreviewMixin
from src.views.settings_scale import SettingsScaleMixin
from src.views.settings_theme import SettingsThemeMixin


class _OfflineSync:
    """Dublê mínimo para não tocar em credenciais nem rede."""

    def is_authenticated(self) -> bool:
        return False


def _composer(config) -> SettingsComposer:
    return SettingsComposer(
        scale=1.0,
        config=config,
        current_theme_mode="light",
        auto_scale=True,
        manual_scale=1.0,
        effective_scale=1.0,
        on_navigate=lambda _: None,
        on_change_theme=lambda _: None,
        on_toggle_auto_scale=lambda _: None,
        on_change_scale=lambda _: None,
        on_reset_settings=lambda: None,
        cloud_sync_service=_OfflineSync(),
    )


def test_settings_mro_contains_the_five_mixins():
    assert SettingsComposer.__mro__[1:6] == (
        SettingsThemeMixin,
        SettingsScaleMixin,
        SettingsPreviewMixin,
        SettingsCloudMixin,
        SettingsDatabaseMixin,
    )


def test_card_methods_live_in_their_mixins():
    assert "_compose_theme_option" in SettingsThemeMixin.__dict__
    assert "_compose_theme_card" in SettingsThemeMixin.__dict__
    assert "_compose_scale_card" in SettingsScaleMixin.__dict__
    assert "_compose_preview_card" in SettingsPreviewMixin.__dict__
    assert "_palette_chip" in SettingsPreviewMixin.__dict__
    assert "_format_relative_time" in SettingsCloudMixin.__dict__
    assert "_show_conflict_modal" in SettingsCloudMixin.__dict__
    assert "_compose_cloud_sync_card" in SettingsCloudMixin.__dict__
    assert "_compose_database_card" in SettingsDatabaseMixin.__dict__
    assert "_open_delete_databases_dialog" in SettingsDatabaseMixin.__dict__


def test_shared_shell_methods_stay_in_facade():
    for name in (
        "__init__",
        "_compose_header",
        "_compose_card_container",
        "_compose_cards",
        "compose",
    ):
        assert name in SettingsComposer.__dict__


def test_no_method_is_defined_twice_in_the_mro():
    owners: dict[str, list[str]] = {}
    for klass in SettingsComposer.__mro__:
        for name, value in vars(klass).items():
            if name.startswith("__") or not callable(value):
                continue
            owners.setdefault(name, []).append(klass.__name__)
    duplicated = {name: klasses for name, klasses in owners.items() if len(klasses) > 1}

    assert duplicated == {}


def test_mixins_have_no_initializer():
    for mixin in (
        SettingsThemeMixin,
        SettingsScaleMixin,
        SettingsPreviewMixin,
        SettingsCloudMixin,
        SettingsDatabaseMixin,
    ):
        assert "__init__" not in mixin.__dict__


def test_composition_still_builds_five_cards(view_config):
    view = _composer(view_config).compose()

    assert isinstance(view, ft.Container)
    cards_row = view.content.controls[1].content.controls[0]
    assert isinstance(cards_row, ft.ResponsiveRow)
    assert len(cards_row.controls) == 5
    assert view.content.controls[0].content.controls[0].controls[0].value == (
        "Configurações"
    )
