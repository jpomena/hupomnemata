"""Cofre de segredos do Hupomnemata.

Prioriza o cofre do sistema operacional via ``keyring`` (Windows Credential
Manager, macOS Keychain, Secret Service no Linux). Quando o backend não está
disponível — CI headless, ambiente sem D-Bus, testes —, recorre a um arquivo
JSON local com permissões restritas.

Nunca grava segredos em ``user_preferences.json``: esse arquivo é legível e
versionável por acidente. Chaves legadas encontradas nele são migradas e
apagadas automaticamente em ``SettingsService.load_settings``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Protocol

from src.configs.paths import resolve_secrets_path

logger = logging.getLogger('hupomnemata.secrets')

SERVICE_NAME = 'hupomnemata'


class SecretBackend(Protocol):
    """Contrato mínimo de um backend de segredos."""

    label: str

    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> bool: ...

    def delete(self, name: str) -> bool: ...


class KeyringBackend:
    """Backend do cofre nativo do sistema operacional."""

    label = 'keyring'

    def __init__(self, keyring_module=None) -> None:
        if keyring_module is None:
            import keyring as keyring_module  # type: ignore
        self._keyring = keyring_module

    def get(self, name: str) -> str | None:
        return self._keyring.get_password(SERVICE_NAME, name)

    def set(self, name: str, value: str) -> bool:
        self._keyring.set_password(SERVICE_NAME, name, value)
        return True

    def delete(self, name: str) -> bool:
        try:
            self._keyring.delete_password(SERVICE_NAME, name)
        except Exception:  # noqa: BLE001 - senha ausente é resultado normal
            return False
        return True


class FileBackend:
    """Backend de contingência: JSON local com escrita atômica e 0600."""

    label = 'file'

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return {
                str(key): str(value)
                for key, value in data.items()
                if isinstance(value, str)
            }
        except (OSError, ValueError) as error:
            logger.warning('Falha ao ler cofre local %s: %s', self.path, error)
            return {}

    def _write(self, data: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + '.tmp')
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass  # Windows: ACL do perfil do usuário já é restritiva
        temporary.replace(self.path)

    def get(self, name: str) -> str | None:
        return self._read().get(name)

    def set(self, name: str, value: str) -> bool:
        data = self._read()
        data[name] = value
        self._write(data)
        return True

    def delete(self, name: str) -> bool:
        data = self._read()
        if name not in data:
            return False
        del data[name]
        self._write(data)
        return True


class SecretStore:
    """Fachada resiliente: tenta o keyring e cai para arquivo sem quebrar."""

    def __init__(
        self,
        fallback_path: Path | None = None,
        backend: SecretBackend | None = None,
    ) -> None:
        self.fallback_path = Path(fallback_path or resolve_secrets_path())
        self._file = FileBackend(self.fallback_path)
        self._backend = backend if backend is not None else self._detect_backend()
        self._warned = False

    @staticmethod
    def _detect_backend() -> SecretBackend | None:
        try:
            backend = KeyringBackend()
            # Um backend "fail"/"null" não deve ser tratado como cofre real.
            if 'fail' in backend._keyring.get_keyring().__class__.__name__.lower():
                return None
            return backend
        except Exception as error:  # noqa: BLE001 - ausência de keyring é esperada
            logger.info('keyring indisponível (%s); usando cofre local.', error)
            return None

    @property
    def backend_label(self) -> str:
        return self._backend.label if self._backend is not None else self._file.label

    def get_secret(self, name: str) -> str | None:
        if self._backend is not None:
            try:
                value = self._backend.get(name)
                if value:
                    return value
            except Exception as error:  # noqa: BLE001
                self._warn_once(error)
        return self._file.get(name)

    def set_secret(self, name: str, value: str) -> bool:
        if self._backend is not None:
            try:
                if self._backend.set(name, value):
                    # Só remove a cópia local quando o cofre é externo: se o
                    # backend É o próprio arquivo, apagar destruiria o segredo.
                    if self._backend.label != self._file.label:
                        self._file.delete(name)
                    return True
            except Exception as error:  # noqa: BLE001
                self._warn_once(error)
        return self._file.set(name, value)

    def delete_secret(self, name: str) -> bool:
        removed = False
        if self._backend is not None:
            try:
                removed = self._backend.delete(name)
            except Exception as error:  # noqa: BLE001
                self._warn_once(error)
        return self._file.delete(name) or removed

    def _warn_once(self, error: Exception) -> None:
        if not self._warned:
            logger.warning(
                'Cofre do sistema indisponível (%s); usando fallback local.',
                error,
            )
            self._warned = True
