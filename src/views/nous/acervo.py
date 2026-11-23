"""Implementações de acervo do compositor Nous."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from src.views.nous_composer import NousComposer


def build_acervo_management_card(self: NousComposer) -> ft.Control:
    """Card de gestão de sínteses do acervo e processamento em lote."""
    self.metrics_row = ft.Row(
        controls=[
            self._metric_chip("Total de Obras", self.stat_total, self.config.colors["text"]),
            self._metric_chip("Com Síntese IA", self.stat_with_ai, self.config.colors["gold"]),
            self._metric_chip("Personalizadas", self.stat_custom, self.config.colors["muted"]),
            self._metric_chip("Pendentes", self.stat_pending, self.config.colors["muted"]),
        ],
        spacing=14 * self.scale,
    )

    batch_actions_row = ft.Row(
        controls=[
            self.search_filter,
            ft.FilledButton(
                content="Gerar para Todas as Obras Pendentes",
                icon=ft.Icons.BOLT,
                on_click=self._handle_batch_generation,
                style=ft.ButtonStyle(
                    bgcolor=self.config.colors["gold"],
                    color=self.config.colors["on_gold"],
                ),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    return ft.Container(
        bgcolor=self.config.colors["surface"],
        border=ft.Border.all(1, self.config.colors["border"]),
        border_radius=10,
        padding=18 * self.scale,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME, size=18 * self.scale, color=self.config.colors["gold"]),
                        ft.Text(
                            "Gestão de Síntese Epistemológica do Acervo",
                            size=self.config.font_sizes["cormorant_medium"] * self.scale,
                            font_family=self.config.font_families["cormorant"],
                            weight=self.config.font_weights["cormorant_semibold"],
                            color=self.config.colors["gold"],
                        ),
                    ],
                    spacing=8 * self.scale,
                ),
                ft.Text(
                    "As sínteses epistemológicas contextualizam as teses fundamentais de cada obra e "
                    "posicionam os nós na Constelação 3D. Você pode gerar com IA e sobrepor com suas próprias anotações a qualquer momento.",
                    size=15 * self.scale,
                    font_family=self.config.font_families["cormorant"],
                    weight=ft.FontWeight.W_600,
                    color=self.config.colors["text"],
                    style=ft.TextStyle(height=1.4),
                ),
                self.metrics_row,
                ft.Divider(color=self.config.colors["border"], height=10 * self.scale),
                batch_actions_row,
                self.batch_progress_bar,
                self.batch_progress_text,
                ft.Container(height=6 * self.scale),
                self.works_column,
            ],
            spacing=12 * self.scale,
            tight=True,
        ),
    )


def metric_chip(self: NousComposer, label: str, value_ctrl: ft.Text, accent_color: str) -> ft.Control:
    return ft.Container(
        bgcolor=self.config.colors["bg"],
        border=ft.Border.all(1, self.config.colors["border"]),
        border_radius=8,
        padding=ft.Padding(16 * self.scale, 10 * self.scale, 16 * self.scale, 10 * self.scale),
        content=ft.Column(
            controls=[
                ft.Text(
                    label.upper(),
                    size=10 * self.scale,
                    font_family=self.config.font_families["montserrat"],
                    weight=ft.FontWeight.W_600,
                    color=self.config.colors["muted"],
                ),
                value_ctrl,
            ],
            spacing=2 * self.scale,
            tight=True,
        ),
        expand=True,
    )


def refresh_works_data(self: NousComposer) -> None:
    """Carrega todas as obras do banco e calcula métricas de IA."""
    self.works_data = self.nous_service.list_works_ai_status()

    total = len(self.works_data)
    with_ai = sum(1 for w in self.works_data if w["has_llm"] and not w["has_custom"])
    custom = sum(1 for w in self.works_data if w["has_custom"])
    pending = sum(1 for w in self.works_data if not w["has_llm"] and not w["has_custom"])

    self.stat_total.value = str(total)
    self.stat_with_ai.value = str(with_ai)
    self.stat_custom.value = str(custom)
    self.stat_pending.value = str(pending)

    self._render_works_list(self.works_data)
