from collections.abc import Awaitable, Callable
from functools import partial
from typing import TypeVar

import flet as ft

from src.contracts import (
    CompilationPayload,
    CompilationRecord,
    CompilationFragmentRecord,
    CompilationSectionRecord,
    CompilationWorkRecord,
    FragmentRecord,
)
from src.utils.fragment_reference import fragment_abnt_notation
from src.utils.types import ViewConfig
from src.utils.view_styles import (
    button_text_style,
    dropdown_style,
    text_field_style,
)

EventControl = TypeVar('EventControl', bound=ft.Control)


def _control_list(*controls: ft.Control) -> list[ft.Control]:
    return list(controls)


class CompilationHubComposer:
    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        compilation: CompilationRecord,
        refresh_compilations: Callable[[], list[CompilationRecord]],
        search_works: Callable[[str], list[tuple[int, str]]],
        on_update: Callable[[int, CompilationPayload], bool],
        on_add_work: Callable[[int, int], bool],
        on_remove_work: Callable[[int, int], bool],
        on_reorder_works: Callable[[int, list[int]], bool],
        on_fragment_membership: Callable[[int, int, bool], bool],
        on_fragment_note: Callable[[int, int, str | None], bool],
        on_create_section: Callable[
            [int, str, str | None], int | None
        ],
        on_update_section: Callable[[int, int, str, str | None], bool],
        on_delete_section: Callable[[int, int], bool],
        on_reorder_sections: Callable[[int, list[int]], bool],
        on_assign_fragment_to_section: Callable[
            [int, int, int | None], bool
        ],
        on_reorder_section_fragments: Callable[
            [int, int, list[int]], bool
        ],
        on_copy_caderno: Callable[[str], Awaitable[None]],
        on_create_work: Callable[[int], None],
        on_edit_work: Callable[[int, int], None],
        on_create_fragment: Callable[[int, int], None],
        on_edit_fragment: Callable[[int, FragmentRecord], None],
        on_close: Callable[[], None],
        on_data_changed: Callable[[CompilationRecord], None],
    ) -> None:
        self.page = page
        self.config = config
        self.compilation = compilation
        self.refresh_compilations = refresh_compilations
        self.search_works = search_works
        self.on_update = on_update
        self.on_add_work = on_add_work
        self.on_remove_work = on_remove_work
        self.on_reorder_works = on_reorder_works
        self.on_fragment_membership = on_fragment_membership
        self.on_fragment_note = on_fragment_note
        self.on_create_section = on_create_section
        self.on_update_section = on_update_section
        self.on_delete_section = on_delete_section
        self.on_reorder_sections = on_reorder_sections
        self.on_assign_fragment_to_section = on_assign_fragment_to_section
        self.on_reorder_section_fragments = on_reorder_section_fragments
        self.on_copy_caderno = on_copy_caderno
        self.on_create_work = on_create_work
        self.on_edit_work = on_edit_work
        self.on_create_fragment = on_create_fragment
        self.on_edit_fragment = on_edit_fragment
        self.on_close = on_close
        self.on_data_changed = on_data_changed
        self.selected_tab = 1
        self.editing_outline = False
        self.new_section_title = ft.TextField(
            label='Nome da seção/ideia *',
            hint_text='Ex.: Argumento central',
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            max_length=150,
            **text_field_style(config),
        )
        self.new_section_idea = ft.TextField(
            label='Ideia central (opcional)',
            hint_text='Que papel esta seção terá no texto?',
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            max_length=2000,
            **text_field_style(config),
        )
        self.work_search = ft.TextField(
            label='Adicionar obra existente',
            hint_text='Busque pelo título no Acervo',
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            on_change=self._search_work_matches,
            **text_field_style(config),
        )
        self.work_matches = ft.Column(
            spacing=2,
            tight=True,
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.name_field = ft.TextField(
            label='Nome da compilação *',
            value=compilation['name'],
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            **text_field_style(config),
        )
        self.description_field = ft.TextField(
            label='Descrição (opcional)',
            value=compilation['description'] or '',
            multiline=True,
            min_lines=3,
            max_lines=6,
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            **text_field_style(config),
        )
        dialog_actions: list[ft.Control] = [
            ft.TextButton(
                content=ft.Text(
                    'Fechar',
                    color=config.colors['text'],
                    font_family=config.font_families['montserrat'],
                    size=config.font_sizes['montserrat_medium'],
                    weight=config.font_weights['montserrat_normal'],
                ),
                style=ft.ButtonStyle(
                    text_style=button_text_style(config),
                ),
                on_click=self._close,
            )
        ]
        self.dialog = ft.AlertDialog(
            modal=True,
            bgcolor=config.colors['surface'],
            content=self._compose_content(),
            actions=dialog_actions,
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(
                radius=config.ui['card_radius']
            ),
            content_padding=config.ui['modal_content_padding'],
            on_dismiss=self.on_close,
        )

    def _close(self) -> None:
        self.dialog.open = False
        self.on_close()
        self.page.update()

    def _run_click_action(
        self,
        event: ft.Event[EventControl],
        action: Callable[[], object],
    ) -> None:
        del event
        action()

    def open(self) -> None:
        self.page.show_dialog(self.dialog)

    def refresh(self) -> None:
        compilation = next(
            (
                record
                for record in self.refresh_compilations()
                if record['id'] == self.compilation['id']
            ),
            None,
        )
        if compilation is None:
            self.dialog.open = False
            self.on_close()
            self.page.update()
            return
        self.compilation = compilation
        self.on_data_changed(compilation)
        self.name_field.value = compilation['name']
        self.description_field.value = compilation['description'] or ''
        self.work_search.value = ''
        self.work_matches.controls = []
        self.work_matches.visible = False
        self.new_section_title.value = ''
        self.new_section_idea.value = ''
        self.dialog.content = self._compose_content()
        self.page.update()

    def _save_details(self, event: ft.Event[ft.Button]) -> None:
        del event
        if self.on_update(self.compilation['id'], {
            'name': self.name_field.value or '',
            'description': self.description_field.value,
        }):
            self.refresh()

    def _search_work_matches(
        self,
        event: ft.Event[ft.TextField],
    ) -> None:
        query = (event.control.value or '').strip()
        if len(query) < 2:
            self.work_matches.controls = []
            self.work_matches.visible = False
            self.page.update()
            return
        linked_ids = {
            work['id'] for work in self.compilation['works']
        }
        matches = [
            (work_id, title)
            for work_id, title in self.search_works(query)
            if work_id not in linked_ids
        ][:8]
        self.work_matches.controls = [
            ft.TextButton(
                content=ft.Text(
                    value=title,
                    color=self.config.colors['text'],
                    font_family=self.config.font_families[
                        'montserrat'
                    ],
                    size=self.config.font_sizes['montserrat_medium'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
                style=ft.ButtonStyle(
                    text_style=button_text_style(self.config),
                ),
                on_click=lambda event, resource_id=work_id: (
                    self._run_click_action(
                        event,
                        lambda: self._add_work(resource_id),
                    )
                ),
            )
            for work_id, title in matches
        ]
        if not matches:
            self.work_matches.controls = [
                ft.Text(
                    value='Nenhuma obra disponível para adicionar.',
                    color=self.config.colors['muted'],
                )
            ]
        self.work_matches.visible = True
        self.page.update()

    def _add_work(self, bib_res_id: int) -> None:
        if self.on_add_work(self.compilation['id'], bib_res_id):
            self.refresh()

    def _remove_work(self, bib_res_id: int) -> None:
        if self.on_remove_work(self.compilation['id'], bib_res_id):
            self.refresh()

    def _move_work(self, index: int, offset: int) -> None:
        work_ids = [work['id'] for work in self.compilation['works']]
        target_index = index + offset
        if target_index < 0 or target_index >= len(work_ids):
            return
        work_ids[index], work_ids[target_index] = (
            work_ids[target_index],
            work_ids[index],
        )
        if self.on_reorder_works(self.compilation['id'], work_ids):
            self.refresh()

    def _save_fragment_note(
        self,
        fragment_id: int,
        note: str | None,
    ) -> None:
        if self.on_fragment_note(
            self.compilation['id'],
            fragment_id,
            note.strip() if isinstance(note, str) else None,
        ):
            self.refresh()

    def _create_section(
        self,
        event: ft.Event[ft.Button],
        after_create: Callable[[int], None] | None = None,
    ) -> None:
        del event
        section_id = self.on_create_section(
            self.compilation['id'],
            self.new_section_title.value or '',
            self.new_section_idea.value,
        )
        if section_id is None:
            return
        if after_create is not None:
            after_create(section_id)
        else:
            self.refresh()

    def _toggle_outline_edit(
        self,
        event: ft.Event[ft.Button],
    ) -> None:
        del event
        if self.editing_outline:
            self.editing_outline = False
            self.refresh()
            return
        self.editing_outline = True
        self.dialog.content = self._compose_content()
        self.page.update()

    def _set_fragment_destination(
        self,
        fragment_id: int,
        destination: str,
    ) -> None:
        if destination == 'create_section':
            self._prompt_create_section(fragment_id)
            return
        if destination == 'not_selected':
            if self.on_fragment_membership(
                self.compilation['id'],
                fragment_id,
                False,
            ):
                self.refresh()
            return
        section_id = (
            None if destination == 'unassigned' else int(destination)
        )
        fragment = next(
            (
                fragment
                for work in self.compilation['works']
                for fragment in work['fragments']
                if fragment['id'] == fragment_id
            ),
            None,
        )
        if fragment is None:
            return
        if not fragment['is_member']:
            if not self.on_fragment_membership(
                self.compilation['id'],
                fragment_id,
                True,
            ):
                return
        if section_id is None and not fragment['is_member']:
            self.refresh()
            return
        if self.on_assign_fragment_to_section(
            self.compilation['id'],
            fragment_id,
            section_id,
        ):
            self.refresh()
        elif not fragment['is_member']:
            self.refresh()

    def _prompt_create_section(self, fragment_id: int) -> None:
        title = ft.TextField(
            label='Nome da seção/ideia *',
            hint_text='Ex.: Argumento central',
            filled=True,
            fill_color=self.config.colors['surface'],
            max_length=150,
            **text_field_style(self.config),
        )
        central_idea = ft.TextField(
            label='Ideia central (opcional)',
            hint_text='Que papel esta seção terá no texto?',
            multiline=True,
            min_lines=2,
            max_lines=4,
            max_length=2000,
            filled=True,
            fill_color=self.config.colors['surface'],
            **text_field_style(self.config),
        )
        create_dialog: ft.AlertDialog

        def create(event: ft.Event[ft.Button]) -> None:
            del event

            def assign(section_id: int) -> None:
                fragment = next(
                    (
                        fragment
                        for work in self.compilation['works']
                        for fragment in work['fragments']
                        if fragment['id'] == fragment_id
                    ),
                    None,
                )
                if fragment is not None:
                    membership_ready = (
                        fragment['is_member']
                        or self.on_fragment_membership(
                            self.compilation['id'],
                            fragment_id,
                            True,
                        )
                    )
                    if membership_ready:
                        self.on_assign_fragment_to_section(
                            self.compilation['id'],
                            fragment_id,
                            section_id,
                        )
                self.page.pop_dialog()
                self.refresh()

            section_id = self.on_create_section(
                self.compilation['id'],
                title.value or '',
                central_idea.value,
            )
            if section_id is not None:
                assign(section_id)

        create_actions: list[ft.Control] = [
            ft.TextButton(
                content=ft.Text(
                    'Cancelar',
                    color=self.config.colors['text'],
                    font_family=self.config.font_families[
                        'montserrat'
                    ],
                    size=self.config.font_sizes[
                        'montserrat_medium'
                    ],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
                style=ft.ButtonStyle(
                    text_style=button_text_style(self.config),
                ),
                on_click=lambda: self.page.pop_dialog(),
            ),
            ft.FilledButton(
                content=ft.Text(
                    'Criar e adicionar fragmento',
                    color=self.config.colors['bg'],
                    font_family=self.config.font_families['montserrat'],
                    size=self.config.font_sizes['montserrat_medium'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
                bgcolor=self.config.colors['gold'],
                style=ft.ButtonStyle(
                    text_style=button_text_style(self.config),
                ),
                on_click=create,
            ),
        ]
        create_dialog = ft.AlertDialog(
            modal=True,
            bgcolor=self.config.colors['surface'],
            title=ft.Text(
                value='Criar ideia e organizar fragmento',
                color=self.config.colors['gold'],
                font_family=self.config.font_families['cormorant'],
                size=self.config.font_sizes['cormorant_medium'],
                weight=self.config.font_weights['cormorant_semibold'],
            ),
            content=ft.Column(
                controls=[title, central_idea],
                tight=True,
                width=560,
                spacing=self.config.ui['control_gap'],
            ),
            actions=create_actions,
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(
                radius=self.config.ui['card_radius']
            ),
            content_padding=self.config.ui['modal_content_padding'],
        )
        self.page.show_dialog(create_dialog)

    def _update_section(
        self,
        section_id: int,
        title: str,
        central_idea: str | None,
    ) -> None:
        if self.on_update_section(
            self.compilation['id'],
            section_id,
            title,
            central_idea,
        ):
            self.refresh()

    def _delete_section(self, section_id: int) -> None:
        if self.on_delete_section(self.compilation['id'], section_id):
            self.refresh()

    def _move_section(self, index: int, offset: int) -> None:
        sections = sorted(
            self.compilation['sections'],
            key=lambda section: (section['position'], section['id']),
        )
        target_index = index + offset
        if target_index < 0 or target_index >= len(sections):
            return
        section_ids = [section['id'] for section in sections]
        section_ids[index], section_ids[target_index] = (
            section_ids[target_index],
            section_ids[index],
        )
        if self.on_reorder_sections(
            self.compilation['id'],
            section_ids,
        ):
            self.refresh()

    def _move_section_fragment(
        self,
        section_id: int,
        current_index: int,
        offset: int,
    ) -> None:
        section = next(
            (
                item for item in self.compilation['sections']
                if item['id'] == section_id
            ),
            None,
        )
        if section is None:
            return
        members = self._section_fragments(section_id)
        if current_index < 0 or current_index >= len(members):
            return
        target_index = current_index + offset
        if target_index < 0 or target_index >= len(members):
            return
        fragment_ids = [fragment['id'] for fragment in members]
        fragment_ids[current_index], fragment_ids[target_index] = (
            fragment_ids[target_index],
            fragment_ids[current_index],
        )
        if self.on_reorder_section_fragments(
            self.compilation['id'],
            section_id,
            fragment_ids,
        ):
            self.refresh()

    def _caderno_text(self) -> str:
        lines = [self.compilation['name']]
        sections = sorted(
            self.compilation['sections'],
            key=lambda section: (section['position'], section['id']),
        )
        for section in sections:
            fragments = self._section_fragments(section['id'])
            lines.extend(('', f"## {section['title']}", ''))
            if section['central_idea']:
                lines.extend((section['central_idea'], ''))
            for fragment in fragments:
                fragment_type = (
                    'Citação'
                    if fragment['fragment_type'] == 'quote'
                    else 'Comentário'
                )
                lines.extend((
                    f"{fragment_type}: {fragment['excerpt']}",
                    fragment_abnt_notation(fragment),
                ))
                if fragment['work_note']:
                    lines.append(
                        f"Nota de articulação: {fragment['work_note']}"
                    )
                lines.append('')
        unassigned = self._unassigned_fragments()
        if unassigned:
            lines.extend(('', '## A organizar', ''))
            for work, fragment in unassigned:
                lines.extend((
                    f"### {work['title']}",
                    f"{fragment['excerpt']}",
                    fragment_abnt_notation(fragment),
                ))
                if fragment['work_note']:
                    lines.append(
                        f"Nota de articulação: {fragment['work_note']}"
                    )
                lines.append('')
        return '\n'.join(lines).strip()

    def _section_fragments(
        self,
        section_id: int,
    ) -> list[CompilationFragmentRecord]:
        fragments = [
            fragment
            for work in self.compilation['works']
            for fragment in work['fragments']
            if (
                fragment['is_member']
                and fragment['section_id'] == section_id
            )
        ]
        return sorted(
            fragments,
            key=lambda fragment: (
                fragment['project_position']
                if fragment['project_position'] is not None
                else fragment['id']
            ),
        )

    def _unassigned_fragments(
        self,
    ) -> list[tuple[CompilationWorkRecord, CompilationFragmentRecord]]:
        return [
            (work, fragment)
            for work in self.compilation['works']
            for fragment in work['fragments']
            if fragment['is_member'] and fragment['section_id'] is None
        ]

    def _outline_dropdown_option(
        self,
        key: str,
        label: str,
    ) -> ft.DropdownOption:
        return ft.DropdownOption(
            key=key,
            text=label,
            content=ft.Text(
                value=label,
                color=self.config.colors['text'],
                font_family=self.config.font_families['montserrat'],
                size=self.config.font_sizes['montserrat_medium'],
                weight=self.config.font_weights['montserrat_normal'],
            ),
        )

    def _compose_section(
        self,
        section: CompilationSectionRecord,
        index: int,
    ) -> ft.Container:
        sections = sorted(
            self.compilation['sections'],
            key=lambda item: (item['position'], item['id']),
        )
        title_field = ft.TextField(
            label='Nome da seção/ideia *',
            value=section['title'],
            max_length=150,
            expand=True,
            **text_field_style(self.config),
        )
        idea_field = ft.TextField(
            label='Ideia central (opcional)',
            value=section['central_idea'] or '',
            hint_text='Que papel esta seção terá no texto?',
            multiline=True,
            min_lines=1,
            max_lines=3,
            max_length=2000,
            expand=True,
            **text_field_style(self.config),
        )
        fragment_work_titles = {
            fragment['id']: work['title']
            for work in self.compilation['works']
            for fragment in work['fragments']
        }
        fragments = self._section_fragments(section['id'])
        section_heading: ft.Control = (
            title_field
            if self.editing_outline
            else ft.Text(
                value=section['title'],
                color=self.config.colors['gold'],
                size=self.config.font_sizes['cormorant_medium'],
                font_family=self.config.font_families['cormorant'],
                weight=self.config.font_weights['cormorant_semibold'],
            )
        )
        section_controls: list[ft.Control] = []
        section_controls.append(
            ft.Row(
                controls=_control_list(
                    section_heading,
                    *(
                        [
                            ft.IconButton(
                                icon=ft.Icons.ARROW_UPWARD,
                                tooltip='Mover ideia para cima',
                                disabled=index == 0,
                                on_click=lambda event, current=index: (
                                    self._run_click_action(
                                        event,
                                        lambda: self._move_section(
                                            current,
                                            -1,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ARROW_DOWNWARD,
                                tooltip='Mover ideia para baixo',
                                disabled=index >= len(sections) - 1,
                                on_click=lambda event, current=index: (
                                    self._run_click_action(
                                        event,
                                        lambda: self._move_section(
                                            current,
                                            1,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip=(
                                    'Remover ideia; devolver fragmentos a '
                                    'A organizar'
                                ),
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda event, current=section['id']: (
                                    self._run_click_action(
                                        event,
                                        lambda: self._delete_section(
                                            current
                                        ),
                                    )
                                ),
                            ),
                        ]
                        if self.editing_outline
                        else []
                    ),
                ),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        if self.editing_outline:
            section_controls.append(idea_field)
            section_controls.append(
                ft.Row(
                    controls=_control_list(
                        ft.FilledButton(
                            content=ft.Text(
                                'Salvar ideia',
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
                            on_click=lambda event, current=section['id'],
                            title=title_field,
                            idea=idea_field: self._run_click_action(
                                event,
                                lambda: self._update_section(
                                    current,
                                    title.value or '',
                                    idea.value,
                                ),
                            ),
                        )
                    ),
                    alignment=ft.MainAxisAlignment.END,
                ),
            )
        elif section['central_idea']:
            section_controls.append(
                ft.Text(
                    value=section['central_idea'],
                    color=self.config.colors['text'],
                    size=self.config.font_sizes['montserrat_medium'],
                    font_family=self.config.font_families['montserrat'],
                    selectable=True,
                )
            )
        for fragment_index, fragment in enumerate(fragments):
            move_section_fragment = self._move_section_fragment
            fragment_type_label = (
                'Citação'
                if fragment['fragment_type'] == 'quote'
                else 'Comentário'
            )
            fragment_details: list[ft.Control] = [
                ft.Text(
                    value=fragment_work_titles[fragment['id']],
                    color=self.config.colors['gold'],
                    size=self.config.font_sizes['montserrat_medium'],
                    font_family=self.config.font_families['montserrat'],
                    weight=self.config.font_weights['montserrat_semibold'],
                ),
                ft.Text(
                    value=(
                        f'{fragment_type_label}: {fragment["excerpt"]}'
                    ),
                    color=self.config.colors['text'],
                    size=self.config.font_sizes['montserrat_medium'],
                    font_family=self.config.font_families['montserrat'],
                    selectable=True,
                ),
                ft.Text(
                    value=fragment_abnt_notation(fragment),
                    color=self.config.colors['muted'],
                    size=self.config.font_sizes['montserrat_medium'],
                    font_family=self.config.font_families['montserrat'],
                    selectable=True,
                ),
            ]
            if self.editing_outline:
                fragment_details.append(
                    ft.TextField(
                        label='Nota de articulação (opcional)',
                        hint_text='Por que este trecho importa para a ideia?',
                        value=fragment['work_note'] or '',
                        multiline=True,
                        min_lines=1,
                        max_lines=3,
                        max_length=2000,
                        expand=True,
                        on_blur=lambda event, current_id=fragment['id']: (
                            self._save_fragment_note(
                                current_id,
                                event.control.value,
                            )
                        ),
                        **text_field_style(self.config),
                    )
                )
            elif fragment['work_note']:
                fragment_details.append(
                    ft.Text(
                        value=f"Nota de articulação: {fragment['work_note']}",
                        color=self.config.colors['muted'],
                        size=self.config.font_sizes['montserrat_medium'],
                        font_family=self.config.font_families['montserrat'],
                        selectable=True,
                    )
                )
            section_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=_control_list(
                            ft.Column(
                                controls=fragment_details,
                                spacing=4,
                                expand=True,
                                horizontal_alignment=(
                                    ft.CrossAxisAlignment.STRETCH
                                ),
                            ),
                            *(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.ARROW_UPWARD,
                                        tooltip='Mover fragmento para cima',
                                        disabled=fragment_index == 0,
                                        on_click=lambda event, current=(
                                            fragment_index
                                        ), current_section=section['id']: (
                                            self._run_click_action(
                                                event,
                                                partial(
                                                    move_section_fragment,
                                                    current_section,
                                                    current,
                                                    -1,
                                                ),
                                            )
                                        ),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.ARROW_DOWNWARD,
                                        tooltip='Mover fragmento para baixo',
                                        disabled=(
                                            fragment_index
                                            >= len(fragments) - 1
                                        ),
                                        on_click=lambda event, current=(
                                            fragment_index
                                        ), current_section=section['id']: (
                                            self._run_click_action(
                                                event,
                                                partial(
                                                    move_section_fragment,
                                                    current_section,
                                                    current,
                                                    1,
                                                ),
                                            )
                                        ),
                                    ),
                                ]
                                if self.editing_outline
                                else []
                            ),
                        ),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=self.config.ui['card_padding'],
                    bgcolor=self.config.colors['bg'],
                    border=ft.Border.all(1, self.config.colors['border']),
                    border_radius=self.config.ui['card_radius'],
                )
            )
        if not fragments:
            section_controls.append(
                ft.Text(
                    value=(
                        'Nenhum fragmento nesta ideia. Você pode atribuí-los '
                        'na aba Obras e fragmentos.'
                    ),
                    color=self.config.colors['muted'],
                    size=self.config.font_sizes['montserrat_medium'],
                    font_family=self.config.font_families[
                        'montserrat'
                    ],
                )
            )
        return ft.Container(
            content=ft.Column(
                controls=section_controls,
                spacing=self.config.ui['control_gap'],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['surface'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
        )

    def _compose_caderno_ideas(self) -> ft.Control:
        sections = sorted(
            self.compilation['sections'],
            key=lambda section: (section['position'], section['id']),
        )
        edit_label = (
            'Concluir edição'
            if self.editing_outline
            else 'Editar caderno'
        )
        edit_action = ft.FilledButton(
            content=ft.Text(
                edit_label,
                color=self.config.colors['bg'],
                font_family=self.config.font_families[
                    'montserrat'
                ],
                size=self.config.font_sizes['montserrat_medium'],
                weight=self.config.font_weights['montserrat_normal'],
            ),
            bgcolor=self.config.colors['gold'],
            style=ft.ButtonStyle(
                text_style=button_text_style(self.config),
            ),
            on_click=self._toggle_outline_edit,
        )
        controls: list[ft.Control] = []
        controls.append(
            ft.Row(
                controls=_control_list(
                    ft.Column(
                        controls=[
                            ft.Text(
                                value='Esqueleto de escrita',
                                color=self.config.colors['text'],
                                size=self.config.font_sizes[
                                    'cormorant_medium'
                                ],
                                font_family=(
                                    self.config.font_families['cormorant']
                                ),
                                weight=self.config.font_weights[
                                    'cormorant_semibold'
                                ],
                            ),
                            ft.Text(
                                value=(
                                    'Ideias e fragmentos organizados para '
                                    'orientar a escrita deste projeto.'
                                ),
                                color=self.config.colors['muted'],
                                size=self.config.font_sizes[
                                    'montserrat_medium'
                                ],
                                font_family=(
                                    self.config.font_families['montserrat']
                                ),
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.FilledButton(
                        content=ft.Text(
                            'Copiar esqueleto',
                            color=self.config.colors['bg'],
                            font_family=self.config.font_families[
                                'montserrat'
                            ],
                            size=self.config.font_sizes[
                                'montserrat_medium'
                            ],
                            weight=self.config.font_weights[
                                'montserrat_normal'
                            ],
                        ),
                        bgcolor=self.config.colors['gold'],
                        disabled=not sections and not any(
                            fragment['is_member']
                            for work in self.compilation['works']
                            for fragment in work['fragments']
                        ),
                        style=ft.ButtonStyle(
                            text_style=button_text_style(self.config),
                        ),
                        on_click=self._copy_caderno,
                    ),
                    edit_action,
                ),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        if self.editing_outline:
            controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=_control_list(
                            ft.Text(
                                value='Nova ideia ou seção',
                                color=self.config.colors['gold'],
                                size=self.config.font_sizes[
                                    'cormorant_medium'
                                ],
                                font_family=(
                                    self.config.font_families['cormorant']
                                ),
                                weight=self.config.font_weights[
                                    'cormorant_semibold'
                                ],
                            ),
                            ft.Row(
                                controls=_control_list(
                                    self.new_section_title,
                                    self.new_section_idea,
                                ),
                            ),
                            ft.Row(
                                controls=_control_list(
                                    ft.FilledButton(
                                        content=ft.Text(
                                            'Criar ideia',
                                            color=self.config.colors['bg'],
                                            font_family=(
                                                self.config.font_families[
                                                    'montserrat'
                                                ]
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
                                            text_style=button_text_style(
                                                self.config
                                            ),
                                        ),
                                        on_click=self._create_section,
                                    )
                                ),
                                alignment=ft.MainAxisAlignment.END,
                            ),
                        ),
                        spacing=self.config.ui['control_gap'],
                        horizontal_alignment=(
                            ft.CrossAxisAlignment.STRETCH
                        ),
                    ),
                    padding=self.config.ui['card_padding'],
                    bgcolor=self.config.colors['surface'],
                    border=ft.Border.all(1, self.config.colors['border']),
                    border_radius=self.config.ui['card_radius'],
                )
            )
        unassigned = self._unassigned_fragments()
        if unassigned:
            controls.append(
                ft.Column(
                    controls=[
                        ft.Text(
                            value=f'A organizar ({len(unassigned)})',
                            color=self.config.colors['gold'],
                            size=self.config.font_sizes['cormorant_medium'],
                            font_family=(
                                self.config.font_families['cormorant']
                            ),
                            weight=self.config.font_weights[
                                'cormorant_semibold'
                            ],
                        ),
                        *[
                            self._compose_unassigned_fragment(work, fragment)
                            for work, fragment in unassigned
                        ],
                    ],
                    spacing=self.config.ui['control_gap'],
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                )
            )
        controls.extend(
            self._compose_section(section, index)
            for index, section in enumerate(sections)
        )
        if not sections:
            controls.append(
                ft.Text(
                    value=(
                        'Ainda não há ideias. Use “Editar caderno” para '
                        'criar a primeira ideia ou atribua um fragmento a '
                        'uma nova ideia na aba Obras e fragmentos.'
                    ),
                    color=self.config.colors['muted'],
                    size=self.config.font_sizes['montserrat_medium'],
                    font_family=self.config.font_families['montserrat'],
                )
            )
        return ft.Column(
            controls=controls,
            spacing=self.config.ui['grid_gap'],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _compose_unassigned_fragment(
        self,
        work: CompilationWorkRecord,
        fragment: CompilationFragmentRecord,
    ) -> ft.Container:
        fragment_type_label = (
            'Citação'
            if fragment['fragment_type'] == 'quote'
            else 'Comentário'
        )
        details: list[ft.Control] = [
            ft.Text(
                value=work['title'],
                color=self.config.colors['gold'],
                size=self.config.font_sizes['montserrat_medium'],
                font_family=self.config.font_families['montserrat'],
                weight=self.config.font_weights['montserrat_semibold'],
            ),
            ft.Text(
                value=(
                    f'{fragment_type_label}: {fragment["excerpt"]}'
                ),
                color=self.config.colors['text'],
                size=self.config.font_sizes['montserrat_medium'],
                font_family=self.config.font_families['montserrat'],
                selectable=True,
            ),
            ft.Text(
                value=fragment_abnt_notation(fragment),
                color=self.config.colors['muted'],
                size=self.config.font_sizes['montserrat_medium'],
                font_family=self.config.font_families['montserrat'],
                selectable=True,
            ),
        ]
        if self.editing_outline:
            details.append(
                ft.TextField(
                    label='Nota de articulação (opcional)',
                    hint_text='Por que este trecho importa para o projeto?',
                    value=fragment['work_note'] or '',
                    multiline=True,
                    min_lines=1,
                    max_lines=3,
                    max_length=2000,
                    expand=True,
                    on_blur=lambda event, current_id=fragment['id']: (
                        self._save_fragment_note(
                            current_id,
                            event.control.value,
                        )
                    ),
                    **text_field_style(self.config),
                )
            )
        elif fragment['work_note']:
            details.append(
                ft.Text(
                    value=f"Nota de articulação: {fragment['work_note']}",
                    color=self.config.colors['muted'],
                    size=self.config.font_sizes['montserrat_medium'],
                    font_family=self.config.font_families['montserrat'],
                    selectable=True,
                )
            )
        return ft.Container(
            content=ft.Column(
                controls=_control_list(*details),
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['bg'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
        )

    def _compose_caderno(self) -> ft.Control:
        return ft.Container(
            content=self._compose_caderno_ideas(),
            padding=ft.Padding.only(top=12),
            expand=True,
        )

    async def _copy_caderno(self, event: ft.Event[ft.Button]) -> None:
        del event
        has_selected_fragments = any(
            fragment['is_member']
            for work in self.compilation['works']
            for fragment in work['fragments']
        )
        if not has_selected_fragments and not self.compilation['sections']:
            return
        await self.on_copy_caderno(self._caderno_text())

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

    def _compose_fragment(
        self,
        fragment: CompilationFragmentRecord,
    ) -> ft.Container:
        location = ', '.join(
            part
            for part in (
                fragment['location_type'],
                fragment['location_value'],
            )
            if part
        )
        fragment_type = (
            'Citação' if fragment['fragment_type'] == 'quote' else 'Comentário'
        )
        is_member = fragment['is_member']
        destination_value = (
            str(fragment['section_id'])
            if fragment['section_id'] is not None
            else 'unassigned'
        ) if is_member else 'not_selected'
        section_options = [
            self._outline_dropdown_option(
                str(section['id']),
                section['title'],
            )
            for section in sorted(
                self.compilation['sections'],
                key=lambda item: (item['position'], item['id']),
            )
        ]
        destination_control = ft.Dropdown(
            label='Destino no caderno',
            value=destination_value,
            options=[
                self._outline_dropdown_option(
                    'not_selected',
                    'Fora do caderno',
                ),
                self._outline_dropdown_option(
                    'unassigned',
                    'A organizar',
                ),
                *section_options,
                self._outline_dropdown_option(
                    'create_section',
                    '+ Criar nova ideia…',
                ),
            ],
            on_select=lambda event, current_id=fragment['id']: (
                self._set_fragment_destination(
                    current_id,
                    event.control.value,
                )
                if event.control.value is not None
                else None
            ),
            expand=True,
            **{
                **dropdown_style(self.config),
                'text_style': ft.TextStyle(
                    color=self.config.colors['text'],
                    font_family=self.config.font_families['montserrat'],
                    size=self.config.font_sizes['montserrat_medium'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
                'label_style': ft.TextStyle(
                    color=self.config.colors['muted'],
                    font_family=self.config.font_families['montserrat'],
                    size=self.config.font_sizes['montserrat_small'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
            },
        )
        fragment_details: list[ft.Control] = [
            ft.Text(
                value=fragment_type,
                color=self.config.colors['gold'],
                size=self.config.font_sizes['montserrat_medium'],
                font_family=self.config.font_families['montserrat'],
            ),
            ft.Text(
                value=fragment['excerpt'],
                color=self.config.colors['text'],
                size=self.config.font_sizes['montserrat_medium'],
                font_family=self.config.font_families['montserrat'],
                selectable=True,
            ),
            ft.Text(
                value=location,
                color=self.config.colors['muted'],
                size=self.config.font_sizes['montserrat_medium'],
                font_family=self.config.font_families['montserrat'],
                visible=bool(location),
            ),
        ]
        return ft.Container(
            content=ft.Column(
                controls=_control_list(
                    ft.Row(
                        controls=_control_list(
                            ft.Column(
                                controls=fragment_details,
                                spacing=3,
                                expand=True,
                                horizontal_alignment=(
                                    ft.CrossAxisAlignment.STRETCH
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                tooltip='Editar fragmento',
                                icon_color=self.config.colors['text'],
                                on_click=lambda event, current=fragment: (
                                    self._run_click_action(
                                        event,
                                        lambda: self.on_edit_fragment(
                                            self.compilation['id'],
                                            current,
                                        ),
                                    )
                                ),
                            ),
                        ),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=destination_control,
                        width=460,
                        padding=ft.Padding.only(top=4),
                    ),
                ),
                spacing=self.config.ui['control_gap'],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['bg'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
        )

    def _compose_work(self, index: int) -> ft.Container:
        work = self.compilation['works'][index]
        fragments = work['fragments']
        fragment_count_label = (
            'fragmento' if len(fragments) == 1 else 'fragmentos'
        )
        resource_id = work['id']
        fragment_sections: list[ft.Control] = []
        if fragments:
            for is_member, title in (
                (True, 'Selecionados para o caderno'),
                (False, 'Materiais disponíveis'),
            ):
                section_fragments = [
                    fragment
                    for fragment in fragments
                    if fragment['is_member'] is is_member
                ]
                if section_fragments:
                    rendered_fragments = [
                        self._compose_fragment(
                            fragment,
                        )
                        for fragment in section_fragments
                    ]
                    fragment_sections.append(
                        ft.Column(
                            controls=[
                                ft.Text(
                                    value=(
                                        title
                                        + f' ({len(section_fragments)})'
                                    ),
                                    color=self.config.colors['muted'],
                                    size=self.config.font_sizes[
                                        'montserrat_medium'
                                    ],
                                    weight=self.config.font_weights[
                                        'montserrat_semibold'
                                    ],
                                    font_family=self.config.font_families[
                                        'montserrat'
                                    ],
                                ),
                                *rendered_fragments,
                            ],
                            spacing=max(
                                2,
                                int(self.config.ui['grid_gap'] / 8),
                            ),
                            horizontal_alignment=(
                                ft.CrossAxisAlignment.STRETCH
                            ),
                        )
                    )
        else:
            fragment_sections.append(
                ft.Text(
                    value='Ainda não há fragmentos para esta obra.',
                    color=self.config.colors['muted'],
                    size=self.config.font_sizes['montserrat_small'],
                    font_family=self.config.font_families['montserrat'],
                )
            )
        return ft.Container(
            content=ft.Column(
                controls=_control_list(
                    ft.Row(
                        controls=_control_list(
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        value=work['title'],
                                        size=self.config.font_sizes[
                                            'cormorant_medium'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'cormorant'
                                            ]
                                        ),
                                        weight=(
                                            self.config.font_weights[
                                                'cormorant_semibold'
                                            ]
                                        ),
                                        color=self.config.colors['gold'],
                                        selectable=True,
                                    ),
                                    ft.Text(
                                        value=(
                                            f'{len(fragments)} '
                                            f'{fragment_count_label}'
                                        ),
                                        color=self.config.colors['muted'],
                                        size=self.config.font_sizes[
                                            'montserrat_small'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'montserrat'
                                            ]
                                        ),
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ARROW_UPWARD,
                                tooltip='Mover obra para cima',
                                disabled=index == 0,
                                on_click=lambda event, current=index: (
                                    self._run_click_action(
                                        event,
                                        lambda: self._move_work(
                                            current,
                                            -1,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ARROW_DOWNWARD,
                                tooltip='Mover obra para baixo',
                                disabled=(
                                    index == len(self.compilation['works']) - 1
                                ),
                                on_click=lambda event, current=index: (
                                    self._run_click_action(
                                        event,
                                        lambda: self._move_work(
                                            current,
                                            1,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                tooltip='Editar obra',
                                icon_color=self.config.colors['text'],
                                on_click=lambda event, work_id=resource_id: (
                                    self._run_click_action(
                                        event,
                                        lambda: self.on_edit_work(
                                            self.compilation['id'],
                                            work_id,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ADD_COMMENT_OUTLINED,
                                tooltip='Novo fragmento nesta obra',
                                icon_color=self.config.colors['gold'],
                                on_click=lambda event, work_id=resource_id: (
                                    self._run_click_action(
                                        event,
                                        lambda: self.on_create_fragment(
                                            self.compilation['id'],
                                            work_id,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip='Retirar obra e seus vínculos',
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda event, work_id=resource_id: (
                                    self._run_click_action(
                                        event,
                                        lambda: self._remove_work(work_id),
                                    )
                                ),
                            ),
                        ),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        controls=fragment_sections,
                        spacing=max(
                            2,
                            int(self.config.ui['grid_gap'] / 8),
                        ),
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                ),
                spacing=self.config.ui['modal_gap'],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['surface'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
        )

    def _compose_works_and_fragments(self) -> ft.Control:
        search_group = ft.Column(
            controls=[self.work_search, self.work_matches],
            spacing=2,
            tight=True,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    search_group,
                    ft.FilledButton(
                        content=ft.Text(
                            '+ Criar obra',
                            color=self.config.colors['bg'],
                            font_family=(
                                self.config.font_families['montserrat']
                            ),
                            size=self.config.font_sizes['montserrat_medium'],
                            weight=self.config.font_weights[
                                'montserrat_normal'
                            ],
                        ),
                        bgcolor=self.config.colors['gold'],
                        style=ft.ButtonStyle(
                            text_style=button_text_style(self.config),
                        ),
                        on_click=lambda event: self._run_click_action(
                            event,
                            lambda: self.on_create_work(
                                self.compilation['id']
                            ),
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=self.config.ui['control_gap'],
            )
        ]
        if not self.compilation['works']:
            controls.append(
                ft.Container(
                    content=ft.Text(
                        value=(
                            'Adicione uma obra existente ou crie uma nova '
                            'para começar a reunir fontes neste projeto.'
                        ),
                        color=self.config.colors['muted'],
                        size=self.config.font_sizes['montserrat_small'],
                        font_family=self.config.font_families['montserrat'],
                    ),
                    padding=self.config.ui['card_padding'],
                    bgcolor=self.config.colors['surface'],
                    border_radius=self.config.ui['card_radius'],
                )
            )
        else:
            controls.extend(
                self._compose_work(index)
                for index in range(len(self.compilation['works']))
            )
        return ft.Column(
            controls=controls,
            spacing=self.config.ui['grid_gap'],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _compose_content(self) -> ft.Container:
        tab_bar = ft.TabBar(
            tabs=[
                ft.Tab(label='Visão geral'),
                ft.Tab(label='Obras e fragmentos'),
                ft.Tab(label='Caderno de trabalho'),
            ],
            label_text_style=ft.TextStyle(
                font_family=self.config.font_families['cormorant'],
                size=self.config.font_sizes['cormorant_small'],
                weight=self.config.font_weights['cormorant_semibold'],
            ),
            unselected_label_text_style=ft.TextStyle(
                font_family=self.config.font_families['cormorant'],
                size=self.config.font_sizes['cormorant_small'],
                weight=self.config.font_weights['cormorant_semibold'],
            ),
            label_color=self.config.colors['gold'],
            unselected_label_color=self.config.colors['muted'],
            indicator_color=self.config.colors['gold'],
            divider_color=self.config.colors['border'],
        )
        tab_views = ft.TabBarView(
            expand=True,
            controls=[
                ft.Container(
                    content=self._compose_overview(),
                    padding=ft.Padding.only(top=12),
                    expand=True,
                ),
                ft.Container(
                    content=self._compose_works_and_fragments(),
                    padding=ft.Padding.only(top=12),
                    expand=True,
                ),
                ft.Container(
                    content=self._compose_caderno(),
                    padding=ft.Padding.only(top=12),
                    expand=True,
                ),
            ],
        )
        tabs = ft.Tabs(
            length=3,
            selected_index=self.selected_tab,
            on_change=lambda event: setattr(
                self,
                'selected_tab',
                event.control.selected_index,
            ),
            content=ft.Column(
                controls=[tab_bar, tab_views],
                expand=True,
                spacing=0,
            ),
            expand=True,
        )
        return ft.Container(
            content=ft.Column(
                controls=_control_list(
                    ft.Row(
                        controls=_control_list(
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        value=self.compilation['name'],
                                        size=self.config.font_sizes[
                                            'cormorant_large'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'cormorant'
                                            ]
                                        ),
                                        weight=(
                                            self.config.font_weights[
                                                'cormorant_semibold'
                                            ]
                                        ),
                                        color=self.config.colors['gold'],
                                    ),
                                    ft.Text(
                                        value=(
                                            'Hub de obras, fragmentos e '
                                            'relações deste projeto'
                                        ),
                                        color=self.config.colors['muted'],
                                        size=self.config.font_sizes[
                                            'montserrat_large'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'montserrat'
                                            ]
                                        ),
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                tooltip='Fechar hub',
                                icon_color=self.config.colors['text'],
                                on_click=self._close,
                            ),
                        ),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(
                        color=self.config.colors['border'],
                        height=1,
                    ),
                    tabs,
                ),
                spacing=self.config.ui['modal_gap'],
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            width=min(self.config.ui['modal_width'], 1200),
            height=min(self.config.ui['modal_height'], 820),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['surface'],
        )
