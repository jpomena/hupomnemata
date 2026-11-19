"""CadernoPromptsMixin extraído de ``caderno_mixin.py``.

Movimentação literal: sem ``__init__``, colabora com o hub via ``self``.
"""

from collections.abc import Callable

import flet as ft

from src.contracts import (
    CompilationFragmentRecord,
    CompilationSectionRecord,
)
from src.views import ui_kit as ui
from src.views.ui_kit import s
from .common import (
    close_dialog,
    dialog,
    form_field,
    open_dialog,
    select_input,
    text_input,
)


class CadernoPromptsMixin:
    """Diálogos de criação, edição e vínculo de seções do Caderno."""

    def _section_dialog(
        self,
        title: str,
        confirm_label: str,
        on_confirm: Callable[[str, str | None], None],
        section: CompilationSectionRecord | None = None,
        subtitle: str | None = None,
        title_hint: str = 'Ex.: Argumento central',
        name_label: str = 'Nome da ideia',
        idea_label: str = 'Ideia central (opcional)',
        extra_fields: list[ft.Control] | None = None,
    ) -> ft.AlertDialog:
        c = self.config
        title_field = text_input(
            c,
            value=section['title'] if section else '',
            hint=title_hint,
            max_length=150,
            autofocus=True,
            expand=True,
        )
        idea_field = text_input(
            c,
            value=(section['central_idea'] or '') if section else '',
            hint='Que papel esta seção terá no texto?',
            multiline=True,
            min_lines=2,
            max_lines=5,
            max_length=2000,
            expand=True,
        )

        def confirm(_event=None) -> None:
            value = (title_field.value or '').strip()
            if not value:
                title_field.error_text = 'Dê um nome à seção.'
                try:
                    title_field.update()
                except Exception:
                    pass
                return
            idea = (idea_field.value or '').strip() or None
            close_dialog(self.page)
            on_confirm(value, idea)

        title_field.on_submit = confirm
        fields = [
            form_field(c, name_label, title_field),
            form_field(c, idea_label, idea_field),
        ]
        if extra_fields:
            fields.extend(extra_fields)
        modal = dialog(
            c,
            title,
            fields,
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: close_dialog(self.page), variant='ghost'),
                ui.button(c, confirm_label, on_click=confirm, variant='primary'),
            ],
            subtitle=subtitle,
        )
        modal.data = {'title': title_field, 'idea': idea_field, 'confirm': confirm}
        open_dialog(self.page, modal)
        return modal

    def _prompt_new_chapter(self) -> ft.AlertDialog:
        return self._section_dialog(
            'Novo Capítulo',
            'Criar capítulo',
            lambda title, idea: self._create_section(title, idea, parent_id=None),
            title_hint='Ex.: Capítulo 1: Fundamentação Teórica',
            name_label='Título do capítulo',
            idea_label='Ideia central do capítulo (opcional)',
            subtitle='O capítulo é uma divisão principal no roteiro de escrita.',
        )

    def _prompt_new_argument(self, default_parent_id: int | None = None) -> ft.AlertDialog:
        chapters = self._root_chapters()
        if not chapters:
            return self._prompt_new_chapter()
        selected_parent = default_parent_id or chapters[0]['id']
        c = self.config
        parent_options = [(str(ch['id']), ch['title']) for ch in chapters]
        parent_selector = select_input(
            c,
            str(selected_parent),
            parent_options,
            on_select=lambda e: setattr(parent_selector, 'value', e.control.value),
        )
        parent_container = form_field(c, 'Capítulo pai', parent_selector)

        def create_arg(title: str, idea: str | None) -> None:
            chosen_parent = int(parent_selector.value) if parent_selector.value else chapters[0]['id']
            self._create_section(title, idea, parent_id=chosen_parent)

        return self._section_dialog(
            'Novo Argumento / Ideia',
            'Criar argumento',
            create_arg,
            title_hint='Ex.: 1.1 Contexto histórico',
            name_label='Nome do argumento',
            idea_label='Ideia central (opcional)',
            subtitle='O argumento fica estruturado dentro do capítulo selecionado.',
            extra_fields=[parent_container],
        )

    def _prompt_new_section(self) -> ft.AlertDialog:
        chapters = self._root_chapters()
        if not chapters:
            return self._section_dialog(
                'Nova Ideia',
                'Criar ideia',
                lambda title, idea: self._create_section(title, idea),
            )
        c = self.config
        options = [ft.dropdown.Option('root', 'Capítulo principal')] + [
            ft.dropdown.Option(str(ch['id']), f"Argumento em: {ch['title']}")
            for ch in chapters
        ]
        parent_select = ft.Dropdown(
            options=options,
            value='root',
            border_color=c.colors['border'],
            color=c.colors['text'],
            bgcolor=c.colors['surface'],
            text_size=13,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=s(10), vertical=s(8)),
        )
        parent_field = ft.Container(
            content=ft.Column(
                [
                    ui.ui_text(c, 'Nível estrutural', size=12, color=c.colors['muted'], weight=ui.W500),
                    parent_select,
                ],
                spacing=s(4),
                tight=True,
            ),
            margin=ft.Margin.only(bottom=s(8)),
        )
        return self._section_dialog(
            'Nova Ideia',
            'Criar ideia',
            lambda title, idea: self._create_section(
                title,
                idea,
                parent_id=(None if parent_select.value == 'root' else int(parent_select.value)),
            ),
            extra_fields=[parent_field],
        )

    def _prompt_edit_section(self, section: CompilationSectionRecord) -> ft.AlertDialog:
        is_chapter = not section.get('parent_id')
        name_lbl = 'Nome do capítulo' if is_chapter else 'Nome do argumento'
        title = 'Editar Capítulo' if is_chapter else 'Editar Argumento'
        return self._section_dialog(
            title,
            'Salvar alterações',
            lambda title_val, idea: self._update_section(section['id'], title_val, idea),
            section=section,
            name_label=name_lbl,
        )

    def _prompt_transfer_section(self, section: CompilationSectionRecord) -> ft.AlertDialog:
        c = self.config
        chapters = [ch for ch in self._root_chapters() if ch['id'] != section.get('parent_id')]
        options = [('root', 'Promover a Capítulo principal')] + [
            (str(ch['id']), f"Capítulo: {ch['title']}") for ch in chapters
        ]
        selector = select_input(c, options[0][0], options)

        def confirm(_e=None) -> None:
            close_dialog(self.page)
            val = selector.value
            new_parent = None if val == 'root' else int(val)
            self._transfer_section(section['id'], new_parent)
            ui.toast(
                self.page,
                self.config,
                'Argumento transferido com sucesso.',
                icon_name='folder-tree',
            )

        modal = dialog(
            c,
            f'Transferir “{section["title"]}”',
            [
                ui.ui_text(
                    c,
                    'Selecione o novo destino para este argumento:',
                    size=13,
                    color=c.colors['muted'],
                ),
                form_field(c, 'Novo destino', selector),
            ],
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: close_dialog(self.page), variant='ghost'),
                ui.button(c, 'Transferir', on_click=confirm, variant='primary'),
            ],
            width=460,
        )
        open_dialog(self.page, modal)
        return modal

    def _prompt_link_fragment_to_section(
        self,
        fragment: CompilationFragmentRecord,
    ) -> ft.AlertDialog | None:
        c = self.config
        member_section_ids = {
            f['section_id']
            for _w, f in self._all_fragments()
            if f['id'] == fragment['id'] and f['is_member']
        }
        available_sections = [
            s for s in self._sorted_sections()
            if s['id'] not in member_section_ids
        ]
        if not available_sections:
            ui.toast(
                self.page,
                self.config,
                'Este fragmento já está vinculado a todas as seções existentes.',
                icon_name='circle-info',
            )
            return None
        options = [
            (str(s['id']), f"{self._section_label(s)}. {s['title']}")
            for s in available_sections
        ]
        selector = select_input(c, options[0][0], options)

        def confirm(_e=None) -> None:
            if not selector.value:
                return
            target_sid = int(selector.value)
            close_dialog(self.page)
            self._link_fragment_to_section(fragment['id'], target_sid)

        modal = dialog(
            c,
            'Vincular também a outra seção',
            [
                ui.ui_text(
                    c,
                    'O fragmento aparecerá também na seção escolhida, com ordenação e nota próprias.',
                    size=13,
                    color=c.colors['muted'],
                ),
                form_field(c, 'Vincular a', selector),
            ],
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: close_dialog(self.page), variant='ghost'),
                ui.button(c, 'Vincular', on_click=confirm, variant='primary'),
            ],
            width=460,
        )
        open_dialog(self.page, modal)
        return modal

    def _prompt_create_section(self, fragment_id: int) -> ft.AlertDialog:
        def create(title: str, idea: str | None) -> None:
            def assign(section_id: int) -> None:
                fragment = self._find_fragment(fragment_id)
                if fragment is None:
                    return
                ready = fragment['is_member'] or self.on_fragment_membership(self.compilation['id'], fragment_id, True)
                if ready:
                    self.on_assign_fragment_to_section(self.compilation['id'], fragment_id, section_id)

            self._create_section(title, idea, after_create=assign)

        return self._section_dialog(
            'Novo capítulo com este fragmento',
            'Criar e adicionar fragmento',
            create,
            subtitle='O fragmento entra no caderno dentro da nova seção.',
        )
