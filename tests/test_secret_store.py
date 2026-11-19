"""Regressões do cofre de segredos (keyring + fallback local)."""

import json
from pathlib import Path

from src.services.secret_store import (
    FileBackend,
    SecretStore,
)
from src.services.settings_service import AppearanceSettings, SettingsService


class FakeBackend:
    label = 'fake'

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.fail = False

    def get(self, name: str) -> str | None:
        if self.fail:
            raise RuntimeError('backend indisponível')
        return self.data.get(name)

    def set(self, name: str, value: str) -> bool:
        if self.fail:
            raise RuntimeError('backend indisponível')
        self.data[name] = value
        return True

    def delete(self, name: str) -> bool:
        return self.data.pop(name, None) is not None


def test_file_backend_roundtrip(tmp_path: Path):
    backend = FileBackend(tmp_path / 'secrets.json')
    assert backend.set('alpha', 'segredo') is True
    assert backend.get('alpha') == 'segredo'
    assert backend.delete('alpha') is True
    assert backend.get('alpha') is None


def test_secret_store_prefers_external_backend(tmp_path: Path):
    backend = FakeBackend()
    store = SecretStore(fallback_path=tmp_path / 'secrets.json', backend=backend)

    assert store.set_secret('gemini_api_key', 'AIzaSyExterno') is True
    assert store.get_secret('gemini_api_key') == 'AIzaSyExterno'
    assert backend.data['gemini_api_key'] == 'AIzaSyExterno'
    assert not (tmp_path / 'secrets.json').exists()


def test_secret_store_falls_back_when_backend_fails(tmp_path: Path):
    backend = FakeBackend()
    backend.fail = True
    store = SecretStore(fallback_path=tmp_path / 'secrets.json', backend=backend)

    assert store.set_secret('gemini_api_key', 'AIzaSyFallback') is True
    assert store.get_secret('gemini_api_key') == 'AIzaSyFallback'
    assert json.loads(
        (tmp_path / 'secrets.json').read_text(encoding='utf-8')
    )['gemini_api_key'] == 'AIzaSyFallback'


def test_legacy_key_is_migrated_out_of_preferences(tmp_path: Path):
    storage = tmp_path / 'user_preferences.json'
    storage.write_text(
        json.dumps(
            {
                'theme_mode': 'dark',
                'gemini_api_key': 'AIzaSyLegado',
            }
        ),
        encoding='utf-8',
    )

    service = SettingsService(storage_path=storage)
    loaded = service.load_settings()

    assert loaded.gemini_api_key == 'AIzaSyLegado'
    assert service.get_api_key() == 'AIzaSyLegado'

    persisted = json.loads(storage.read_text(encoding='utf-8'))
    assert persisted['gemini_api_key'] == ''
    assert persisted['theme_mode'] == 'dark'
    assert json.loads(
        (tmp_path / 'secrets.json').read_text(encoding='utf-8')
    )['gemini_api_key'] == 'AIzaSyLegado'


def test_save_settings_never_persists_key_in_plain_json(tmp_path: Path):
    storage = tmp_path / 'user_preferences.json'
    service = SettingsService(storage_path=storage)

    assert service.save_settings(
        AppearanceSettings(gemini_api_key='AIzaSyNova')
    ) is True

    persisted = json.loads(storage.read_text(encoding='utf-8'))
    assert persisted['gemini_api_key'] == ''
    assert service.get_api_key() == 'AIzaSyNova'


def test_delete_api_key_removes_from_store(tmp_path: Path):
    service = SettingsService(storage_path=tmp_path / 'prefs.json')
    service.set_api_key('AIzaSyTemporaria')
    assert service.get_api_key() == 'AIzaSyTemporaria'

    assert service.delete_api_key() is True
    assert service.get_api_key() == ''
