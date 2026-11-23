"""SettingsCloudMixin extraído de ``settings.py``.

Movimentação literal: métodos sem ``__init__``, colaborando com
``SettingsComposer`` via ``self``.
"""

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any

import flet as ft

from src.services.cloud_sync_service import SyncStatus
from src.utils.ui_thread import run_on_ui
from src.views import ui_kit as ui
from src.utils.control_safety import safe_update


class SettingsCloudMixin:
    """Card de sincronização em nuvem e resolução de conflitos."""

    def _format_relative_time(self, iso_str: str | None) -> str:
        """Formata timestamp UTC da nuvem em tempo relativo amigável."""
        if not iso_str:
            return "recentemente"
        try:
            clean_iso = iso_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - dt
            seconds = int(delta.total_seconds())
            if seconds < 0:
                return "recentemente"
            if seconds < 60:
                return "há poucos segundos"
            minutes = seconds // 60
            if minutes < 60:
                return f"há {minutes} minuto{'s' if minutes > 1 else ''}"
            hours = minutes // 60
            if hours < 24:
                return f"há {hours} hora{'s' if hours > 1 else ''}"
            days = hours // 24
            if days <= 7:
                return f"há {days} dia{'s' if days > 1 else ''}"
            return f"em {dt.astimezone().strftime('%Y-%m-%d %H:%M')}"
        except Exception:
            return "recentemente"

    def _show_conflict_modal(
        self,
        res: Any,
        status_text: ft.Text,
        feedback_banner: ft.Container,
    ) -> None:
        """Apresenta diálogo modal canônico para resolução de conflito de sincronização."""
        page = self.page or getattr(status_text, "page", None)
        if not page:
            return

        c = self.config
        remote_manifest = (
            res.details.get("remote_manifest", {})
            if hasattr(res, "details") and isinstance(res.details, dict)
            else {}
        )
        timestamp_utc = remote_manifest.get("timestamp_utc")
        rel_time = self._format_relative_time(timestamp_utc)

        explanatory_text = (
            f"A nuvem possui alterações gravadas {rel_time} por outra estação, "
            "enquanto esta máquina também possui alterações locais não sincronizadas."
        )
        remote_counts = remote_manifest.get("counts")
        if isinstance(remote_counts, dict):
            explanatory_text += (
                f" Nuvem: {remote_counts.get('resources', 0)} obras, "
                f"{remote_counts.get('fragments', 0)} fragmentos, "
                f"{remote_counts.get('compilations', 0)} compilações."
            )
        reassurance_text = "Uma cópia fria de segurança da base local foi preservada em disco."

        modal_ref: list[ft.AlertDialog | None] = [None]

        def safe_ui_update(ctrl: ft.Control | None = None) -> None:
            def _apply() -> None:
                if ctrl is not None and safe_update(ctrl):
                    return
                if page is not None:
                    safe_update(page)

            run_on_ui(page, _apply)

        def close_modal():
            ui.close_dialog(page)
            if modal_ref[0] is not None:
                modal_ref[0].open = False
            safe_ui_update()

        def resolve_conflict(force_pull: bool = False, force_push: bool = False):
            close_modal()
            direction_desc = (
                "Baixando e aplicando alterações da nuvem..."
                if force_pull
                else "Enviando alterações locais para a nuvem..."
            )
            status_text.value = direction_desc
            status_text.color = c.colors["gold"]
            feedback_banner.visible = True
            feedback_banner.content = ft.ProgressBar(
                color=c.colors["gold"],
                bgcolor=c.colors["surface"],
            )
            safe_ui_update(status_text)
            safe_ui_update(feedback_banner)

            def run_resolution():
                try:
                    res_resolve = self.cloud_sync_service.sync(
                        force_pull=force_pull,
                        force_push=force_push,
                        sync_pdfs=True,
                    )
                    if res_resolve.status == SyncStatus.SUCCESS:
                        status_text.value = f"Sincronizado: {res_resolve.message}"
                        status_text.color = c.colors["gold"]
                        feedback_banner.visible = False
                        safe_ui_update(status_text)
                        safe_ui_update(feedback_banner)
                        if self.on_navigate:
                            self.on_navigate("settings")
                    else:
                        status_text.value = f"Erro ao resolver conflito: {res_resolve.message}"
                        status_text.color = c.colors["danger"]
                        feedback_banner.visible = False
                        safe_ui_update(status_text)
                        safe_ui_update(feedback_banner)
                except Exception as err:
                    status_text.value = f"Erro na resolução: {err}"
                    status_text.color = c.colors["danger"]
                    feedback_banner.visible = False
                    safe_ui_update(status_text)
                    safe_ui_update(feedback_banner)

            run_task = getattr(page, "run_task", None) if page is not None else None
            if run_task is not None:
                async def _async_resolution():
                    await asyncio.to_thread(run_resolution)
                run_task(_async_resolution)
            else:
                threading.Thread(target=run_resolution, daemon=True).start()

        content_controls: list[ft.Control] = [
            ui.ui_text(
                c,
                explanatory_text,
                size=13,
                color=c.colors["text"],
                max_lines=None,
            ),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ui.icon(c, "shield-halved", size=13, color=c.colors["gold"]),
                        ui.ui_text(
                            c,
                            reassurance_text,
                            size=12,
                            color=c.colors["muted"],
                            max_lines=None,
                            expand=True,
                        ),
                    ],
                    spacing=ui.s(8),
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                padding=ft.Padding.symmetric(vertical=ui.s(4)),
            ),
        ]

        if getattr(res, "conflict_backup_path", None):
            backup_file_name = str(res.conflict_backup_path).replace("\\", "/").split("/")[-1]
            content_controls.append(
                ui.meta_text(c, f"Cópia de segurança preservada: {backup_file_name}", max_lines=2)
            )

        actions: list[ft.Control] = [
            ui.button(
                c,
                "Manter Local",
                on_click=lambda _e: resolve_conflict(force_push=True),
                variant="default",
            ),
            ui.button(
                c,
                "Manter Nuvem",
                on_click=lambda _e: resolve_conflict(force_pull=True),
                variant="primary",
            ),
        ]

        dialog_box = ui.modal(
            c,
            title="Conflito de Sincronização",
            controls=content_controls,
            actions=actions,
            width=500,
            subtitle="Divergência detectada entre as estações de trabalho.",
        )
        modal_ref[0] = dialog_box
        ui.open_dialog(page, dialog_box)

    def _compose_cloud_sync_card(self) -> ft.Container:
        """Card de governança da sincronização com Google Drive."""
        sync_svc = self.cloud_sync_service
        is_auth = sync_svc.is_authenticated() if sync_svc else False

        status_text = ft.Text(
            value=(
                "Conectado ao Google Drive (appDataFolder)."
                if is_auth
                else "Nenhuma conta vinculada. Os dados residem exclusivamente neste dispositivo."
            ),
            font_family=self.config.font_families["montserrat"],
            weight=self.config.font_weights["montserrat_normal"],
            size=self.config.font_sizes["montserrat_micro"],
            color=self.config.colors["text" if is_auth else "muted"],
        )

        feedback_banner = ft.Container(visible=False)

        def safe_ui_update(ctrl: ft.Control | None = None) -> None:
            page = self.page or getattr(status_text, "page", None)

            def _apply() -> None:
                if ctrl is not None and safe_update(ctrl):
                    return
                if page is not None:
                    safe_update(page)

            run_on_ui(page, _apply)

        def on_sync_click(_):
            status_text.value = "Sincronizando com o Google Drive..."
            status_text.color = self.config.colors["gold"]
            feedback_banner.visible = True
            feedback_banner.content = ft.ProgressBar(
                color=self.config.colors["gold"],
                bgcolor=self.config.colors["surface"],
            )
            safe_ui_update(status_text)
            safe_ui_update(feedback_banner)

            def run_sync():
                try:
                    res = sync_svc.sync(sync_pdfs=False)
                    if res.status == SyncStatus.SUCCESS:
                        status_text.value = f"Sincronizado: {res.message}"
                        status_text.color = self.config.colors["gold"]
                        feedback_banner.visible = False
                    elif res.status == SyncStatus.NO_CHANGES:
                        status_text.value = "Tudo atualizado. Nenhuma mutação pendente."
                        status_text.color = self.config.colors["text"]
                        feedback_banner.visible = False
                    elif res.status == SyncStatus.CONFLICT:
                        status_text.value = "Aviso: Conflito detectado com outra estação."
                        status_text.color = self.config.colors["danger"]
                        if res.conflict_backup_path:
                            feedback_banner.visible = True
                            feedback_banner.content = ft.Text(
                                f"Cópia de segurança criada em: {res.conflict_backup_path}",
                                size=11,
                                color=self.config.colors["danger"],
                            )
                        else:
                            feedback_banner.visible = False
                        self._show_conflict_modal(
                            res,
                            status_text=status_text,
                            feedback_banner=feedback_banner,
                        )
                    else:
                        status_text.value = f"Erro: {res.message}"
                        status_text.color = self.config.colors["danger"]
                        feedback_banner.visible = False
                except Exception as err:
                    status_text.value = f"Erro durante sincronização: {err}"
                    status_text.color = self.config.colors["danger"]
                    feedback_banner.visible = False
                safe_ui_update(status_text)
                safe_ui_update(feedback_banner)

            run_task = getattr(self.page, "run_task", None) if hasattr(self, "page") and self.page is not None else None
            if run_task is not None:
                async def _async_sync():
                    await asyncio.to_thread(run_sync)
                run_task(_async_sync)
            else:
                threading.Thread(target=run_sync, daemon=True).start()

        def on_auth_click(_):
            if is_auth:
                sync_svc.logout()
                if self.on_navigate:
                    self.on_navigate("settings")
                return

            status_text.value = "Abrindo navegador para autenticação..."
            status_text.color = self.config.colors["gold"]
            safe_ui_update(status_text)

            def run_auth():
                try:
                    sync_svc.authenticate()
                    status_text.value = "Autenticação concluída! Atualizando painel..."
                    status_text.color = self.config.colors["gold"]
                    safe_ui_update(status_text)
                    if self.on_navigate:
                        self.on_navigate("settings")
                except Exception as err:
                    status_text.value = f"Falha na autenticação: {err}"
                    status_text.color = self.config.colors["danger"]
                    safe_ui_update(status_text)

            run_task = getattr(self.page, "run_task", None) if hasattr(self, "page") and self.page is not None else None
            if run_task is not None:
                async def _async_auth():
                    await asyncio.to_thread(run_auth)
                run_task(_async_auth)
            else:
                threading.Thread(target=run_auth, daemon=True).start()

        sync_button = ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.SYNC_ROUNDED,
                        size=16,
                        color=self.config.colors["bg"],
                    ),
                    ft.Text(
                        value="Sincronizar Agora",
                        font_family=self.config.font_families["montserrat"],
                        weight=self.config.font_weights["montserrat_semibold"],
                        size=self.config.font_sizes["montserrat_small"],
                        color=self.config.colors["bg"],
                    ),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(
                bgcolor=self.config.colors["gold"],
                shape=ft.RoundedRectangleBorder(
                    radius=self.config.ui.get("card_radius", 6)
                ),
                padding=ft.Padding.symmetric(vertical=12, horizontal=16),
            ),
            on_click=on_sync_click,
            visible=is_auth,
        )

        auth_button = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.LOGIN_ROUNDED if not is_auth else ft.Icons.LOGOUT_ROUNDED,
                        size=16,
                    ),
                    ft.Text(
                        value="Conectar Google Drive" if not is_auth else "Desconectar",
                        font_family=self.config.font_families["montserrat"],
                        weight=self.config.font_weights["montserrat_semibold"],
                        size=self.config.font_sizes["montserrat_small"],
                    ),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, self.config.colors["border"]),
                shape=ft.RoundedRectangleBorder(
                    radius=self.config.ui.get("card_radius", 6)
                ),
                bgcolor=self.config.colors["surface"],
                padding=ft.Padding.symmetric(vertical=12, horizontal=16),
            ),
            on_click=on_auth_click,
        )

        buttons_row = ft.Row(
            controls=[btn for btn in [sync_button, auth_button] if btn.visible],
            spacing=10,
        )

        content = ft.Column(
            controls=[
                status_text,
                feedback_banner,
                buttons_row,
            ],
            spacing=12,
        )

        return self._compose_card_container(
            icon=ft.Icons.CLOUD_SYNC_OUTLINED,
            title="Sincronização em Nuvem (Google Drive)",
            subtitle="Persistência privada e atômica na pasta oculta appDataFolder com custo zero.",
            content=content,
        )
