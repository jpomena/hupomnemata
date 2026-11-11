"""Diálogo de importação inteligente de metadados por DOI, ISBN e ISSN."""

from __future__ import annotations

import threading
from collections.abc import Callable

import flet as ft

from src.utils.fa import fa_icon
from src.utils.types import ViewConfig
from src.services.metadata_service import (
    IdentifierType,
    ImportedMetadata,
    MetadataService,
    check_local_duplicate,
    detect_identifier,
)
from src.views import ui_kit as ui
from src.views.ui_kit import s


class ImportModalDialog:
    """Diálogo modal com auto-detecção em tempo real e busca de metadados."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        on_success: Callable[[ImportedMetadata], None],
        on_navigate_to_work: Callable[[int], None] | None = None,
        service: MetadataService | None = None,
    ) -> None:
        self.page = page
        self.config = config
        self.on_success = on_success
        self.on_navigate_to_work = on_navigate_to_work
        self.service = service or MetadataService()

        self.dialog: ft.AlertDialog | None = None
        self.is_open = False
        self.loading = False
        self.ignore_duplicate = False

        # Controles
        c = self.config
        self.input_field = ui.input_field(
            c,
            hint="Ex.: 10.1038/nature.2014.14583, 978-85-7559-484-1 ou 0101-3300",
            prefix_icon="barcode",
            on_change=self._on_input_change,
            on_submit=lambda _e: self._on_search_clicked(),
            expand=True,
            autofocus=True,
        )

        self.badge_container = ft.Container(content=None, visible=False)
        self.error_text = ui.ui_text(c, "", size=12, color=c.colors.get("danger", "#ef4444"))
        self.error_box = ft.Container(
            content=ft.Row(
                [
                    fa_icon("circle-exclamation", size=s(14), color=c.colors.get("danger", "#ef4444")),
                    ft.Container(content=self.error_text, expand=True),
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            visible=False,
            padding=ft.Padding.symmetric(vertical=s(4)),
        )

        self.duplicate_box = ft.Container(visible=False, padding=ft.Padding.symmetric(vertical=s(4)))

        self.loading_ring = ft.ProgressRing(width=s(16), height=s(16), stroke_width=2, color=c.colors["gold"])
        self.loading_label = ui.ui_text(c, "Consultando bases abertas...", size=12, color=c.colors["muted"])
        self.loading_box = ft.Container(
            content=ft.Row([self.loading_ring, self.loading_label], spacing=s(8), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            visible=False,
            padding=ft.Padding.symmetric(vertical=s(4)),
        )

        self.btn_cancel = ui.button(c, "Cancelar", on_click=lambda _e: self.close(), variant="ghost")
        self.btn_submit = ui.button(c, "Buscar e Preencher", icon_name="magnifying-glass", variant="primary", on_click=lambda _e: self._on_search_clicked())

    def show(self) -> None:
        c = self.config
        header = ft.Container(
            content=ft.Row(
                [
                    fa_icon("file-import", size=s(16), color=c.colors["gold"]),
                    ft.Column(
                        [
                            ui.ui_text(c, "Importar Metadados", size=15, weight=ui.W600),
                            ui.ui_text(c, "Informe um DOI, ISBN ou ISSN para preencher automaticamente os dados da obra.", size=12, color=c.colors["muted"]),
                        ],
                        spacing=s(2),
                        tight=True,
                        expand=True,
                    ),
                    ui.icon_button(c, "xmark", on_click=lambda _e: self.close(), tooltip="Fechar (Esc)"),
                ],
                spacing=s(12),
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=s(20),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
        )

        input_row = ft.Row(
            [
                self.input_field,
                self.badge_container,
            ],
            spacing=s(8),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        body = ft.Container(
            width=s(540),
            content=ft.Column(
                [
                    header,
                    ft.Container(
                        content=ft.Column(
                            [
                                input_row,
                                self.badge_container,
                                self.loading_box,
                                self.error_box,
                                self.duplicate_box,
                            ],
                            spacing=s(10),
                            tight=True,
                        ),
                        padding=s(20),
                    ),
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(expand=True),
                                self.btn_cancel,
                                self.btn_submit,
                            ],
                            spacing=s(8),
                        ),
                        padding=ft.Padding.only(left=s(20), right=s(20), bottom=s(16), top=s(8)),
                    ),
                ],
                spacing=0,
                tight=True,
            ),
        )

        self.dialog = ft.AlertDialog(
            content=body,
            content_padding=0,
            bgcolor=c.colors["surface"],
            shape=ft.RoundedRectangleBorder(radius=s(10)),
            alignment=ft.Alignment.CENTER,
            barrier_color=ft.Colors.with_opacity(0.6, c.colors["black"]),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            on_dismiss=lambda _e: setattr(self, "is_open", False),
        )
        self.is_open = True
        self.page.show_dialog(self.dialog)

    def close(self) -> None:
        self.is_open = False
        if self.dialog is not None:
            self.dialog.open = False
            try:
                self.dialog.update()
            except Exception:
                pass
            try:
                self.page.pop_dialog()
            except Exception:
                pass

    def _on_input_change(self, event: ft.ControlEvent) -> None:
        raw = event.control.value or ""
        id_type, _ = detect_identifier(raw)
        c = self.config

        if not raw.strip():
            self.badge_container.visible = False
            self.badge_container.content = None
        elif id_type == IdentifierType.DOI:
            self.badge_container.visible = True
            self.badge_container.content = ui.badge(c, "DOI Detectado")
        elif id_type == IdentifierType.ISBN:
            self.badge_container.visible = True
            self.badge_container.content = ui.badge(c, "ISBN Detectado")
        elif id_type == IdentifierType.ISSN:
            self.badge_container.visible = True
            self.badge_container.content = ui.badge(c, "ISSN Detectado")
        else:
            self.badge_container.visible = True
            self.badge_container.content = ui.badge(c, "Formato desconhecido")

        # Limpar erros antigos
        self.error_box.visible = False
        self.duplicate_box.visible = False
        self.ignore_duplicate = False
        try:
            self.badge_container.update()
            self.error_box.update()
            self.duplicate_box.update()
        except Exception:
            pass

    def _set_loading(self, loading: bool) -> None:
        self.loading = loading
        self.loading_box.visible = loading
        self.btn_submit.disabled = loading
        self.input_field.disabled = loading
        try:
            self.loading_box.update()
            self.btn_submit.update()
            self.input_field.update()
        except Exception:
            pass

    def _show_error(self, message: str) -> None:
        self.error_text.value = message
        self.error_box.visible = True
        self.duplicate_box.visible = False
        try:
            self.error_box.update()
            self.duplicate_box.update()
        except Exception:
            pass

    def _show_duplicate_warning(self, work_id: int, work_title: str) -> None:
        c = self.config

        def _on_view_existing(_e):
            self.close()
            if self.on_navigate_to_work is not None:
                self.on_navigate_to_work(work_id)

        def _on_force_continue(_e):
            self.ignore_duplicate = True
            self.duplicate_box.visible = False
            try:
                self.duplicate_box.update()
            except Exception:
                pass
            self._execute_remote_search()

        self.duplicate_box.content = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            fa_icon("triangle-exclamation", size=s(14), color=c.colors.get("warning", "#eab308")),
                            ui.ui_text(c, "Identificador já cadastrado no Acervo:", size=12, weight=ui.W600, color=c.colors.get("warning", "#eab308")),
                        ],
                        spacing=s(6),
                    ),
                    ui.ui_text(c, f"“{work_title}”", size=12, color=c.colors["text"], weight=ui.W500),
                    ft.Row(
                        [
                            ui.button(c, "Ver obra cadastrada", variant="default", small=True, on_click=_on_view_existing),
                            ui.button(c, "Importar como nova", variant="ghost", small=True, on_click=_on_force_continue),
                        ],
                        spacing=s(6),
                    ),
                ],
                spacing=s(6),
                tight=True,
            ),
            bgcolor=ui.alpha(c.colors.get("warning", "#eab308"), 0.12),
            border=ft.Border.all(1, ui.alpha(c.colors.get("warning", "#eab308"), 0.3)),
            border_radius=ft.BorderRadius.all(s(6)),
            padding=s(10),
        )
        self.duplicate_box.visible = True
        try:
            self.duplicate_box.update()
        except Exception:
            pass

    def _on_search_clicked(self) -> None:
        if self.loading:
            return

        raw = (self.input_field.value or "").strip()
        if not raw:
            self._show_error("Por favor, digite um DOI, ISBN ou ISSN.")
            return

        id_type, clean_id = detect_identifier(raw)
        if id_type == IdentifierType.UNKNOWN:
            self._show_error("Identificador não reconhecido. Certifique-se de inserir um DOI (10.xxxx), ISBN ou ISSN.")
            return

        # Checar duplicidade no banco local antes da requisição de rede
        if not self.ignore_duplicate:
            duplicate = check_local_duplicate(id_type, clean_id)
            if duplicate:
                work_id, work_title = duplicate
                self._show_duplicate_warning(work_id, work_title)
                return

        self._execute_remote_search()

    def _execute_remote_search(self) -> None:
        raw = (self.input_field.value or "").strip()
        self._set_loading(True)
        self.error_box.visible = False
        try:
            self.error_box.update()
        except Exception:
            pass

        def run_thread():
            try:
                metadata = self.service.resolve(raw)
                # Encaminhar sucesso de volta à thread principal do UI
                def finish_success():
                    self.close()
                    self.on_success(metadata)

                if hasattr(self.page, "run_task"):
                    self.page.run_task(lambda: finish_success())
                else:
                    finish_success()
            except Exception as exc:
                err_msg = str(exc)
                if "não foi encontrado" in err_msg.lower():
                    clean_msg = err_msg
                else:
                    clean_msg = f"Falha ao consultar metadados: {err_msg}"

                def finish_error():
                    self._set_loading(False)
                    self._show_error(clean_msg)

                if hasattr(self.page, "run_task"):
                    self.page.run_task(lambda: finish_error())
                else:
                    finish_error()

        thread = threading.Thread(target=run_thread, daemon=True)
        thread.start()
