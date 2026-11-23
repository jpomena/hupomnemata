"""Implementações de override do compositor Nous."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from typing import Dict
import flet as ft

if TYPE_CHECKING:
    from src.views.nous_composer import NousComposer


def open_override_dialog(self: NousComposer, work_item: Dict[str, Any]) -> None:
    """Abre diálogo para o usuário inspecionar e sobrepor a síntese com texto próprio."""
    work_id = work_item["id"]
    title = work_item["title"]
    current_custom = work_item.get("custom_description") or ""
    current_llm = work_item.get("llm_description") or ""

    text_input = ft.TextField(
        value=current_custom if current_custom else current_llm,
        label="Síntese Conceitual / Anotação da Obra",
        hint_text="Escreva ou ajuste a síntese da obra. Seu texto terá prioridade sobre a IA.",
        multiline=True,
        min_lines=6,
        max_lines=12,
        text_size=16 * self.scale,
        text_style=ft.TextStyle(
            font_family=self.config.font_families["cormorant"],
            size=16 * self.scale,
            weight=ft.FontWeight.W_600,
            color=self.config.colors["text"],
            height=1.45,
        ),
        border_color=self.config.colors["border"],
        bgcolor=self.config.colors["surface"],
        text_align=ft.TextAlign.JUSTIFY,
    )

    def save_override(_):
        new_text = text_input.value or ""
        self.nous_service.override_work_description(work_id, new_text)
        dialog.open = False
        self.page.update()

        self._refresh_works_data()

    def clear_override(_):
        self.nous_service.override_work_description(work_id, None)
        dialog.open = False
        self.page.update()

        self._refresh_works_data()

    dialog = ft.AlertDialog(
        title=ft.Text(
            f"Personalizar Síntese: {title}",
            size=20 * self.scale,
            font_family=self.config.font_families["cormorant"],
            weight=ft.FontWeight.W_700,
            color=self.config.colors["gold"],
        ),
        content=ft.Container(
            width=550 * self.scale,
            content=ft.Column(
                controls=[
                    ft.Text(
                        "O texto inserido aqui sobrepõe qualquer síntese gerada por IA e passará a orientar a posição da obra na Constelação 3D.",
                        size=12 * self.scale,
                        font_family=self.config.font_families["montserrat"],
                        color=self.config.colors["muted"],
                    ),
                    text_input,
                ],
                spacing=10 * self.scale,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton(
                content="Restaurar Síntese IA",
                on_click=clear_override,
            ),
            ft.OutlinedButton(
                content="Cancelar",
                on_click=lambda _: setattr(dialog, "open", False) or self.page.update(),
            ),
            ft.FilledButton(
                content="Salvar Síntese",
                on_click=save_override,
                style=ft.ButtonStyle(
                    bgcolor=self.config.colors["gold"],
                    color=self.config.colors["on_gold"],
                ),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    self.page.overlay.append(dialog)
    dialog.open = True
    self.page.update()
