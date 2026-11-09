"""Aba Visão geral: tabela do roteiro, card Detalhes e zona de risco."""

import flet as ft

from src.contracts import CompilationPayload
from src.views import ui_kit as ui
from src.views.ui_kit import s
from .common import dialog, fmt_date, form_field, text_input


class CompilationHubOverviewMixin:
    """Nome, descrição, datas e exclusão da compilação."""

    # ── ações ──────────────────────────────────────────────

    def _save_details(self, name: str, description: str | None) -> bool:
        if not name or not name.strip():
            return False
        payload: CompilationPayload = {
            'name': name.strip(),
            'description': (description or '').strip() or None,
        }
        if self.on_update(self.compilation['id'], payload):
            self.refresh()
            if self.on_chrome_changed is not None:
                self.on_chrome_changed()
            return True
        return False

    def _open_details_dialog(self) -> ft.AlertDialog:
        c = self.config
        self.name_field = text_input(c, value=self.compilation['name'], max_length=150, autofocus=True)
        self.description_field = text_input(
            c,
            value=self.compilation['description'] or '',
            hint='Qual é o tema ou o objetivo deste projeto?',
            multiline=True,
            min_lines=3,
            max_lines=6,
        )

        def save(_event=None) -> None:
            if not (self.name_field.value or '').strip():
                self.name_field.error_text = 'Dê um nome à compilação.'
                try:
                    self.name_field.update()
                except Exception:
                    pass
                return
            self.page.pop_dialog()
            self._save_details(self.name_field.value or '', self.description_field.value)

        self.name_field.on_submit = save
        modal = dialog(
            c,
            'Editar detalhes',
            [form_field(c, 'Nome', self.name_field), form_field(c, 'Descrição (opcional)', self.description_field)],
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: self.page.pop_dialog(), variant='ghost'),
                ui.button(c, 'Salvar', on_click=save, variant='primary'),
            ],
        )
        modal.data = {'save': save}
        self.page.show_dialog(modal)
        return modal

    def _delete_compilation(self) -> None:
        if self.on_delete is None or not self.on_delete(self.compilation['id']):
            return
        self.deleted = True
        if self.on_navigate is not None:
            self.on_navigate('Compilações')

    def _confirm_delete(self) -> ft.AlertDialog:
        c = self.config

        def confirm(_event=None) -> None:
            self.page.pop_dialog()
            self._delete_compilation()

        modal = dialog(
            c,
            'Excluir compilação?',
            [
                ui.ui_text(
                    c,
                    f'“{self.compilation["name"]}” deixa de existir, com o roteiro, as ideias e as notas de articulação. Obras e fragmentos continuam no Acervo.',
                    size=13,
                    color=c.colors['muted'],
                    max_lines=None,
                )
            ],
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: self.page.pop_dialog(), variant='ghost'),
                ui.button(c, 'Excluir compilação', on_click=confirm, variant='danger', icon_name='trash-can', icon_style='regular'),
            ],
            width=440,
        )
        modal.data = {'confirm': confirm}
        self.page.show_dialog(modal)
        return modal

    # ── composição ─────────────────────────────────────────

    def _created_label(self) -> str:
        return fmt_date(self.compilation.get('created_at'))

    def _updated_label(self) -> str:
        return fmt_date(self.compilation.get('updated_at') or self.compilation.get('created_at'))

    def _compose_outline_table(self) -> ft.Container:
        c = self.config
        sections = self._sorted_sections()

        def cells(index: ft.Control, title: ft.Control, idea: ft.Control, count: ft.Control) -> list[ft.Control]:
            return [
                ft.Container(index, width=s(40)),
                ft.Container(title, expand=2),
                ft.Container(idea, expand=3),
                ft.Container(count, width=s(88), alignment=ft.Alignment.CENTER_RIGHT),
            ]

        header = ft.Container(
            content=ft.Row(
                cells(
                    ui.ui_text(c, '#', size=12, color=c.colors['faint']),
                    ui.ui_text(c, 'Ideia', size=12, color=c.colors['faint']),
                    ui.ui_text(c, 'Ideia central', size=12, color=c.colors['faint']),
                    ui.ui_text(c, 'Fragmentos', size=12, color=c.colors['faint']),
                ),
                spacing=s(12),
            ),
            height=s(34),
            padding=ft.Padding.symmetric(horizontal=s(16)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors['border'])),
            alignment=ft.Alignment.CENTER_LEFT,
        )
        rows: list[ft.Control] = []
        for index, section in enumerate(sections):
            sec_title = ui.ui_text(c, section['title'], size=13, weight=ui.W600)

            def _on_hover_sec(hovering: bool, st=sec_title) -> None:
                st.color = c.colors['gold'] if hovering else c.colors['text']

            row = ui.hover_surface(
                c,
                ft.Row(
                    cells(
                        ui.ui_text(c, str(index + 1), size=13, color=c.colors['faint'], tabular=True),
                        sec_title,
                        ui.ui_text(c, section['central_idea'] or '', size=13, color=c.colors['muted']),
                        ui.ui_text(c, str(len(self._section_fragments(section['id']))), size=13, tabular=True),
                    ),
                    spacing=s(12),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=lambda _e, sid=section['id']: self._focus_idea(sid),
                padding=ft.Padding.symmetric(horizontal=s(16), vertical=s(10)),
                radius=0,
                on_hover=_on_hover_sec,
                accent_left=True,
            )
            row.data = section['id']
            rows.append(ft.Container(row, border=ft.Border.only(bottom=ft.BorderSide(1, c.colors['border'])) if index < len(sections) - 1 else None))
        body: list[ft.Control] = [header, *rows] if rows else [
            ft.Container(
                ui.ui_text(c, 'Nenhuma ideia ainda. Crie a primeira no caderno de trabalho.', size=13, color=c.colors['faint']),
                padding=s(16),
            )
        ]
        self.outline_rows = rows
        return ui.card(
            c,
            [ui.card_head(c, 'Roteiro', trailing=ui.link_button(c, 'Abrir caderno', on_click=lambda _e: self._select_tab('caderno')), count=len(sections)), *body],
        )

    def _compose_details_card(self) -> ft.Container:
        c = self.config
        self.edit_details_button = ui.button(
            c,
            'Editar',
            on_click=lambda _e: self._open_details_dialog(),
            icon_name='pen',
            variant='ghost',
            small=True,
        )
        return ui.card(
            c,
            [
                ui.card_head(c, 'Detalhes', trailing=self.edit_details_button),
                ft.Container(
                    ui.props(
                        c,
                        [
                            ('Nome', self.compilation['name']),
                            ('Descrição', self.compilation['description'] or 'Sem descrição'),
                            ('Criada', self._created_label()),
                            ('Atualizada', self._updated_label()),
                        ],
                    ),
                    padding=s(16),
                ),
            ],
        )

    def _compose_danger_card(self) -> ft.Container:
        c = self.config
        self.delete_button = ui.button(
            c,
            'Excluir compilação',
            on_click=lambda _e: self._confirm_delete(),
            icon_name='trash-can',
            icon_style='regular',
            variant='danger',
            small=True,
            disabled=self.on_delete is None,
        )
        return ui.card(
            c,
            [
                ui.card_head(c, 'Excluir compilação'),
                ft.Container(
                    ft.Column(
                        [
                            ui.ui_text(c, 'Remove só os vínculos deste projeto. Obras e fragmentos continuam no Acervo.', size=13, color=c.colors['muted'], max_lines=None),
                            self.delete_button,
                        ],
                        spacing=s(12),
                        tight=True,
                    ),
                    padding=s(16),
                ),
            ],
            danger=True,
        )

    def _compose_overview(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(self._compose_outline_table(), expand=17),
                    ft.Column([self._compose_details_card(), self._compose_danger_card()], spacing=s(24), expand=10, tight=True),
                ],
                spacing=s(24),
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.only(left=s(32), right=s(32), top=s(24), bottom=s(48)),
        )
