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
from src.utils.fa import fa_icon
from .common import (
    close_dialog,
    dialog,
    form_field,
    open_dialog,
    select_input,
    text_input,
)
from src.utils.control_safety import safe_update


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
                safe_update(title_field)
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

    def _prompt_allocate_fragment(
        self,
        fragment: CompilationFragmentRecord,
    ) -> ft.AlertDialog:
        """Alocação por busca, com vínculo em várias ideias ao mesmo tempo."""
        c = self.config
        fragment_id = fragment['id']
        current = set(self._fragment_section_ids(fragment_id))
        rows_host = ft.Column(spacing=s(1), tight=True, scroll=ft.ScrollMode.AUTO)

        def paint(query: str = '') -> None:
            nonlocal current
            current = set(self._fragment_section_ids(fragment_id))
            term = (query or '').strip().casefold()
            controls: list[ft.Control] = []

            def add_row(section: CompilationSectionRecord, depth: int) -> None:
                if term and term not in section['title'].casefold():
                    return
                selected = section['id'] in current
                glyph = fa_icon(
                    'circle-check' if selected else 'circle',
                    size=s(12),
                    color=c.colors['gold'] if selected else c.colors['faint'],
                    style='regular',
                )
                label = ui.ui_text(
                    c,
                    self._section_path_label(section),
                    size=13,
                    weight=ui.W600 if selected else ui.W500,
                    color=c.colors['text'] if selected else c.colors['muted'],
                    expand=True,
                )
                box = ui.hover_surface(
                    c,
                    ft.Row(
                        [
                            glyph,
                            ft.Container(label, padding=ft.Padding.only(left=s(depth * 14))),
                        ],
                        spacing=s(8),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    on_click=lambda _e, sid=section['id']: toggle(sid),
                    selected=selected,
                    padding=ft.Padding.symmetric(horizontal=s(10)),
                    height=s(34),
                    accent_left=True,
                )
                controls.append(box)

            for chapter in self._root_chapters():
                add_row(chapter, 0)
                for child in self._child_sections(chapter['id']):
                    add_row(child, 1)
            if not controls:
                controls.append(
                    ui.meta_text(
                        c,
                        'Nenhuma ideia corresponde à busca.' if term else 'Nenhuma ideia criada ainda.',
                        max_lines=2,
                    )
                )
            rows_host.controls = controls
            safe_update(rows_host)

        def toggle(section_id: int) -> None:
            self._toggle_fragment_section(fragment_id, section_id)
            self._reload()
            paint(search.value or '')

        closed = {'done': False}

        def create_new(_e=None) -> None:
            closed['done'] = True
            close_dialog(self.page)
            self._prompt_create_section(fragment_id)

        def finish(_e=None) -> None:
            closed['done'] = True
            close_dialog(self.page)
            self.refresh()

        def dismissed(_e=None) -> None:
            if not closed['done']:
                closed['done'] = True
                self.refresh()

        search = ui.search_field(
            c,
            'Buscar capítulo ou argumento',
            on_change=lambda event: paint(event.control.value or ''),
            width=None,
            expand=False,
            autofocus=True,
        )
        # ``expand`` não deve competir com a altura de uma linha no diálogo.
        search.multiline = False
        search.min_lines = 1
        search.max_lines = 1
        paint()
        modal = dialog(
            c,
            'Alocar fragmento',
            [
                ui.ui_text(
                    c,
                    'Marque uma ou várias ideias. O fragmento pode pertencer a mais de uma.',
                    size=13,
                    color=c.colors['muted'],
                    max_lines=2,
                ),
                search,
                ft.Container(rows_host, height=s(300)),
                ui.button(
                    c,
                    'Nova ideia com este fragmento',
                    on_click=create_new,
                    icon_name='plus',
                    variant='ghost',
                    small=True,
                ),
            ],
            [
                ui.button(c, 'Concluir', on_click=finish, variant='primary'),
            ],
            width=520,
            dismissible=True,
            on_dismiss=dismissed,
        )
        modal.data = {
            'paint': paint,
            'toggle': toggle,
            'finish': finish,
            'search': search,
            'dismiss': dismissed,
        }
        open_dialog(self.page, modal)
        return modal

    def _prompt_link_fragment_to_section(
        self,
        fragment: CompilationFragmentRecord,
    ) -> ft.AlertDialog | None:
        return self._prompt_allocate_fragment(fragment)

    def _prompt_create_section(self, fragment_id: int) -> ft.AlertDialog:
        def create(title: str, idea: str | None) -> None:
            def assign(section_id: int) -> None:
                fragment = self._find_fragment(fragment_id)
                if fragment is None:
                    return
                ready = fragment['is_member'] or self.on_fragment_membership(self.compilation['id'], fragment_id, True)
                if ready:
                    on_link = getattr(self, 'on_link_fragment_to_section', None)
                    if on_link is not None:
                        on_link(self.compilation['id'], fragment_id, section_id)
                    else:
                        self.on_assign_fragment_to_section(self.compilation['id'], fragment_id, section_id)

            self._create_section(title, idea, after_create=assign)

        return self._section_dialog(
            'Novo capítulo com este fragmento',
            'Criar e adicionar fragmento',
            create,
            subtitle='O fragmento entra no caderno dentro da nova seção.',
        )
