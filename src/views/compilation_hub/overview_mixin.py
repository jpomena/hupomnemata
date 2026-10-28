"""Mixin para a aba de Visão Geral no hub de compilações."""

import flet as ft

from src.contracts import CompilationPayload
from src.utils.view_styles import button_text_style


class CompilationHubOverviewMixin:
    """Responsável pela apresentação de metadados, métricas e edição da compilação."""

    def _save_details(self, event: ft.Event[ft.Button]) -> None:
        del event
        name = self.name_field.value
        if not name or not name.strip():
            return
        payload: CompilationPayload = {
            'name': name.strip(),
            'description': (self.description_field.value or '').strip() or None,
        }
        if self.on_update(self.compilation['id'], payload):
            self.refresh()

    def _work_count_label(self) -> str:
        count = len(self.compilation['works'])
        return f'{count} {"obra" if count == 1 else "obras"}'

    def _fragment_count_label(self) -> str:
        fragments = [
            fragment
            for work in self.compilation['works']
            for fragment in work['fragments']
        ]
        selected = sum(fragment['is_member'] for fragment in fragments)
        total = len(fragments)
        noun = 'fragmento selecionado' if selected == 1 else (
            'fragmentos selecionados'
        )
        return (
            f'{selected} de {total} {noun} para o caderno'
        )

    def _compose_overview(self) -> ft.Control:
        return ft.Column(
            controls=[
                ft.Text(
                    value='Sobre este projeto',
                    size=self.config.font_sizes['cormorant_medium'],
                    font_family=self.config.font_families['cormorant'],
                    weight=self.config.font_weights['cormorant_semibold'],
                    color=self.config.colors['text'],
                ),
                self.name_field,
                self.description_field,
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text(
                                        value=self._work_count_label(),
                                        color=self.config.colors['gold'],
                                        size=self.config.font_sizes[
                                            'cormorant_medium'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'cormorant'
                                            ]
                                        ),
                                    ),
                                    ft.Text(
                                        value='Obras vinculadas',
                                        color=self.config.colors['muted'],
                                        size=self.config.font_sizes[
                                            'montserrat_medium'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'montserrat'
                                            ]
                                        ),
                                    ),
                                ],
                                spacing=2,
                            ),
                            padding=self.config.ui['card_padding'],
                            bgcolor=self.config.colors['surface'],
                            border_radius=self.config.ui['card_radius'],
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Text(
                                        value=self._fragment_count_label(),
                                        color=self.config.colors['gold'],
                                        size=self.config.font_sizes[
                                            'cormorant_medium'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'cormorant'
                                            ]
                                        ),
                                    ),
                                    ft.Text(
                                        value='Fragmentos no caderno',
                                        color=self.config.colors['muted'],
                                        size=self.config.font_sizes[
                                            'montserrat_medium'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'montserrat'
                                            ]
                                        ),
                                    ),
                                ],
                                spacing=2,
                            ),
                            padding=self.config.ui['card_padding'],
                            bgcolor=self.config.colors['surface'],
                            border_radius=self.config.ui['card_radius'],
                            expand=True,
                        ),
                    ],
                    spacing=self.config.ui['control_gap'],
                ),
                ft.Row(
                    controls=[
                        ft.FilledButton(
                            content=ft.Text(
                                'Salvar dados do projeto',
                                color=self.config.colors['bg'],
                                font_family=(
                                    self.config.font_families['montserrat']
                                ),
                                size=self.config.font_sizes[
                                    'montserrat_medium'
                                ],
                                weight=self.config.font_weights[
                                    'montserrat_normal'
                                ],
                            ),
                            bgcolor=self.config.colors['gold'],
                            style=ft.ButtonStyle(
                                text_style=button_text_style(self.config),
                            ),
                            on_click=self._save_details,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=self.config.ui['control_gap'],
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
