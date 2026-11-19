"""Serviço de gerenciamento das configurações de aparência e preferências do usuário."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import flet as ft

from src.configs.settings import CONFIG_DIR
from src.services.secret_store import FileBackend, SecretStore
from src.utils.error_log import log_exception
from src.utils.ft_responsiveness import Responsive


@dataclass
class AppearanceSettings:
    """Modelo de dados das preferências de aparência."""

    theme_mode: str = "light"  # "dark", "light", "system"
    auto_scale: bool = True
    manual_scale: float = 1.0  # de 0.80 a 1.40
    gemini_api_key: str = ""
    cloud_sync_enabled: bool = False
    sync_pdfs: bool = False
    last_sync_utc: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Converte as configurações para dicionário."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppearanceSettings":
        """Instancia configurações a partir de um dicionário com validação de limites."""
        theme_mode = data.get("theme_mode", "light")
        if theme_mode not in {"dark", "light", "system"}:
            theme_mode = "light"

        auto_scale = bool(data.get("auto_scale", True))

        try:
            manual_scale = float(data.get("manual_scale", 1.0))
            manual_scale = round(max(0.80, min(1.40, manual_scale)), 2)
        except (ValueError, TypeError):
            manual_scale = 1.0

        gemini_api_key = str(data.get("gemini_api_key", "") or "").strip()
        cloud_sync_enabled = bool(data.get("cloud_sync_enabled", False))
        sync_pdfs = bool(data.get("sync_pdfs", False))
        last_sync_utc = str(data.get("last_sync_utc", "") or "").strip()

        return cls(
            theme_mode=theme_mode,
            auto_scale=auto_scale,
            manual_scale=manual_scale,
            gemini_api_key=gemini_api_key,
            cloud_sync_enabled=cloud_sync_enabled,
            sync_pdfs=sync_pdfs,
            last_sync_utc=last_sync_utc,
        )


def resolve_effective_theme(
    theme_mode: str, page: ft.Page | None = None
) -> str:
    """Retorna 'dark' ou 'light' com base na escolha do usuário e sistema."""
    if theme_mode in {"dark", "light"}:
        return theme_mode

    # Modo 'system': tenta inferir o tema a partir do brilho do sistema
    if page is not None and hasattr(page, "platform_brightness"):
        brightness = getattr(page, "platform_brightness", None)
        if brightness is not None:
            # ft.Brightness.DARK ou string "dark"
            if str(brightness).lower() in {"dark", "brightness.dark"}:
                return "dark"
            return "light"

    return "light"


BASE_WINDOW_SCALE = 1.09375


def resolve_effective_scale(
    settings: AppearanceSettings,
    page: ft.Page | None = None,
    is_maximized: bool | None = None,
) -> float:
    """Calcula a escala proporcional a ser aplicada aos componentes."""
    if settings.auto_scale and page is not None:
        raw_scale = Responsive.get_scale(page)
        # Limita a escala entre 0.75 e 1.50 para preservar usabilidade
        return round(max(0.75, min(1.50, raw_scale)), 2)

    return round(settings.manual_scale, 2)


class SettingsService:
    """Persistência e recuperação das preferências visuais do usuário."""

    def __init__(
        self,
        storage_path: Path | None = None,
        secret_store: 'SecretStore | None' = None,
    ) -> None:
        self.storage_path = (
            storage_path
            if storage_path is not None
            else (CONFIG_DIR / "user_preferences.json")
        )
        if secret_store is not None:
            self.secret_store = secret_store
        elif storage_path is not None:
            # Configuração/personalizada (testes, instâncias isoladas): usa um
            # cofre de arquivo irmão e nunca toca no keyring do sistema.
            fallback = self.storage_path.parent / "secrets.json"
            self.secret_store = SecretStore(
                fallback_path=fallback,
                backend=FileBackend(fallback),
            )
        else:
            self.secret_store = SecretStore()

    # ── segredos (BYOK) ────────────────────────────────────────

    def get_api_key(self) -> str:
        """Lê a chave Gemini do cofre (keyring ou fallback local)."""
        return self.secret_store.get_secret('gemini_api_key') or ""

    def set_api_key(self, api_key: str) -> bool:
        """Persiste a chave Gemini no cofre do sistema."""
        cleaned = (api_key or "").strip()
        if not cleaned:
            return self.secret_store.delete_secret('gemini_api_key')
        return self.secret_store.set_secret('gemini_api_key', cleaned)

    def delete_api_key(self) -> bool:
        """Remove a chave Gemini do cofre."""
        return self.secret_store.delete_secret('gemini_api_key')

    # ── preferências ───────────────────────────────────────────

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

    def load_settings(self) -> AppearanceSettings:
        """Carrega configurações persistidas ou retorna o padrão."""
        if not self.storage_path.exists():
            settings = AppearanceSettings()
            settings.gemini_api_key = self.get_api_key()
            return settings
        try:
            with open(self.storage_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            settings = AppearanceSettings.from_dict(data)

            legacy_key = settings.gemini_api_key.strip()
            if legacy_key:
                # Migração: chave antiga em texto puro sai do JSON.
                self.set_api_key(legacy_key)
                payload = settings.to_dict()
                payload['gemini_api_key'] = ''
                self._write_payload(payload)

            settings.gemini_api_key = self.get_api_key()
            return settings
        except Exception as error:
            log_exception("Falha ao carregar configurações de aparência", error)
            return AppearanceSettings()

    def save_settings(self, settings: AppearanceSettings) -> bool:
        """Persiste as preferências, roteando a chave para o cofre."""
        try:
            if settings.gemini_api_key.strip():
                self.set_api_key(settings.gemini_api_key)
            payload = settings.to_dict()
            payload['gemini_api_key'] = ''
            self._write_payload(payload)
            return True
        except Exception as error:
            log_exception("Falha ao persistir configurações de aparência", error)
            return False

    def reset_to_defaults(self) -> AppearanceSettings:
        """Restaura e persiste as preferências padrão de fábrica."""
        defaults = AppearanceSettings()
        self.save_settings(defaults)
        return defaults
