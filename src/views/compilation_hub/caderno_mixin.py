"""Mixin para o Caderno de Ideias e Esqueleto de Escrita no hub de compilações."""

from collections.abc import Callable
from functools import partial
import flet as ft

from src.contracts import (
    CompilationFragmentRecord,
    CompilationSectionRecord,
    CompilationWorkRecord,
)
from src.utils.fragment_reference import fragment_abnt_notation
from src.utils.view_styles import button_text_style, text_field_style
from .common import _control_list


class CompilationHubCadernoMixin:
    """Responsável pela gestão de ideias, seções do esqueleto e caderno de trabalho."""

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
        if section_id is not None:
            if after_create is not None:
                after_create(section_id)
            self.refresh()

    def _toggle_outline_edit(self, event: ft.Event[ft.Button]) -> None:
        del event
        self.editing_outline = not self.editing_outline
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
            fragment_details.append(
                self._compose_fragment_note(fragment)
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
        details.append(self._compose_fragment_note(fragment))
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
