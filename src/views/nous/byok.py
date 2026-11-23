"""Implementações de byok do compositor Nous."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft
import webbrowser

from src.configs.settings import COLORS_DARK, COLORS_LIGHT

if TYPE_CHECKING:
    from src.views.nous_composer import NousComposer


def build_byok_card(self: NousComposer) -> ft.Control:
    """Card de configuração BYOK com instruções didáticas passo a passo."""
    tutorial_steps = ft.Container(
        bgcolor=f"{self.config.colors['bg']}",
        border=ft.Border(left=ft.BorderSide(3 * self.scale, self.config.colors["gold"])),
        border_radius=6,
        padding=14 * self.scale,
        content=ft.Column(
            controls=[
                ft.Text(
                    "COMO OBTER SUA CHAVE GRATUITA¹ DO GOOGLE GEMINI EM 3 PASSOS:",
                    size=11 * self.scale,
                    weight=ft.FontWeight.W_700,
                    color=self.config.colors["gold"],
                    font_family=self.config.font_families['montserrat'],
                ),
                ft.Text(
                    "1. Acesse o portal oficial do Google AI Studio (aistudio.google.com/app/apikey).",
                    size=12 * self.scale,
                    color=self.config.colors["text"],
                    font_family=self.config.font_families['montserrat'],
                ),
                ft.Text(
                    "2. Faça login com sua conta Google e clique no botão azul 'Get API key' (ou 'Create API key') para gerar uma nova chave.",
                    size=12 * self.scale,
                    color=self.config.colors["text"],
                    font_family=self.config.font_families['montserrat'],
                ),
                ft.Text(
                    "3. Copie a chave, cole no campo abaixo e clique em 'Salvar e Testar Conexão'². Sua chave é gravada localmente de forma privada.",
                    size=12 * self.scale,
                    color=self.config.colors["text"],
                    font_family=self.config.font_families['montserrat'],
                ),
                ft.Text(
                    "1 A disponibilidade de chaves gratuitas depende única e exclusivamente da Google, não cabendo a esta aplicação o fornecimento de chaves gratuitas.",
                    size=10 * self.scale,
                    color=self.config.colors["text"],
                    font_family=self.config.font_families['montserrat'],
                    italic=True,
                ),
                ft.Text(
                    "2 Os desenvolvedores não se responsabilizam por quaisquer custos decorrentes do uso de modelos generativos de linguagem pelo usuário, fornecendo apenas uma interface para uso mediado.",
                    size=10 * self.scale,
                    color=self.config.colors["text"],
                    font_family=self.config.font_families['montserrat'],
                    italic=True,
                ),
            ],
            spacing=8 * self.scale,
            tight=True,
        ),
    )

    input_row = ft.Row(
        controls=[
            self.api_key_field,
            ft.FilledButton(
                content="Salvar e Testar",
                icon=ft.Icons.CHECK,
                on_click=self._handle_save_and_test_key,
                style=ft.ButtonStyle(
                    bgcolor=self.config.colors["gold"],
                    color=self.config.colors["on_gold"],
                ),
            ),
            ft.OutlinedButton(
                content="Abrir AI Studio",
                icon=ft.Icons.OPEN_IN_NEW,
                on_click=self._handle_open_ai_studio,
                style=ft.ButtonStyle(
                    color=self.config.colors["text"],
                    side=ft.BorderSide(1, self.config.colors["border"]),
                ),
            ),
        ],
        spacing=10 * self.scale,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
                        ft.Icon(ft.Icons.KEY, size=18 * self.scale, color=self.config.colors["gold"]),
                        ft.Text(
                            "Configuração BYOK (Bring Your Own Key)",
                            size=15 * self.scale,
                            font_family=self.config.font_families["montserrat"],
                            weight=ft.FontWeight.W_700,
                            color=self.config.colors["gold"],
                        ),
                    ],
                    spacing=8 * self.scale,
                ),
                tutorial_steps,
                input_row,
                self.status_feedback,
            ],
            spacing=12 * self.scale,
            tight=True,
        ),
    )


def handle_open_ai_studio(self: NousComposer, _e: ft.ControlEvent) -> None:
    """Abre a página do Google AI Studio no navegador padrão."""
    url = "https://aistudio.google.com/app/apikey"
    try:
        webbrowser.open(url)
    except Exception:
        if self.page:
            self.page.run_task(self.page.launch_url, url)


def get_error_colors(self: NousComposer) -> tuple[str, str]:
    """Retorna (cor_texto, cor_fundo) a partir dos tokens de erro do tema."""
    is_dark = (self.current_theme_mode or "light").lower() == "dark"
    colors = COLORS_DARK if is_dark else COLORS_LIGHT
    return colors["error_text"], colors["error_bg"]


def handle_save_and_test_key(self: NousComposer, _e: ft.ControlEvent) -> None:
    """Salva a chave de API fornecida e executa teste de conectividade."""
    err_color, _ = self._get_error_colors()
    key = (self.api_key_field.value or "").strip()
    if not key:
        self.status_feedback.value = "Por favor, digite ou cole a chave de API."
        self.status_feedback.color = err_color
        self.status_feedback.weight = ft.FontWeight.W_600
        self.page.update()

        return

    self.status_feedback.value = "Testando conexão com Google Gemini..."
    self.status_feedback.color = self.config.colors["muted"]
    self.status_feedback.weight = ft.FontWeight.W_400
    self.page.update()

    ok, msg = self.nous_service.test_connection(key)
    if ok:
        self.nous_service.save_api_key(key)
        self.has_key = True
        self.status_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE
        self.status_icon.color = self.config.colors["gold"]
        self.status_chip_text.value = "Conexão Ativa"
        self.status_chip_text.color = self.config.colors["gold"]
        self.status_chip_text.weight = ft.FontWeight.W_600
        self.status_chip.bgcolor = self.config.colors["surface"]
        self.status_chip.border = ft.Border.all(1, self.config.colors["gold"])
        self.status_feedback.value = "✓ " + msg
        self.status_feedback.color = self.config.colors["gold"]
        self.status_feedback.weight = ft.FontWeight.W_500
    else:
        self.status_icon.name = ft.Icons.ERROR_OUTLINE
        self.status_icon.color = err_color
        self.status_chip_text.value = "Falha na Conexão"
        self.status_chip_text.color = err_color
        self.status_chip_text.weight = ft.FontWeight.W_600
        self.status_chip.bgcolor = self.config.colors["surface"]
        self.status_chip.border = ft.Border.all(1, err_color)
        self.status_feedback.value = "✕ " + msg
        self.status_feedback.color = err_color
        self.status_feedback.weight = ft.FontWeight.W_600

    self.page.update()
