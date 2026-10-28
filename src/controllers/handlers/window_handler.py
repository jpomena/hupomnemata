"""Handler para eventos de janela, temas e responsividade de escala."""

from dataclasses import replace
import flet as ft

from src.configs.settings import COLORS_DARK, COLORS_LIGHT
from src.services import resolve_effective_scale, resolve_effective_theme


class WindowControllerMixin:
    """Gerencia preferências visuais, alternância de tema, escala e controle da janela."""

    def change_theme(self, theme_mode: str) -> None:
        self.settings.theme_mode = theme_mode
        self.settings_service.save_settings(self.settings)
        effective_theme = resolve_effective_theme(theme_mode, self.page)
        self.view_config = replace(
            self.view_config,
            colors=COLORS_DARK if effective_theme == "dark" else COLORS_LIGHT,
        )
        if hasattr(self.page, "theme_mode"):
            self.page.theme_mode = (
                ft.ThemeMode.DARK
                if effective_theme == "dark"
                else ft.ThemeMode.LIGHT
            )
        self.rebuild_ui()
        self.show_message("Tema atualizado.", self.view_config.colors["gold"])

    def toggle_auto_scale(self, enabled: bool) -> None:
        self.settings.auto_scale = enabled
        self.scale = resolve_effective_scale(self.settings, self.page)
        self.settings_service.save_settings(self.settings)
        self.rebuild_ui()
        message = (
            "Escala automática ativada."
            if enabled
            else "Escala manual ativada."
        )
        self.show_message(message, self.view_config.colors["gold"])

    def change_scale(self, scale_val: float) -> None:
        self.settings.manual_scale = round(scale_val, 2)
        if not self.settings.auto_scale:
            self.scale = self.settings.manual_scale
        self.settings_service.save_settings(self.settings)
        self.rebuild_ui()

    def reset_settings(self) -> None:
        self.settings = self.settings_service.reset_to_defaults()
        effective_theme = resolve_effective_theme(
            self.settings.theme_mode, self.page
        )
        self.view_config = replace(
            self.view_config,
            colors=COLORS_DARK if effective_theme == "dark" else COLORS_LIGHT,
        )
        self.scale = resolve_effective_scale(self.settings, self.page)
        if hasattr(self.page, "theme_mode"):
            self.page.theme_mode = (
                ft.ThemeMode.DARK
                if effective_theme == "dark"
                else ft.ThemeMode.LIGHT
            )
        self.rebuild_ui()
        self.show_message(
            "Configurações restauradas para os padrões originais.",
            self.view_config.colors["gold"],
        )

    def toggle_maximize(self) -> None:
        window = getattr(self.page, "window", None)
        if window is not None:
            target_max = not bool(getattr(window, "maximized", False))
            window.maximized = target_max
            self._last_maximized_state = target_max
            if hasattr(self.page, "update"):
                self.page.update()

            if hasattr(self, "application") and self.application is not None:
                if hasattr(self.application, "update_window_state"):
                    self.application.update_window_state(target_max)
                if getattr(self, "current_destination", "") == "Estruturas de Saber":
                    knowledge_comp = getattr(self.application, "knowledge_composer", None)
                    if knowledge_comp is not None:
                        knowledge_comp.on_window_resized()

            new_scale = resolve_effective_scale(
                self.settings, self.page, is_maximized=target_max
            )
            if self.settings.auto_scale:
                if abs(new_scale - self.scale) >= 0.05:
                    self.scale = new_scale
                    self.rebuild_ui()
            else:
                self.scale = new_scale

    def handle_window_event(self, event) -> None:
        raw_type = getattr(event, "type", None)
        type_str = getattr(raw_type, "value", str(raw_type) if raw_type is not None else "")
        data_str = str(getattr(event, "data", "") or "")
        event_str = f"{type_str} {data_str}".lower()

        if any(k in event_str for k in ("maximize", "unmaximize", "restore")):
            is_max = "unmaximize" not in event_str and ("maximize" in event_str)
            self._last_maximized_state = is_max
            if hasattr(self, "application") and self.application is not None:
                if hasattr(self.application, "update_window_state"):
                    self.application.update_window_state(is_max)
                if getattr(self, "current_destination", "") == "Estruturas de Saber":
                    knowledge_comp = getattr(self.application, "knowledge_composer", None)
                    if knowledge_comp is not None:
                        knowledge_comp.on_window_resized()

            new_scale = resolve_effective_scale(
                self.settings, self.page, is_maximized=is_max
            )
            if self.settings.auto_scale:
                if abs(new_scale - self.scale) >= 0.05:
                    self.scale = new_scale
                    self.rebuild_ui()
            else:
                self.scale = new_scale
        elif any(k in event_str for k in ("resize", "resized")):
            self.handle_window_resize(event)

    def handle_window_resize(self, event=None) -> None:
        if event is not None:
            w = getattr(event, "width", None)
            h = getattr(event, "height", None)
            if w and float(w) > 200:
                self.page.width = float(w)
            if h and float(h) > 200:
                self.page.height = float(h)

        current_maximized = bool(
            getattr(getattr(self.page, "window", None), "maximized", False)
        )
        maximized_changed = current_maximized != getattr(
            self, "_last_maximized_state", False
        )
        if maximized_changed:
            self._last_maximized_state = current_maximized
            if hasattr(self, "application") and self.application is not None:
                if hasattr(self.application, "update_window_state"):
                    self.application.update_window_state(current_maximized)

        # Se estamos no dashboard de Estruturas de Saber, ajusta elasticamente sem alterar o scale global do aplicativo
        if getattr(self, "current_destination", "") == "Estruturas de Saber":
            if hasattr(self, "application") and self.application is not None:
                knowledge_comp = getattr(self.application, "knowledge_composer", None)
                if knowledge_comp is not None:
                    knowledge_comp.on_window_resized()
            return

        new_scale = resolve_effective_scale(
            self.settings, self.page, is_maximized=current_maximized
        )
        if self.settings.auto_scale:
            if abs(new_scale - self.scale) >= 0.05:
                self.scale = new_scale
                self.rebuild_ui()
        else:
            self.scale = new_scale

    def handle_brightness_change(self, event=None) -> None:
        del event
        if self.settings.theme_mode != "system":
            return
        new_theme = resolve_effective_theme("system", self.page)
        current_is_dark = self.view_config.colors == COLORS_DARK
        if (new_theme == "dark") != current_is_dark:
            self.view_config = replace(
                self.view_config,
                colors=COLORS_DARK if new_theme == "dark" else COLORS_LIGHT,
            )
            if hasattr(self.page, "theme_mode"):
                self.page.theme_mode = (
                    ft.ThemeMode.DARK
                    if new_theme == "dark"
                    else ft.ThemeMode.LIGHT
                )
            self.rebuild_ui()
