"""Card de manutenção destrutiva dos bancos de dados."""

import threading
from typing import Callable

import flet as ft

from src.utils.control_safety import safe_update
from src.views import ui_kit as ui


class SettingsDatabaseMixin:
    """Zona de perigo para apagar bancos locais e, opcionalmente, a nuvem."""

    def _compose_database_card(self) -> ft.Container:
        c = self.config
        is_auth = False
        sync_svc = getattr(self, "cloud_sync_service", None)
        if sync_svc is not None:
            try:
                is_auth = bool(sync_svc.is_authenticated())
            except Exception:
                is_auth = False

        body = ft.Column(
            controls=[
                ui.ui_text(
                    c,
                    "Apaga o banco ativo, backups de conflito, backups locais "
                    "e snapshots de sincronização. A base é recriada vazia; "
                    "PDFs e preferências são preservados.",
                    size=13,
                    color=c.colors["text"],
                    max_lines=None,
                ),
                ui.ui_text(
                    c,
                    (
                        "A cópia no Google Drive só é apagada se a opção for "
                        "marcada no diálogo de confirmação."
                        if is_auth
                        else "Nuvem não conectada: apenas os bancos locais "
                        "serão apagados e o autosave ficará suspenso até que "
                        "a nuvem seja apagada."
                    ),
                    size=12,
                    color=c.colors["muted"],
                    max_lines=None,
                ),
                ft.Row(
                    controls=[
                        ui.button(
                            c,
                            "Apagar bancos de dados...",
                            on_click=lambda _e: self._open_delete_databases_dialog(
                                is_auth
                            ),
                            variant="danger",
                            icon_name="trash-can",
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=ui.s(8),
            tight=True,
        )
        return self._compose_card_container(
            icon=ft.Icons.DELETE_FOREVER,
            title="Bancos de dados",
            subtitle="Zona de perigo",
            content=body,
        )

    def _open_delete_databases_dialog(self, is_auth: bool) -> None:
        page = self.page
        if page is None:
            return
        c = self.config

        confirm = ui.input_field(
            c,
            hint="Digite APAGAR para confirmar",
            autofocus=True,
            expand=None,
        )
        delete_cloud = ft.Checkbox(
            label="Apagar também a cópia na nuvem (Google Drive)",
            value=is_auth,
            disabled=not is_auth,
            fill_color=c.colors["danger"],
        )
        delete_button = ft.FilledButton(
            content=ft.Text(
                "Apagar bancos",
                size=13,
                font_family=c.font_families["montserrat"],
                weight=c.font_weights["montserrat_semibold"],
            ),
            bgcolor=c.colors["danger"],
            color=c.colors["on_gold"],
            disabled=True,
        )

        def on_confirm_change(_e) -> None:
            delete_button.disabled = (
                (confirm.value or "").strip().upper() != "APAGAR"
            )
            safe_update(delete_button)

        confirm.on_change = on_confirm_change

        def close_dialog(_e=None) -> None:
            ui.close_dialog(page)

        def confirm_delete(_e=None) -> None:
            if delete_button.disabled:
                return
            remove_cloud = bool(delete_cloud.value) if is_auth else False
            ui.close_dialog(page)
            callback: Callable[[bool], None] | None = getattr(
                self, "on_delete_databases", None
            )
            if callback is not None:
                threading.Thread(
                    target=callback,
                    args=(remove_cloud,),
                    daemon=True,
                ).start()

        delete_button.on_click = confirm_delete

        controls: list[ft.Control] = [
            ui.ui_text(
                c,
                "Serão apagados: banco ativo, backups de conflito, backups "
                "locais e snapshots de sincronização. A base será recriada "
                "vazia. Esta ação é irreversível.",
                size=13,
                color=c.colors["text"],
                max_lines=None,
            ),
            ui.form_field(c, "Confirmação", confirm),
            delete_cloud,
        ]
        if not is_auth:
            controls.append(
                ui.ui_text(
                    c,
                    "Sem conta Google conectada, o autosave ficará suspenso "
                    "para não restaurar uma cópia remota.",
                    size=11,
                    color=c.colors["muted"],
                    max_lines=None,
                )
            )

        ui.modal(
            c,
            title="Apagar bancos de dados?",
            subtitle="Zona de perigo · ação irreversível",
            controls=controls,
            actions=[
                ui.button(
                    c,
                    "Cancelar",
                    on_click=close_dialog,
                    variant="default",
                ),
                delete_button,
            ],
            width=560,
            dismissible=False,
            page=page,
        )
